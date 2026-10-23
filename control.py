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


class UnitParameter(NamedTuple):
    code: int
    description: str
    note: str


# Appendix E, page 21 of the same CT610/310/600 manual. The note field
# references the explanations on pages 22-26; Note 16* limits CT600 to one tuner.
# Page 21 prints "LSB" for both 0x23 and 0x25. Their lookup names use MSB
# as explained by Notes 26-27; descriptions below retain the printed wording.
UNIT_PARAMETERS = {
    "unit_name": UnitParameter(0x00, "Unit name", "1"),
    "version": UnitParameter(0x01, "Version", "2"),
    "zone_description": UnitParameter(0x02, "Zone Description", "3"),
    "amplifier_description": UnitParameter(0x06, "Amplifier Description", "4"),
    "video_scan_rate": UnitParameter(0x07, "Video Scan Rate (NTSC/PAL)", "5"),
    "am_steps": UnitParameter(0x08, "AM steps 9kHz/10kHz", "6"),
    "fm_steps": UnitParameter(0x09, "FM steps 100kHz/200kHz", "7"),
    "active_bkc_dip_version": UnitParameter(0x0C, "Active BKC-DIP Version", "8"),
    "software_time_stamp": UnitParameter(0x0D, "Software Time Stamp", "9"),
    "serial_number": UnitParameter(0x10, "Serial Number", "10"),
    "highest_bkc_dip_version": UnitParameter(0x11, "Highest BKC-DIP Version Available", "11"),
    "active_logical_zone_numbers": UnitParameter(0x12, "Active Logical Zone Numbers", "12"),
    "number_of_inputs": UnitParameter(0x13, "Number of Inputs", "13"),
    "number_of_zones": UnitParameter(0x14, "Number of Zones", "14"),
    "number_of_dedicated_inputs": UnitParameter(0x15, "Number of Dedicated Inputs", "15"),
    "number_of_tuners": UnitParameter(0x16, "Number of Tuners", "16*"),
    "number_of_control_outputs": UnitParameter(0x17, "Number of Control Outputs", "17"),
    "number_of_control_inputs": UnitParameter(0x18, "Number of Control Inputs", "18"),
    "number_of_page_events": UnitParameter(0x19, "Number of Page/Events", "19"),
    "number_of_input_boards": UnitParameter(0x1A, "Number of Input Boards", "20"),
    "number_of_output_boards": UnitParameter(0x1B, "Number of Output Boards", "21"),
    "number_of_external_inputs": UnitParameter(0x1C, "Number of External Inputs", "22"),
    "number_of_zones_and_detectors": UnitParameter(0x1D, "Number of Zones and Detectors", "23"),
    "receive_id": UnitParameter(0x1E, "Receive ID", "24"),
    "transmit_id": UnitParameter(0x1F, "Transmit ID", "24"),
    "input_bitmap_lsb": UnitParameter(0x20, "Input Bitmap LSB", "25"),
    "input_bitmap_msb": UnitParameter(0x21, "Input Bitmap MSB", "25"),
    "output_bitmap_lsb": UnitParameter(0x22, "Output Bitmap LSB", "26"),
    "output_bitmap_msb": UnitParameter(0x23, "Output Bitmap LSB", "26"),
    "dedicated_input_bitmap_lsb": UnitParameter(0x24, "Dedicated Input Bitmap LSB", "27"),
    "dedicated_input_bitmap_msb": UnitParameter(0x25, "Dedicated Input Bitmap LSB", "27"),
    "serial_macro_free_space_msb": UnitParameter(0x26, "Serial Macro Free Space MSB", "28"),
    "serial_macro_free_space_lsb": UnitParameter(0x27, "Serial Macro Free Space LSB", "28"),
    "rf_remote": UnitParameter(0x28, "RF Remote", "29"),
    "group_code_set_list": UnitParameter(0x29, "Group Code Set List", "30"),
    "audio_input_detect_bitmap_lsb": UnitParameter(0x2A, "Audio Input Detect Bitmap LSB", "31"),
    "audio_input_detect_bitmap_msb": UnitParameter(0x2B, "Audio Input Detect Bitmap MSB", "31"),
    "video_input_detect_bitmap_lsb": UnitParameter(0x2C, "Video Input Detect Bitmap LSB", "31"),
    "video_input_detect_bitmap_msb": UnitParameter(0x2D, "Video Input Detect Bitmap MSB", "31"),
    "control_input_detect_bitmap": UnitParameter(0x2E, "Control Input Detect Bitmap", "32"),
    "control_output_status_bitmap": UnitParameter(0x2F, "Control Output Status Bitmap", "33"),
    "tuner_detect_status_bitmap": UnitParameter(0x30, "Tuner Detect Status Bitmap", "34"),
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


def build_unit_parameter_request(name: str, address: int = 0) -> bytes:
    """Build a get request, e.g. build_unit_parameter_request("serial_number").

    Unit parameters use G,F4 and have no zone selector. The device address
    is an integer encoded as hexadecimal. Unknown names raise KeyError.
    This builds bytes without sending them; responses are displayed raw by CLI.
    """
    if address < 0:
        raise ValueError("address must be a non-negative integer")
    parameter = UNIT_PARAMETERS[name]
    return build_bk_command(f"{address:02X},G,F4,{parameter.code:02X}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--command", choices=IR_COMMANDS,
                        help="IR command to send (default: power_on)")
    action.add_argument("--get-unit", choices=UNIT_PARAMETERS,
                        help="Get an Appendix E unit parameter (no zone selector)")
    parser.add_argument("--zone", type=int, default=1)
    parser.add_argument("--address", type=lambda value: int(value, 0), default=0,
                        help="Device address as decimal or 0x-prefixed hex (default: 0)")
    parser.add_argument("--list-commands", action="store_true",
                        help="List Appendix F IR commands and exit")
    parser.add_argument("--list-unit-parameters", action="store_true",
                        help="List Appendix E unit parameters and exit")
    args = parser.parse_args()

    if args.list_commands or args.list_unit_parameters:
        if args.list_commands:
            for name, command in IR_COMMANDS.items():
                print(f"{name:28}  0x{command.code:02X}  {command.description}")
        if args.list_unit_parameters:
            for name, parameter in UNIT_PARAMETERS.items():
                print(f"{name:32}  0x{parameter.code:02X}  "
                      f"{parameter.description} (Note {parameter.note})")
        return
    if not args.port:
        parser.error("--port is required when sending a command")
    try:
        if args.get_unit:
            packet = build_unit_parameter_request(args.get_unit, args.address)
        else:
            packet = build_ir_command(args.command or "power_on", args.zone, args.address)
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

