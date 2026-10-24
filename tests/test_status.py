"""Current input aliases share a bounded poll with the live volume reading."""
from dataclasses import replace
from unittest.mock import Mock, patch
import unittest

import serial

from app import create_app
from control import build_bk_command
from parameters import CURRENT_INPUT_PARAMETERS, ParameterAddress, VOLUME
from serial_connection import SerialBusyError, SerialConnection, SerialReplyTimeout
from settings import Settings


def status_reply(values='1=38,F3=5,F4=1,F5=18,F6=5,F7=19,F8=F,F9=0', zone=1):
    return build_bk_command(f'0,R,P{zone:X}=FF,{values}')


class InputParameterTests(unittest.TestCase):
    def test_all_seven_aliases_and_note_conversions(self):
        parameters = tuple(CURRENT_INPUT_PARAMETERS.values())
        self.assertEqual([parameter.code for parameter in parameters], list(range(0xF3, 0xFA)))
        address = ParameterAddress()
        self.assertEqual(address.get_many(parameters, 0x1A), build_bk_command('1A,G,P1=FF,F3,F4,F5,F6,F7,F8,F9'))
        readings = address.read_many(parameters, status_reply())
        self.assertEqual(readings['surround_mode']['label'], 'Stereo')
        self.assertEqual(readings['surround_command']['label'], 'Lock Analog')
        self.assertEqual(readings['center_level']['value'], 0)
        self.assertEqual(readings['rear_level']['value'], 0.5)
        self.assertEqual(readings['sub_level']['value'], -12)
        self.assertEqual(readings['center_delay']['value'], 5)
        self.assertEqual(readings['rear_delay']['value'], 15)
        self.assertIn('without an exact mapping', CURRENT_INPUT_PARAMETERS['rear_delay'].note)
        for name in ['center_level', 'rear_level', 'sub_level']:
            self.assertEqual(CURRENT_INPUT_PARAMETERS[name].reading(0x30)['value'], 12)

    def test_model_dependent_command_is_not_misidentified(self):
        label = CURRENT_INPUT_PARAMETERS['surround_command'].reading(2)['label']
        self.assertIn('Lock DTS', label)
        self.assertIn('AC3 compression', label)

    def test_bad_parameter_does_not_hide_other_values(self):
        readings = ParameterAddress().read_many(CURRENT_INPUT_PARAMETERS.values(), status_reply('F3=7,F5=31,F6=6,F7=18,F8=10,F9=30'))
        for name in ['surround_mode', 'center_level', 'center_delay', 'rear_delay', 'surround_command']:
            self.assertIsNone(readings[name])
        self.assertEqual(readings['rear_level']['value'], 0)
        self.assertEqual(readings['sub_level']['value'], 12)


