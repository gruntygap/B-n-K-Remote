import argparse
import time
import serial

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

# This will now correctly compile to: b'(00,S,P01=FF,01=50;03EF)\r'
# VOLUME_SET_COMMAND
# POWER_ON_COMMAND = build_bk_command("00,S,P01=FF,01=10")
# TOGGLE_POWER_COMMAND = build_bk_command("00,S,F,01=01")
POWER_ON_COMMAND = build_bk_command('00,S,I,1=80')

# input counter-clockwise: "00,S,F,01=0F"
# input clockwise "00,S,F,01=07"

# volume counter-clockwise (down): "00,S,F,01=0A"
# volume clockwise (up): "00,S,F,01=0B"

parser = argparse.ArgumentParser()
parser.add_argument("--port", required=True)
args = parser.parse_args()

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
    
    print(f"Sending formatted packet: {repr(POWER_ON_COMMAND)}")
    ser.write(POWER_ON_COMMAND)
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

