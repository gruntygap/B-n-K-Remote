import argparse
import time
from typing import NamedTuple


class IRCommand(NamedTuple):
    code: int
    description: str


# Transcribed from Appendix F, pages 27-28 of the CT610/310/600
# BKC-DIP Product Specific Appendices, version 2.00.05 (02/09/04).
# Codes are hexadecimal; descriptions preserve the manual's wording.
# Example: IR_COMMANDS["power_on"].code == 0x40
IR_COMMANDS = {
    "save": IRCommand(0x02, "SAVE"),
    "balance_right": IRCommand(0x04, "(BALANCE) RIGHT"),
    "enter": IRCommand(0x0C, "ENTER"),
    "all_bk_power_off": IRCommand(0x14, "ALL B&K POWER OFF"),
    "all_bk_power_on": IRCommand(0x15, "ALL B&K POWER ON"),
    "all_bk_volume_down": IRCommand(0x16, "ALL B&K VOL DOWN"),
    "all_bk_volume_up": IRCommand(0x17, "ALL B&K VOL UP"),
    "station_up": IRCommand(0x18, "STATION +"),
    "all_bk_volume_0_db": IRCommand(0x19, "ALL B&K 0 dB VOL"),
    "all_bk_volume_minus_20_db": IRCommand(0x1A, "ALL B&K -20 dB VOL"),
    "all_bk_volume_minus_40_db": IRCommand(0x1B, "ALL B&K -40 dB VOL"),
    "all_bk_volume_minus_60_db": IRCommand(0x1D, "ALL B&K -60 dB VOL"),
    "all_bk_mute": IRCommand(0x1E, "ALL B&K MUTE"),
    "volume_up": IRCommand(0x24, "MASTER VOL +"),
    "tune_up": IRCommand(0x38, "TUNE +"),
    "osd_menu_1": IRCommand(0x3F, "OSD MENU 1"),
    "power_on": IRCommand(0x40, "POWER ON"),
    "osd_menu_2": IRCommand(0x41, "OSD MENU 2"),
    "osd_menu_3": IRCommand(0x42, "OSD MENU 3"),
    "osd_menu_4": IRCommand(0x43, "OSD MENU 4"),
    "power_toggle": IRCommand(0x45, "POWER (TOGGLE)"),
    "frequency": IRCommand(0x48, "FREQ"),
    "digit_2": IRCommand(0x4C, "2"),
    "input_6": IRCommand(0x52, "INPUT 6"),
    "zone_direct_input": IRCommand(0x5A, "ZONE_DIRECT_INPUT"),
    "analog_source_down": IRCommand(0x5B, "ANALOG SOURCE -"),
    "digit_8": IRCommand(0x5C, "8"),
    "analog_source_up": IRCommand(0x5D, "ANALOG SOURCE +"),
    "video_source_down": IRCommand(0x5E, "VIDEO SOURCE -"),
    "video_source_up": IRCommand(0x5F, "VIDEO SOURCE +"),
    "input_3": IRCommand(0x60, "INPUT 3"),
    "preset_down": IRCommand(0x63, "PRESET -"),
    "source_down": IRCommand(0x65, "SOURCE -"),
    "source_up": IRCommand(0x66, "SOURCE +"),
    "digit_5": IRCommand(0x6C, "5"),
    "am": IRCommand(0x6E, "AM"),
    "tuner": IRCommand(0x70, "TUNER"),
    "fm": IRCommand(0x71, "FM"),
    "up": IRCommand(0x74, "UP"),
    "input_9": IRCommand(0x76, "INPUT 9"),
    "digit_0": IRCommand(0x7C, "0"),
    "power_off": IRCommand(0x80, "POWER OFF"),
    "digit_1": IRCommand(0x8C, "1"),
    "input_2": IRCommand(0x90, "INPUT 2"),
    "plus_10": IRCommand(0x94, "+10"),
    "digit_7": IRCommand(0x9C, "7"),
    "treble_down": IRCommand(0x9E, "TREBLE -"),
    "treble_up": IRCommand(0x9F, "TREBLE +"),
    "input_1": IRCommand(0xA0, "INPUT 1"),
    "bass_down": IRCommand(0xA6, "BASS -"),
    "bass_up": IRCommand(0xA7, "BASS +"),
    "digit_4": IRCommand(0xAC, "4"),
    "input_4": IRCommand(0xB0, "INPUT 4"),
    "down": IRCommand(0xB4, "DOWN"),
    "exit": IRCommand(0xBE, "EXIT"),
    "mute": IRCommand(0xC0, "MUTE"),
    "volume_down": IRCommand(0xC4, "MASTER VOL -"),
    "band": IRCommand(0xC8, "BAND"),
    "digit_3": IRCommand(0xCC, "3"),
    "right": IRCommand(0xCF, "RIGHT"),
    "input_7": IRCommand(0xD0, "INPUT 7"),
    "left": IRCommand(0xD1, "LEFT"),
    "preset_up": IRCommand(0xD2, "PRESET +"),
    "stereo_mono": IRCommand(0xD7, "STEREO / MONO"),
    "tune_down": IRCommand(0xD8, "TUNE -"),
    "digit_9": IRCommand(0xDC, "9"),
    "input_8": IRCommand(0xE0, "INPUT 8"),
    "station_down": IRCommand(0xE8, "STATION -"),
    "digit_6": IRCommand(0xEC, "6"),
    "input_5": IRCommand(0xF0, "INPUT 5"),
    "mute_on": IRCommand(0xF1, "MUTE ON"),
    "mute_off": IRCommand(0xF2, "MUTE OFF"),
    "loudness_toggle": IRCommand(0xF3, "LOUDNESS (TOGGLE)"),
    "menu": IRCommand(0xF4, "MENU"),
    "balance_left": IRCommand(0xF8, "(BALANCE) LEFT"),
    "zone": IRCommand(0xFC, "ZONE"),
}