class StatusApiTests(unittest.TestCase):
    def setUp(self):
        self.connection = Mock()
        self.connection.query.return_value = status_reply()
        self.client = create_app(Settings(), self.connection).test_client()

    def test_one_poll_fetches_volume_and_all_input_aliases(self):
        result = self.client.get('/api/status?zone=1')
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json['complete'])
        self.assertTrue(result.json['current_input_supported'])
        self.assertEqual(result.json['volume']['value'], -40)
        self.assertEqual(len(result.json['current_input']), 7)
        self.assertEqual(result.headers['Cache-Control'], 'no-store')
        packet, accepts = self.connection.query.call_args.args
        self.assertEqual(packet, build_bk_command('00,G,P1=FF,1,F3,F4,F5,F6,F7,F8,F9'))
        self.assertFalse(accepts(status_reply('1=38')))
        self.assertFalse(accepts(status_reply(zone=2)))
        self.assertTrue(accepts(status_reply()))
        self.connection.query.assert_called_once()
        self.connection.send.assert_not_called()

    def test_configured_address_and_zone_two_do_not_request_zone_one_aliases(self):
        self.connection.query.return_value = status_reply('1=38', zone=2)
        client = create_app(replace(Settings(), device_address=0x1A), self.connection).test_client()
        response = client.get('/api/status?zone=2')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json['current_input_supported'])
        self.assertEqual(response.json['current_input'], {})
        self.assertTrue(response.json['complete'])
        self.assertEqual(self.connection.query.call_args.args[0], build_bk_command('1A,G,P2=FF,1'))

    def test_partial_timeout_keeps_only_valid_reported_fields(self):
        self.connection.query.side_effect = SerialReplyTimeout(status_reply('1=38,F5=18'))
        result = self.client.get('/api/status').json
        self.assertFalse(result['complete'])
        self.assertEqual(result['volume']['value'], -40)
        self.assertEqual(result['current_input']['center_level']['value'], 0)
        self.assertIsNone(result['current_input']['surround_mode'])
        self.connection.query.side_effect = TimeoutError()
        result = self.client.get('/api/status').json
        self.assertIsNone(result['volume'])
        self.assertFalse(result['complete'])
        self.assertTrue(all(reading is None for reading in result['current_input'].values()))

    def test_volume_is_required_for_a_complete_reply(self):
        self.connection.query.return_value = status_reply('F3=5,F4=1,F5=18,F6=5,F7=19,F8=F,F9=0')
        self.assertFalse(self.client.get('/api/status').json['complete'])

    def test_preview_and_validation_never_touch_serial(self):
        client = create_app(replace(Settings(), dry_run=True), self.connection).test_client()
        result = client.get('/api/status').json
        self.assertTrue(result['dry_run'])
        self.assertFalse(result['complete'])
        self.assertTrue(all(reading is None for reading in result['current_input'].values()))
        for zone in ['bad', '3', '0']:
            self.assertEqual(self.client.get('/api/status?zone=' + zone).status_code, 400)
        self.assertEqual(self.client.get('/api/status', headers={'Origin': 'https://example.com'}).status_code, 403)
        self.connection.query.assert_not_called()

    def test_serial_errors_are_explicit(self):
        self.connection.query.side_effect = SerialBusyError('busy')
        self.assertEqual(self.client.get('/api/status').status_code, 429)
        self.connection.query.side_effect = serial.SerialException('unplugged')
        with patch('logging.Logger.exception'):
            self.assertEqual(self.client.get('/api/status').status_code, 503)


class StatusSerialTests(unittest.TestCase):
    @patch('serial_connection.time.sleep')
    def test_split_reply_waits_for_last_parameter(self, _sleep):
        port = Mock()
        port.write.side_effect = lambda packet: len(packet)
        port.read_until.side_effect = [status_reply('1=38,F3=5,F4=1'), status_reply('F5=18,F6=5'), status_reply('F7=19,F8=F,F9=0')]
        connection = SerialConnection(Settings(), Mock(return_value=port))
        self.addCleanup(connection.close)
        address = ParameterAddress()
        parameters = (VOLUME, *CURRENT_INPUT_PARAMETERS.values())
        result = connection.query(address.get_many(parameters), lambda data: all(value is not None for value in address.read_many(parameters, data).values()))
        self.assertEqual(port.read_until.call_count, 3)
        self.assertEqual(address.read_many(parameters, result)['sub_level']['value'], -12)
        port.write.assert_called_once()

    @patch('serial_connection.time.sleep')
    def test_partial_timeout_preserves_bytes_and_connection(self, _sleep):
        port = Mock()
        port.write.side_effect = lambda packet: len(packet)
        port.read_until.return_value = status_reply('1=38')
        connection = SerialConnection(Settings(), Mock(return_value=port))
        self.addCleanup(connection.close)
        with patch('serial_connection.time.monotonic', side_effect=[0, 0, 1]):
            with self.assertRaises(SerialReplyTimeout) as caught:
                connection.query(b'query', lambda data: False)
        self.assertEqual(caught.exception.response, status_reply('1=38'))
        port.close.assert_not_called()
        port.write.assert_called_once()


if __name__ == '__main__':
    unittest.main()
