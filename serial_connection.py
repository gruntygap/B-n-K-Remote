"""One serial connection per process, with bounded, serialized transactions."""

import threading
import time

import serial


class SerialBusyError(Exception):
    pass


class SerialConnection:
    def __init__(self, settings, factory=serial.Serial):
        self.settings = settings
        self._factory = factory
        self._port = None
        self._lock = threading.Lock()

    def send(self, packet):
        # Reject excess requests instead of building a queue of delayed presses.
        if not self._lock.acquire(blocking=False):
            raise SerialBusyError("Receiver is busy. Try again.")
        try:
            if self.settings.dry_run:
                return b""
            if self._port is None:
                self._port = self._factory(
                    self.settings.serial_port,
                    baudrate=self.settings.serial_baudrate,
                    bytesize=self.settings.serial_bytesize,
                    parity=self.settings.serial_parity,
                    stopbits=self.settings.serial_stopbits,
                    timeout=self.settings.serial_timeout,
                    write_timeout=self.settings.serial_write_timeout,
                    xonxoff=False, rtscts=False, dsrdtr=False,
                )
                time.sleep(0.05)
            # Discard old asynchronous feedback; returned bytes are diagnostic
            # only and are not interpreted as acknowledgement or receiver state.
            self._port.reset_input_buffer()
            written = self._port.write(packet)
            if written != len(packet):
                raise serial.SerialException("Incomplete serial write")
            return self._port.read_until(b")", size=4096)
        except (serial.SerialException, OSError):
            self._close_port()
            # Never retry a write automatically: the receiver may have acted.
            raise
        finally:
            self._lock.release()

    def _close_port(self):
        if self._port is not None:
            try:
                self._port.close()
            except OSError:
                pass
            self._port = None

    def close(self):
        with self._lock:
            self._close_port()
