from ..serial_connection import SerialConnection
from ..settings import Settings
from ..parameters import ParameterAddress, ZONE_POWER_PARAMETERS


def main():
    settings = Settings.load()
    connection = SerialConnection(settings)
    realtime_address = ParameterAddress(block="realtime", zone=None)
    zone = 1
    power_parameter = ZONE_POWER_PARAMETERS.get(zone)
    resp = connection.query((realtime_address.get(power_parameter, zone),
        lambda data: realtime_address.read(power_parameter, data) is not None))
    print(resp)


if __name__ == "__main__":
    main()