def build_bk_command(payload: str) -> bytes:
    """
    Forces payload to uppercase, appends a semicolon, calculates the 
    4-character hex checksum, wraps it in parentheses, and adds a \r.
    """
    payload_upper = payload.upper()
    
    # Include the semicolon in the text string BEFORE calculating the sum
    checksum_string = f"{payload_upper};"
    
    # Calculate checksum by summing ASCII character values (now including ';')
    checksum_val = sum(ord(char) for char in checksum_string)
    checksum_hex = f"{checksum_val:04X}"  # 4-digit uppercase hex
    
    # Assemble the final bracketed packet
    full_command = f"({checksum_string}{checksum_hex})\r"
    return full_command.encode('ascii')

def build_ir_command(name: str, zone: int = 1, address: int = 0) -> bytes:
    """Build a named IR packet, e.g. build_ir_command("volume_up", zone=1).

    Zone and device address are integers, encoded as hexadecimal on the wire.
    Unknown names raise KeyError. This builds bytes without sending them.
    """
    if zone < 1:
        raise ValueError("zone must be a positive integer")
    if address < 0:
        raise ValueError("address must be a non-negative integer")
    command = IR_COMMANDS[name]
    return build_bk_command(f"{address:02X},S,I,{zone:X}={command.code:02X}")


POWER_ON_COMMAND = build_ir_command("power_on")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port")
    parser.add_argument("--command", choices=IR_COMMANDS, default="power_on")
    parser.add_argument("--zone", type=int, default=1)
    parser.add_argument("--address", type=lambda value: int(value, 0), default=0,
                        help="Device address as decimal or 0x-prefixed hex (default: 0)")
    parser.add_argument("--list-commands", action="store_true",
                        help="List Appendix F IR commands and exit")
    args = parser.parse_args()

    if args.list_commands:
        for name, command in IR_COMMANDS.items():
            print(f"{name:28}  0x{command.code:02X}  {command.description}")
        return
    if not args.port:
        parser.error("--port is required when sending a command")
    try:
        packet = build_ir_command(args.command, args.zone, args.address)
    except ValueError as exc:
        parser.error(str(exc))

    # Listing commands and importing the catalog do not require pyserial.
    import serial

    print(f"Opening port {args.port}...")
    with serial.Serial(
        args.port,
        baudrate=9600,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.5,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    ) as ser:
        time.sleep(0.2) # Allow port initialization

        print(f"Sending formatted packet: {repr(packet)}")
        ser.write(packet)
        ser.flush()
        time.sleep(0.05)

        print("Waiting for receiver response...")
        time.sleep(1) # Give the processor time to respond

        # Read back any asynchronous confirmation states
        response = ser.read(ser.in_waiting or 1)
        if response:
            print("Receiver response:", repr(response))
        else:
            print("No response received; check the receiver display panel.")


if __name__ == "__main__":
    main()

