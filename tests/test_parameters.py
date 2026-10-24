"""Protocol examples and serial/API behavior for live preset volume."""
from dataclasses import replace
from unittest.mock import Mock, patch
import unittest

import serial

from app import create_app
from control import build_bk_command
from parameters import Parameter, ParameterAddress, PRESET_PARAMETERS, VOLUME
from serial_connection import SerialBusyError, SerialConnection
from settings import Settings


def reply(raw=0x60, zone=1, preset=0xFF):
    return build_bk_command(f"0,R,P{zone:X}={preset:X},1={raw:X}")


class ParameterTests(unittest.TestCase):
    def test_note_one_mute_and_db_conversion(self):
        for raw, db in [(0, None), (1, -95), (0x38, -40), (0x60, 0), (0x6F, 15)]:
            with self.subTest(raw=raw):
                reading = VOLUME.reading(raw)
                self.assertEqual(reading["raw"], raw)
                self.assertEqual(reading["value"], db)
        self.assertEqual(VOLUME.reading(0)["label"], "Mute")
        for bad in [-1, 112, True, 10.5, "60", None]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                VOLUME.validate(bad)

    def test_identity_includes_block_zone_and_preset(self):
        current = ParameterAddress(zone=2)
        stored = ParameterAddress(zone=2, preset=0xA)
        self.assertNotEqual(current, stored)
        self.assertEqual(current.get(VOLUME), build_bk_command("00,G,P2=FF,1"))
        self.assertEqual(stored.set(VOLUME, 0x60), build_bk_command("00,S,P2=A,1=60"))
        self.assertEqual(ParameterAddress(block="unit", zone=None).get(VOLUME), build_bk_command("00,G,F4,1"))
        with self.assertRaises(ValueError):
            ParameterAddress(preset=0xFE).selector()
        with self.assertRaises(ValueError):
            ParameterAddress(block="realtime", zone=None).set(VOLUME, 1)

    def test_different_parameter_value_types(self):
        title = PRESET_PARAMETERS["title"]
        self.assertEqual(title.reading("Movie")['value'], "Movie")
        self.assertEqual(title.encode("Movie"), '"Movie"')
        for invalid in ["long title exceeding thirteen", 'bad"quote', 'bad;packet', '☃']:
            with self.assertRaises(ValueError):
                title.encode(invalid)
        self.assertEqual(PRESET_PARAMETERS["tuner_band"].reading(1)["label"], "FM")
        with self.assertRaises(ValueError):
            PRESET_PARAMETERS["tuner_band"].encode(2)
        self.assertIs(PRESET_PARAMETERS["tuner_fm_mode"].reading(0)["value"], False)
        self.assertEqual(Parameter("flags", 0, "Flags", kind="bitmask", maximum=7).encode(5), "5")
        level = Parameter("level", 10, "Center level", maximum=0x30, unit="dB", scale=0.5, offset=-12)
        self.assertEqual(level.reading(0x18)["value"], 0)

    def test_generic_reading_keeps_types_case_and_parameter_identity(self):
        address = ParameterAddress()
        title = PRESET_PARAMETERS['title']
        self.assertEqual(address.read(title, b'(0,R,P1=FF,0="Movie Time";)')['value'], 'Movie Time')
        band = PRESET_PARAMETERS['tuner_band']
        self.assertEqual(address.read(band, b'(0,R,P1=FF,4=1;)')['label'], 'FM')
        stereo = PRESET_PARAMETERS['tuner_fm_mode']
        self.assertIs(address.read(stereo, b'(0,R,P1=FF,7=1;)')['value'], True)
        system = ParameterAddress(block='system', zone=None)
        self.assertEqual(system.read(title, b'(0,R,S,0="Cinema";)')['value'], 'Cinema')
        self.assertIsNone(address.read(title, b'(0,R,P1=FF,1=60;)'))
        self.assertIsNone(address.read(title, b'(0,R,P1=FF,0=Unquoted;)'))

    def test_reply_validation_and_matching(self):
        address = ParameterAddress()
        frames = [reply(zone=2), reply(preset=3), build_bk_command("0,G,P1=FF,1"),
                  build_bk_command("0,S,P1=FF,1=60"), reply(112), reply().replace(b"60;", b"61;"),
                  b"(0,R,P1=FF,1=60;BAD)", b"(0,R,P1=FF,1=60;FFFF)"]
        for frame in frames:
            with self.subTest(frame=frame):
                self.assertIsNone(address.read_volume(frame))
        echo = build_bk_command("0,E,G,P1=FF,1")
        self.assertEqual(address.read_volume(echo + reply())["value"], 0)
        self.assertEqual(address.read_volume(b"(0,R,P01=FF,01=38;)")["value"], -40)
        self.assertEqual(address.read_volume(b"(0,R,G,P1=FF,1=1;)")["value"], -95)
        self.assertIsNone(address.read_volume(b"(0,R,P1=FF,1=60;"))
        self.assertIsNone(address.read_volume(b"(0,R,P1=FF,1=\xff;)"))


