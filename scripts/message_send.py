from serial_connection import SerialConnection
from settings import Settings
from parameters import ParameterAddress, ZONE_POWER_PARAMETERS, PRESET_PARAMETERS


def main():
    settings = Settings.load()
    connection = SerialConnection(settings)
    zone = 1
    address = ParameterAddress(zone=zone)
    parameter = PRESET_PARAMETERS.get("volume")
    resp = connection.query(address.get(parameter, 0),
        lambda data: address.read(parameter, data))
    print(resp)


if __name__ == "__main__":
    main()

