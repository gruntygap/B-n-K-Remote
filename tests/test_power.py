"""Realtime power uses Appendix D identifiers 13/14 and Note 14 booleans."""
from dataclasses import replace
from unittest.mock import Mock, patch
import unittest

from app import create_app
from control import build_bk_command
from parameters import ParameterAddress, ZONE_POWER_PARAMETERS
from serial_connection import SerialConnection, SerialReplyTimeout
from settings import Settings
from test_status import power_reply, status_reply


class PowerTests(unittest.TestCase):
    def test_note_14_zone_identifiers_and_wire_format(self):
        address = ParameterAddress(block='realtime', zone=None)
        for zone, code in [(1, 0x13), (2, 0x14)]:
            parameter = ZONE_POWER_PARAMETERS[zone]
            self.assertEqual(parameter.code, code)
            self.assertEqual(address.get(parameter), build_bk_command(f'00,G,R,{code:X}'))
            for raw in (0, 1):
                reading = address.read(parameter, power_reply(zone, raw))
                self.assertIs(reading['value'], bool(raw))
                self.assertEqual(reading['label'], 'On' if raw else 'Off')
            self.assertIsNone(address.read(parameter, power_reply(zone, 2)))
            with self.assertRaises(ValueError):
                address.set(parameter, 1)

    def test_only_matching_realtime_reply_can_confirm_power(self):
        address = ParameterAddress(block='realtime', zone=None)
        parameter = ZONE_POWER_PARAMETERS[1]
        for frame in [power_reply(zone=2), build_bk_command('0,G,R,13'),
                      build_bk_command('0,R,P1=FF,13=1'), build_bk_command('0,R,S,13=1'),
                      power_reply().replace(b'13=1;', b'13=0;'), b'(0,R,R,13=1;FFFF)']:
            with self.subTest(frame=frame):
                self.assertIsNone(address.read(parameter, frame))
        self.assertIs(address.read(parameter, b'(0,R,G,R,13=0;)')['value'], False)

    def test_off_is_confirmed_even_if_sleeping_receiver_has_no_preset_reply(self):
        connection = Mock()
        connection.query.side_effect = SerialReplyTimeout(power_reply(raw=0))
        client = create_app(Settings(), connection).test_client()
        result = client.get('/api/status').json
        self.assertIs(result['power']['value'], False)
        self.assertEqual(result['power']['label'], 'Off')
        self.assertIsNone(result['volume'])
        self.assertFalse(result['complete'])
        self.assertTrue(result['power_supported'])

    def test_missing_or_other_zone_power_stays_unknown_despite_valid_presets(self):
        connection = Mock()
        client = create_app(Settings(), connection).test_client()
        for frame in [status_reply(), status_reply() + power_reply(zone=2), status_reply() + power_reply(raw=2)]:
            connection.query.return_value = frame
            result = client.get('/api/status').json
            self.assertIsNone(result['power'])
            self.assertEqual(result['volume']['value'], -40)
            self.assertFalse(result['complete'])

    def test_undocumented_zone_does_not_guess_a_power_identifier(self):
        connection = Mock()
        connection.query.return_value = status_reply('1=38', zone=3)
        settings = replace(Settings(), remote_zones=(1, 2, 3))
        result = create_app(settings, connection).test_client().get('/api/status?zone=3').json
        self.assertFalse(result['power_supported'])
        self.assertIsNone(result['power'])
        self.assertIsNone(connection.query.call_args.kwargs['before'])

    @patch('serial_connection.time.sleep')
    def test_companion_realtime_and_preset_queries_share_one_transaction(self, _sleep):
        for frames in [[power_reply(), status_reply()], [status_reply(), power_reply()]]:
            with self.subTest(frames=frames):
                port = Mock()
                port.write.side_effect = lambda packet: len(packet)
                port.read_until.side_effect = frames
                connection = SerialConnection(Settings(), Mock(return_value=port))
                try:
                    client = create_app(Settings(), connection).test_client()
                    response = client.get('/api/status')
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(response.json['complete'])
                    self.assertIs(response.json['power']['value'], True)
                    self.assertEqual(port.read_until.call_count, 2)
                    self.assertEqual([call.args[0] for call in port.write.call_args_list], [
                        build_bk_command('00,G,R,13'),
                        build_bk_command('00,G,P1=FF,1,F3,F4,F5,F6,F7,F8,F9')])
                    port.reset_input_buffer.assert_called_once()
                finally:
                    connection.close()


if __name__ == '__main__':
    unittest.main()
