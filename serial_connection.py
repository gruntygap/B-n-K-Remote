"""One serial connection per process, with bounded, serialized transactions."""

import threading
import time

import serial


class SerialBusyError(Exception):
    pass


class SerialReplyTimeout(TimeoutError):
    """A bounded read ended; callers may still inspect validated partial state."""
    def __init__(self, response):
        super().__init__("No complete matching receiver reply")
        self.response = response


class SerialConnection:
    def __init__(self, settings, factory=serial.Serial):
        self.settings = settings
        self._factory = factory
        self._port = None
        self._lock = threading.Lock()

    def send(self, packet):
        return self._exchange(packet)

    def query(self, packet, accepts, before=None):
        """Read past echoes/updates until the requested state arrives.

        An optional preceding packet (a set or companion query) shares the
        same lock and reply buffer. Writes are never retried.
        """
        return self._exchange(packet, accepts, before)

    def _exchange(self, packet, accepts=None, before=None):
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
            # Start a fresh transaction; unsolicited feedback from before this
            # request cannot confirm a new setting.
            self._port.reset_input_buffer()
            if before is not None:
                written = self._port.write(before)
                if written != len(before):
                    raise serial.SerialException("Incomplete serial write")
            written = self._port.write(packet)
            if written != len(packet):
                raise serial.SerialException("Incomplete serial write")
            if accepts is None:
                return self._port.read_until(b")", size=4096)
            deadline = time.monotonic() + max(0.5, self.settings.serial_timeout)
            response = b""
            while len(response) < 4096 and time.monotonic() < deadline:
                chunk = self._port.read_until(b")", size=4096 - len(response))
                response += chunk
                if accepts(response):
                    return response
            raise SerialReplyTimeout(response)
        except SerialReplyTimeout:
            # A partial/unsupported parameter reply does not disconnect the adapter.
            raise
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
