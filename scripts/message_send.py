from serial_connection import SerialConnection
from settings import Settings
from parameters import ParameterAddress, CURRENT_INPUT_PARAMETERS, PRESET_PARAMETERS


def main():
    settings = Settings.load()
    connection = SerialConnection(settings)
    zone = 1
    address = ParameterAddress(zone=zone)
    parameter = CURRENT_INPUT_PARAMETERS.get("sub_level")
    resp = connection.query(address.get(parameter, 0),
        lambda data: address.read(parameter, data))
    print(resp)
    connection.close

if __name__ == "__main__":
    main()

