from serial_connection import SerialConnection
from settings import Settings
from parameters import ParameterAddress, ZONE_POWER_PARAMETERS, PRESET_PARAMETERS


def main():
    settings = Settings.load()
    connection = SerialConnection(settings)
    zone = 1
    address = ParameterAddress(zone=zone)
    parameter = PRESET_PARAMETERS.get("volume")
    resp = connection.query(address.get(parameter, zone),
        lambda data: address.read(parameter, data) is not None)
    print(resp)


if __name__ == "__main__":
    main()

