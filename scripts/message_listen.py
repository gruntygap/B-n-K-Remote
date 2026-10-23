
#!/usr/bin/env python3
"""Group and display complete B&K AVR 507 serial messages."""

import argparse
import time
from datetime import datetime

import serial


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=9600)
    args = parser.parse_args()

    with serial.Serial(
        args.port,
        baudrate=args.baud,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=0.05,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    ) as ser:
        print("Listening only; no commands will be sent.")
        print("Change Z1 Volume by one step at a time. Ctrl+C to stop.\n")

        buffer = bytearray()
        while True:
            data = ser.read(ser.in_waiting or 1)
            if not data:
                continue

            for byte in data:
                if byte == ord("("):
                    buffer = bytearray(b"(")
                elif buffer:
                    buffer.append(byte)
                    if byte == ord(")"):
                        msg = buffer.decode("ascii", errors="replace")
                        print(datetime.now().strftime("%H:%M:%S.%f")[:-3],
                              msg, flush=True)
                        buffer.clear()


if __name__ == "__main__":
    main()

