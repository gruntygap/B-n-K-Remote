from serial_connection import SerialConnection
from settings import Settings
from parameters import Parameter, ParameterAddress, CURRENT_INPUT_PARAMETERS, PRESET_PARAMETERS


def main():
    settings = Settings.load()
    connection = SerialConnection(settings)
    zone = 1
    address = ParameterAddress(zone=None,block="system")
    parameter = CURRENT_INPUT_PARAMETERS.get("sub_level")
    for i in range(0, 20):
        parameter.code = 0x09 + i
        parameter.kind = 'integer'
        get_addr = address.get(parameter)
        print(get_addr)
        try:
            resp = connection.query(get_addr,
                lambda data: address.read(parameter, data))
            print(resp)
        except:
            print("fail")
    connection.close()

if __name__ == "__main__":
    main()