class VolumeApiTests(unittest.TestCase):
    def setUp(self):
        self.connection = Mock()
        self.connection.query.return_value = reply()
        self.client = create_app(Settings(), self.connection).test_client()

    def test_live_volume_reads_current_preset(self):
        result = self.client.get('/api/volume?zone=1')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['volume']['value'], 0)
        self.assertEqual(result.headers['Cache-Control'], 'no-store')
        self.assertEqual(self.connection.query.call_args.args[0], build_bk_command('00,G,P1=FF,1'))
        self.assertIsNone(self.connection.query.call_args.kwargs['before'])

    def test_set_uses_configured_address_and_actual_readback(self):
        self.connection.query.return_value = reply(0x37, zone=2)
        client = create_app(replace(Settings(), device_address=26), self.connection).test_client()
        result = client.post('/api/volume', json={'zone': 2, 'raw': 0x38})
        self.assertEqual(result.status_code, 200)
        # Device-reported value, even when it differs from the requested value.
        self.assertEqual(result.json['volume']['value'], -41)
        self.assertEqual(self.connection.query.call_args.args[0], build_bk_command('1A,G,P2=FF,1'))
        self.assertEqual(self.connection.query.call_args.kwargs['before'], build_bk_command('1A,S,P2=FF,1=38'))

    def test_invalid_requests_never_touch_serial(self):
        for data in [[], {'raw': None}, {'raw': True}, {'raw': -1}, {'raw': 112},
                     {'raw': 40.5}, {'raw': 40, 'zone': True}, {'raw': 40, 'zone': 3},
                     {'raw': 40, 'preset': 10}, {}]:
            with self.subTest(data=data):
                self.assertEqual(self.client.post('/api/volume', json=data).status_code, 400)
        for zone in ['bad', '3', '0']:
            self.assertEqual(self.client.get('/api/volume?zone=' + zone).status_code, 400)
        self.assertEqual(self.client.post('/api/volume', data='raw=40').status_code, 415)
        for method in ['get', 'post']:
            self.assertEqual(getattr(self.client, method)('/api/volume', headers={'Origin': 'https://example.com'}).status_code, 403)
        self.connection.query.assert_not_called()

    def test_preview_has_no_fabricated_live_volume(self):
        client = create_app(replace(Settings(), dry_run=True), self.connection).test_client()
        for response in [client.get('/api/volume'), client.post('/api/volume', json={'raw': 40})]:
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.json['volume'])
        self.connection.query.assert_not_called()

    def test_timeout_and_mismatch_do_not_confirm_requested_volume(self):
        for frame in [b'', reply(zone=2)]:
            self.connection.query.return_value = frame
            response = self.client.post('/api/volume', json={'raw': 40})
            self.assertEqual(response.status_code, 504)
            self.assertIsNone(response.json['volume'])
        for exc, status in [(TimeoutError(), 504), (SerialBusyError('busy'), 429), (serial.SerialException('offline'), 503)]:
            self.connection.query.side_effect = exc
            with patch('app.Flask.log_exception'), patch('logging.Logger.exception'):
                self.assertEqual(self.client.get('/api/volume').status_code, status)


class VolumeSerialTests(unittest.TestCase):
    def setUp(self):
        self.port = Mock()
        self.port.write.side_effect = lambda packet: len(packet)
        self.connection = SerialConnection(Settings(), Mock(return_value=self.port))
        self.addCleanup(self.connection.close)

    @patch('serial_connection.time.sleep')
    def test_query_skips_echoes_unrelated_replies_and_partial_packets(self, _sleep):
        self.port.read_until.side_effect = [build_bk_command('0,E,G,P1=FF,1'), reply(zone=2), reply()[:10], reply()[10:]]
        address = ParameterAddress()
        result = self.connection.query(address.get(VOLUME), address.read_volume, before=address.set(VOLUME, 96))
        self.assertEqual(address.read_volume(result)['value'], 0)
        self.assertEqual([c.args[0] for c in self.port.write.call_args_list], [address.set(VOLUME, 96), address.get(VOLUME)])
        self.port.reset_input_buffer.assert_called_once()

    @patch('serial_connection.time.sleep')
    def test_missing_reply_is_bounded_without_resending(self, _sleep):
        self.port.read_until.return_value = b''
        with patch('serial_connection.time.monotonic', side_effect=[0, 0, 1]):
            with self.assertRaises(TimeoutError):
                self.connection.query(b'query', lambda response: False)
        self.port.write.assert_called_once_with(b'query')

    @patch('serial_connection.time.sleep')
    def test_failed_set_is_not_retried_or_followed_by_get(self, _sleep):
        self.port.write.side_effect = serial.SerialException('unplugged')
        with self.assertRaises(serial.SerialException):
            self.connection.query(b'query', lambda response: True, before=b'set')
        self.port.write.assert_called_once_with(b'set')
        self.port.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
