#!/usr/bin/env python3
"""Passive listener for B&K AVR 507 Series 2 BKC-DIP messages."""

import argparse
import time
from datetime import datetime

import serial


def main():
    parser = argparse.ArgumentParser(
        description="Listen to AVR 507 S2 RS-232 without transmitting."
    )
    parser.add_argument("--port", required=True,
                        help="e.g. /dev/cu.usbserial-A9IL85TE")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--log", default="avr507_rx.log")
    args = parser.parse_args()

    print(f"Opening {args.port} at {args.baud} baud (8N1).")
    print("PASSIVE MODE: this script sends no commands.")
    print("Now change the receiver's Z1 Volume from the front panel.")
    print("Press Ctrl+C to stop.\n")

    try:
        with serial.Serial(
            port=args.port,
            baudrate=args.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        ) as ser, open(args.log, "a", buffering=1) as log:
            log.write(f"\n--- Session {datetime.now().isoformat()} ---\n")
            print(f"Logging to {args.log}")

            while True:
                data = ser.read(ser.in_waiting or 1)
                if not data:
                    continue

                stamp = datetime.now().isoformat(timespec="milliseconds")
                printable = data.decode("ascii", errors="backslashreplace")
                line = f"{stamp} RX raw={data!r} ascii={printable}"
                print(line, flush=True)
                log.write(line + "\n")

    except KeyboardInterrupt:
        print("\nListener stopped.")
    except serial.SerialException as exc:
        raise SystemExit(f"Serial error: {exc}")


if __name__ == "__main__":
    main()
