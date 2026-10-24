"""Hardware-free integration checks: python -m unittest discover -s tests -v."""

from dataclasses import replace
import io
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from contextlib import redirect_stdout

import serial

from app import create_app
import control
from serial_connection import SerialBusyError, SerialConnection
from settings import Settings


class SettingsTests(unittest.TestCase):
    def test_env_file_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / ".env"
            env.write_text("SERIAL_PORT=/dev/test\nSERIAL_BAUDRATE=19200\nWEB_PORT=9000\n"
                           "DEVICE_ADDRESS=0x1A\nDEFAULT_ZONE=2\nREMOTE_ZONES=1,2,2\n")
            with patch.dict(os.environ, {"WEB_PORT": "8085"}, clear=True):
                settings = Settings.load(env)
        self.assertEqual(settings.serial_port, "/dev/test")
        self.assertEqual(settings.serial_baudrate, 19200)
        self.assertEqual(settings.web_port, 8085)
        self.assertEqual(settings.device_address, 26)
        self.assertEqual(settings.default_zone, 2)
        self.assertEqual(settings.remote_zones, (1, 2))

    def test_invalid_configuration_fails_early(self):
        for changes in ({"serial_timeout": 0}, {"serial_timeout": float("nan")},
                        {"serial_parity": ""}, {"web_port": 70000},
                        {"default_zone": 3}, {"device_address": -1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(Settings(), **changes).validate()


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.connection = Mock()
        self.connection.send.return_value = b""
        self.app = create_app(Settings(), self.connection)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_catalog_loading_never_sends(self):
        response = self.client.get("/api/remote")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["commands"]), 80)
        self.assertEqual(len(control.UNIT_PARAMETERS), 42)
        self.connection.send.assert_not_called()
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_every_ir_command_uses_configured_address_and_zone(self):
        client = create_app(replace(Settings(), device_address=0x1A), self.connection).test_client()
        for name in control.IR_COMMANDS:
            with self.subTest(command=name):
                response = client.post("/api/ir", json={"command": name, "zone": 2})
                self.assertEqual(response.status_code, 200)
                self.connection.send.assert_called_with(control.build_ir_command(name, 2, 0x1A))
                self.assertFalse(response.json["dry_run"])

    def test_invalid_input_cannot_reach_serial(self):
        for data in ([], None, {"command": []}, {"command": "missing"},
                     {"command": "power_on", "zone": True},
                     {"command": "power_on", "zone": 0},
                     {"command": "power_on", "zone": 100},
                     {"command": "power_on", "packet": "raw bytes"}):
            with self.subTest(data=data):
                response = self.client.post("/api/ir", json=data, content_type="application/json")
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post("/api/ir", data="command=power_on").status_code, 415)
        self.assertEqual(self.client.post("/api/ir", data='{"', content_type="application/json").status_code, 400)
        self.connection.send.assert_not_called()

    def test_mode_and_sub_level_codes(self):
        for name, code in (("mode_down", "00"), ("mode_up", "64"),
                           ("sub_level_up", "78"), ("sub_level_down", "B8")):
            with self.subTest(command=name):
                response = self.client.post("/api/ir", json={"command": name, "zone": 1})
                self.assertEqual(response.status_code, 200)
                self.connection.send.assert_called_with(control.build_bk_command(f"00,S,I,1={code}"))

    def test_cross_site_requests_rejected(self):
        response = self.client.post("/api/ir", json={"command": "power_on"},
                                    headers={"Origin": "https://example.org"})
        self.assertEqual(response.status_code, 403)
        self.connection.send.assert_not_called()

    def test_unavailable_or_busy_serial_is_explicit(self):
        for exception, status in ((serial.SerialException("unplugged"), 503),
                                  (SerialBusyError("busy"), 429)):
            self.connection.send.side_effect = exception
            with self.assertLogs(self.app.logger, level="ERROR") if status == 503 else patch("sys.stderr", io.StringIO()):
                response = self.client.post("/api/ir", json={"command": "power_on"})
            self.assertEqual(response.status_code, status)
            self.assertIn("error", response.json)

    def test_cli_env_defaults_and_unit_requests_are_preserved(self):
        settings = replace(Settings(), default_zone=2, device_address=0x1A)
        for args, packet in ((["--command", "volume_up"], control.build_ir_command("volume_up", 2, 0x1A)),
                             (["--get-unit", "serial_number"], control.build_unit_parameter_request("serial_number", 0x1A))):
            with patch("sys.argv", ["control.py", *args]), patch.object(Settings, "load", return_value=settings), patch("serial_connection.SerialConnection", return_value=self.connection), redirect_stdout(io.StringIO()):
                control.main()
            self.connection.send.assert_called_with(packet)
            self.connection.close.assert_called()


class SerialTests(unittest.TestCase):
    def setUp(self):
        self.port = Mock()
        self.port.write.side_effect = lambda packet: len(packet)
        self.port.read_until.return_value = b"(response)"
        self.factory = Mock(return_value=self.port)
        self.connection = SerialConnection(Settings(), self.factory)
        self.sleep = patch("serial_connection.time.sleep")
        self.sleep.start()
        self.addCleanup(self.sleep.stop)
        self.addCleanup(self.connection.close)

    def test_reuses_connection_and_bounds_reads(self):
        self.assertEqual(self.connection.send(b"(first)\r"), b"(response)")
        self.connection.send(b"(second)\r")
        self.assertEqual(self.factory.call_count, 1)
        self.port.read_until.assert_called_with(b")", size=4096)
        self.assertEqual(self.factory.call_args.kwargs["write_timeout"], 1)
        self.assertEqual(self.port.write.call_count, 2)

    def test_disconnect_closes_without_retry_then_reopens_on_next_press(self):
        self.port.write.side_effect = [serial.SerialException("unplugged"), 8]
        with self.assertRaises(serial.SerialException):
            self.connection.send(b"(first)\r")
        self.assertEqual(self.port.write.call_count, 1)
        self.port.close.assert_called_once()
        self.connection.send(b"(next)\r\n")
        self.assertEqual(self.factory.call_count, 2)

    def test_concurrent_press_is_rejected_without_queued_write(self):
        entered, release = threading.Event(), threading.Event()
        def block_read(*args, **kwargs):
            entered.set()
            release.wait(2)
            return b""
        self.port.read_until.side_effect = block_read
        thread = threading.Thread(target=self.connection.send, args=(b"one",))
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            with self.assertRaises(SerialBusyError):
                self.connection.send(b"two")
            self.assertEqual(self.port.write.call_count, 1)
        finally:
            release.set()
            thread.join(2)

    def test_preview_never_opens_adapter(self):
        connection = SerialConnection(replace(Settings(), dry_run=True), self.factory)
        self.assertEqual(connection.send(b"(test)\r"), b"")
        self.factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
