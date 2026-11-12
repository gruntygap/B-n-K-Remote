"""One serial adapter for the process, with a queue of matched transactions.

HTTP workers enqueue commands. They never open a port. A single worker keeps
one adapter open and writes each transaction in order; bytes read while that
command is on the wire are its reply. The adapter is opened on the first real
exchange and reused until the process closes it or the port fails. A failed
write is not retried.
"""

import queue
import threading
import time

import serial


# Waiting commands, not counting the one currently on the wire. Waitress runs
# a few HTTP threads, so a short queue absorbs a burst without stacking stale
# presses behind a long delay.
QUEUE_DEPTH = 8


class SerialBusyError(Exception):
    pass


class SerialReplyTimeout(TimeoutError):
    """A bounded read ended; callers may still inspect validated partial state."""
    def __init__(self, response):
        super().__init__("No complete matching receiver reply")
        self.response = response


class _QueuedExchange:
    """One outbound transaction and the reply matched back to it."""

    def __init__(self, packets, accepts):
        self.packets = packets
        self.accepts = accepts
        self.response = b""
        self.error = None
        self._done = threading.Event()

    def finish(self, *, response=b"", error=None):
        self.response = response
        self.error = error
        self._done.set()

    def result(self, timeout):
        if not self._done.wait(timeout):
            raise TimeoutError("Timed out waiting for the serial queue")
        if self.error is not None:
            raise self.error.with_traceback(self.error.__traceback__)
        return self.response


class SerialConnection:
    def __init__(self, settings, factory=serial.Serial, queue_size=QUEUE_DEPTH):
        self.settings = settings
        self._factory = factory
        self._port = None
        self._port_lock = threading.Lock()
        self._state = threading.Lock()
        self._pending = queue.Queue(maxsize=queue_size)
        self._stop = threading.Event()
        self._closed = False
        self._worker = None

    def send(self, packet):
        return self._submit((packet,), None)

    def query(self, packet, accepts, before=None):
        """Read past echoes and updates until this request's matcher accepts.

        An optional preceding packet (a set or companion query) stays in the
        same queue entry and shares its reply buffer. Writes are never retried.
        """
        packets = (before, packet) if before is not None else (packet,)
        return self._submit(packets, accepts)

    def _submit(self, packets, accepts):
        if self.settings.dry_run:
            return b""
        exchange = _QueuedExchange(packets, accepts)
        with self._state:
            if self._closed:
                raise serial.SerialException("Serial connection closed")
            try:
                self._pending.put_nowait(exchange)
            except queue.Full:
                raise SerialBusyError("Receiver is busy. Try again.")
            self._ensure_worker()
        return exchange.result(self._wait_budget())

    def _ensure_worker(self):
        if self._worker is not None and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._run, name="bk-serial", daemon=False)
        self._worker.start()

    def _turn_budget(self):
        return self.settings.serial_write_timeout + max(0.5, self.settings.serial_timeout) + 0.25

    def _wait_budget(self):
        # Every waiting command, plus the one on the wire, can take a full turn.
        return self._turn_budget() * (self._pending.maxsize + 1) + 1

    def _run(self):
        try:
            while not self._stop.is_set():
                try:
                    exchange = self._pending.get(timeout=0.2)
                except queue.Empty:
                    continue
                if exchange is None or self._stop.is_set():
                    if exchange is not None:
                        exchange.finish(error=serial.SerialException("Serial connection closed"))
                    break
                self._run_exchange(exchange)
        finally:
            self._fail_pending(serial.SerialException("Serial connection closed"))
            self._close_port()

    def _run_exchange(self, exchange):
        try:
            response = self._match_reply(exchange)
        except Exception as error:
            exchange.finish(error=error)
        else:
            exchange.finish(response=response)

    def _match_reply(self, exchange):
        """Write this queue entry and keep only the bytes read for it.

        Later commands stay queued until this matcher accepts or times out,
        so a reply cannot be claimed by the wrong request.
        """
        try:
            port = self._open_port()
            # Unsolicited bytes from before this command cannot confirm it.
            port.reset_input_buffer()
            for packet in exchange.packets:
                written = port.write(packet)
                if written != len(packet):
                    raise serial.SerialException("Incomplete serial write")
            if exchange.accepts is None:
                return port.read_until(b")", size=4096)
            deadline = time.monotonic() + max(0.5, self.settings.serial_timeout)
            response = b""
            while len(response) < 4096 and time.monotonic() < deadline:
                chunk = port.read_until(b")", size=4096 - len(response))
                response += chunk
                if exchange.accepts(response):
                    return response
            raise SerialReplyTimeout(response)
        except SerialReplyTimeout:
            # A partial or unsupported parameter reply does not drop the adapter.
            raise
        except (serial.SerialException, OSError):
            self._close_port()
            # Never retry a write automatically: the receiver may have acted.
            raise

    def _open_port(self):
        with self._port_lock:
            if self._port is not None:
                return self._port
            if self._stop.is_set():
                raise serial.SerialException("Serial connection closed")
            port = self._factory(
                self.settings.serial_port,
                baudrate=self.settings.serial_baudrate,
                bytesize=self.settings.serial_bytesize,
                parity=self.settings.serial_parity,
                stopbits=self.settings.serial_stopbits,
                timeout=self.settings.serial_timeout,
                write_timeout=self.settings.serial_write_timeout,
                xonxoff=False, rtscts=False, dsrdtr=False,
            )
            self._port = port
        return port

    def _fail_pending(self, error):
        with self._state:
            self._closed = True
            abandoned = []
            while True:
                try:
                    exchange = self._pending.get_nowait()
                except queue.Empty:
                    break
                if exchange is not None:
                    abandoned.append(exchange)
        for exchange in abandoned:
            exchange.finish(error=error)

    def _close_port(self):
        with self._port_lock:
            port = self._port
            self._port = None
        if port is not None:
            try:
                port.close()
            except OSError:
                pass

    def close(self):
        with self._state:
            worker = self._worker
            if self._closed and (worker is None or not worker.is_alive()):
                return
            self._closed = True
            self._stop.set()
        if worker is not None:
            try:
                self._pending.put_nowait(None)
            except queue.Full:
                pass
            worker.join(self._turn_budget() + 1)
        self._close_port()
