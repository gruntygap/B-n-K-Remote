"""Serve the compiled Svelte remote and a small same-origin IR API."""

import atexit
import logging
from urllib.parse import urlsplit

from flask import Flask, jsonify, request, send_from_directory
import serial
from werkzeug.exceptions import HTTPException

from control import IR_COMMANDS, build_ir_command
from parameters import CURRENT_INPUT_PARAMETERS, PRESET_PARAMETERS, ParameterAddress, VOLUME, ZONE_POWER_PARAMETERS
from serial_connection import SerialBusyError, SerialConnection, SerialReplyTimeout
from settings import ROOT, Settings


def create_app(settings=None, connection=None):
    settings = settings or Settings.load()
    settings.validate()
    connection = connection or SerialConnection(settings)
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 1024
    app.extensions["receiver"] = connection
    atexit.register(connection.close)
    dist = ROOT / "frontend" / "dist"

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith("/api/"):
            return jsonify(error=error.description), error.code
        return error

    @app.get("/api/remote")
    def remote():
        # Loading the page does not open the adapter or transmit a command.
        return jsonify(
            commands=[dict(name=name, code=f"{c.code:02X}", description=c.description)
                      for name, c in IR_COMMANDS.items()],
            zones=list(settings.remote_zones), default_zone=settings.default_zone,
            dry_run=settings.dry_run,
            parameters=[parameter.metadata() for parameter in PRESET_PARAMETERS.values()],
            current_input_parameters=[parameter.metadata() for parameter in CURRENT_INPUT_PARAMETERS.values()],
        )

    @app.get("/api/status")
    def status():
        origin = request.headers.get("Origin")
        if (request.headers.get("Sec-Fetch-Site") == "cross-site"
                or (origin and urlsplit(origin).netloc != request.host)):
            return jsonify(error="Use the remote from this server's website."), 403
        try:
            zone = int(request.args.get("zone", str(settings.default_zone)))
        except ValueError:
            return jsonify(error="Choose a configured zone."), 400
        if zone not in settings.remote_zones:
            return jsonify(error="Choose a configured zone."), 400
        supported = zone == 1
        parameters = (VOLUME, *CURRENT_INPUT_PARAMETERS.values()) if supported else (VOLUME,)
        parameter_address = ParameterAddress(zone=zone)
        power_parameter = ZONE_POWER_PARAMETERS.get(zone)
        realtime_address = ParameterAddress(block="realtime", zone=None)
        power = None
        readings = {parameter.name: None for parameter in parameters}
        if not settings.dry_run:
            def complete(response):
                return (all(reading is not None for reading in parameter_address.read_many(parameters, response).values())
                        and (power_parameter is None or realtime_address.read(power_parameter, response) is not None))
            try:
                # Read both blocks under one lock, retaining replies from both.
                power_packet = realtime_address.get(power_parameter, settings.device_address) if power_parameter else None
                response = connection.query(parameter_address.get_many(parameters, settings.device_address), complete,
                                            before=power_packet)
            except SerialReplyTimeout as error:
                response = error.response
            except TimeoutError:
                response = b""
            except SerialBusyError as error:
                return jsonify(error=str(error)), 429
            except (serial.SerialException, OSError):
                app.logger.exception("Status transaction failed")
                return jsonify(error="Serial connection unavailable. Check the adapter, port and permissions."), 503
            readings = parameter_address.read_many(parameters, response)
            if power_parameter:
                power = realtime_address.read(power_parameter, response)
        complete_reading = (not settings.dry_run and all(reading is not None for reading in readings.values())
                            and (power_parameter is None or power is not None))
        return jsonify(zone=zone, dry_run=settings.dry_run, volume=readings.pop("volume"),
                       current_input=readings, current_input_supported=supported,
                       power=power, power_supported=power_parameter is not None, complete=complete_reading)

    @app.route("/api/volume", methods=["GET", "POST"])
    def volume():
        origin = request.headers.get("Origin")
        if (request.headers.get("Sec-Fetch-Site") == "cross-site"
                or (origin and urlsplit(origin).netloc != request.host)):
            return jsonify(error="Use the remote from this server's website."), 403
        value = None
        if request.method == "POST":
            if not request.is_json:
                return jsonify(error="A JSON volume setting is required."), 415
            data = request.get_json()
            if not isinstance(data, dict) or set(data) - {"zone", "raw"} or "raw" not in data:
                return jsonify(error="Supply raw volume and an optional zone."), 400
            zone = data.get("zone", settings.default_zone)
            value = data["raw"]
            try:
                VOLUME.validate(value)
            except ValueError as error:
                return jsonify(error=str(error)), 400
        else:
            try:
                zone = int(request.args.get("zone", str(settings.default_zone)))
            except ValueError:
                return jsonify(error="Choose a configured zone."), 400
        if type(zone) is not int or zone not in settings.remote_zones:
            return jsonify(error="Choose a configured zone."), 400
        parameter_address = ParameterAddress(zone=zone)
        before = parameter_address.set(VOLUME, value, settings.device_address) if value is not None else None
        packet = parameter_address.get(VOLUME, settings.device_address)
        if settings.dry_run:
            # Preview has no live receiver state; do not invent a reading.
            return jsonify(zone=zone, dry_run=True, volume=None, packet=(before or packet).decode("ascii"))
        try:
            response = connection.query(packet, parameter_address.read_volume, before=before)
            reading = parameter_address.read_volume(response)
            if reading is None:
                raise TimeoutError("No matching receiver reply")
        except SerialBusyError as error:
            return jsonify(error=str(error)), 429
        except TimeoutError:
            return jsonify(error="No volume reply from the receiver. Check its RS-232 settings.",
                           zone=zone, volume=None), 504
        except (serial.SerialException, OSError):
            app.logger.exception("Volume transaction failed")
            return jsonify(error="Serial connection unavailable. Check the adapter, port and permissions."), 503
        return jsonify(zone=zone, dry_run=False, volume=reading)

    @app.post("/api/ir")
    def ir():
        origin = request.headers.get("Origin")
        if (request.headers.get("Sec-Fetch-Site") == "cross-site"
                or (origin and urlsplit(origin).netloc != request.host)):
            return jsonify(error="Use the remote from this server's website."), 403
        if not request.is_json:
            return jsonify(error="A JSON command is required."), 415
        data = request.get_json()
        if not isinstance(data, dict):
            return jsonify(error="Expected a JSON object."), 400
        if set(data) - {"command", "zone"}:
            return jsonify(error="Only command and zone may be supplied."), 400
        name = data.get("command")
        zone = data.get("zone", settings.default_zone)
        if not isinstance(name, str) or name not in IR_COMMANDS:
            return jsonify(error="Unknown IR command."), 400
        if type(zone) is not int or zone not in settings.remote_zones:
            return jsonify(error="Choose a configured zone."), 400
        packet = build_ir_command(name, zone, settings.device_address)
        try:
            response = connection.send(packet)
        except SerialBusyError as error:
            return jsonify(error=str(error)), 429
        except (serial.SerialException, OSError):
            app.logger.exception("Serial transaction failed")
            return jsonify(error="Serial connection unavailable. Check the adapter, port and permissions. "
                           "The command was not retried; check the receiver before sending again."), 503
        return jsonify(
            command=name, zone=zone, dry_run=settings.dry_run,
            packet=packet.decode("ascii"), response=response.decode("ascii", errors="replace"),
        )

    @app.get("/")
    def index():
        if not (dist / "index.html").is_file():
            return "Frontend not built. Run: cd frontend && npm ci && npm run build", 503
        response = send_from_directory(dist, "index.html")
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/assets/<path:filename>")
    def assets(filename):
        return send_from_directory(dist / "assets", filename, max_age=31536000)

    @app.get("/favicon.svg")
    def favicon():
        return send_from_directory(dist, "favicon.svg")

    return app


def main():
    from waitress import serve

    logging.basicConfig(level=logging.INFO)
    settings = Settings.load()
    app = create_app(settings)
    try:
        # One process owns the serial adapter; HTTP workers share its lock.
        serve(app, host=settings.web_host, port=settings.web_port, threads=4)
    finally:
        app.extensions["receiver"].close()


if __name__ == "__main__":
    main()
