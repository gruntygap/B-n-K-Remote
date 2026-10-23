# B&K Serial Webremote

A local receiver remote for Raspberry Pi, with a Python backend and a Svelte
frontend sized for an iPhone. Physical-style controls cover power, volume, menu
navigation, inputs, tuner, tone and the number pad. All 76 Appendix F IR commands
are available in the searchable **All IR commands** drawer.

The existing 42 Unit Parameters, packet builders and command-line tools remain
available. The website currently sends IR commands; it does not query or display
the receiver's actual power, volume or selected input. Its display shows the last
command sent. A successful send means bytes were written, not that the receiver
acknowledged or acted on them.

The project targets a B&K AVR507 S2 via a USB serial-to-RJ45 RS-232 adapter.
The catalogs are transcribed from the included CT610/310/600 protocol appendices;
available commands depend on the receiver model.

## Install and configure

Use Python 3.10+ and Node.js 22.12+ for the frontend build. From the checkout:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` before connecting to your receiver. If `.env` already exists, retain
your settings rather than copying over it. The application loads the `.env` next
to `control.py`, regardless of the current working directory. Process environment
variables take precedence. Restart the server after changing settings.

| Setting | Default | Purpose |
| --- | --- | --- |
| `SERIAL_PORT` | `/dev/ttyUSB0` | Adapter device; a `/dev/serial/by-id/...` path is more stable on a Pi |
| `SERIAL_BAUDRATE` | `9600` | Serial baud rate |
| `SERIAL_BYTESIZE` | `8` | Serial data bits |
| `SERIAL_PARITY` | `N` | `N`, `E`, `O`, `M` or `S` |
| `SERIAL_STOPBITS` | `1` | `1`, `1.5` or `2` |
| `SERIAL_TIMEOUT` | `0.15` | Read timeout in seconds; increase for slower responses |
| `SERIAL_WRITE_TIMEOUT` | `1` | Write timeout in seconds |
| `DEVICE_ADDRESS` | `0` | Receiver address as decimal or `0x`-prefixed hex |
| `DEFAULT_ZONE` | `1` | Initially selected zone |
| `REMOTE_ZONES` | `1,2` | Comma-separated decimal zones shown in the remote |
| `WEB_HOST` | `0.0.0.0` | Listen on all network interfaces; use `127.0.0.1` for local-only access |
| `WEB_PORT` | `8080` | Website port |
| `DRY_RUN` | `false` | Set `true` to preview without opening or writing to serial |

Serial flow control is disabled. Both timeouts must be greater than zero and at
most five seconds. `.env` is ignored by Git; `.env.example` is the shared template.

Build the frontend once:

```sh
cd frontend
npm ci
npm run build
cd ..
```

Start the website:

```sh
.venv/bin/python control.py --serve
```

On your iPhone, join the same Wi-Fi and open `http://<pi-ip-address>:8080`
(or your configured port). Safari's **Share → Add to Home Screen** gives the
remote a convenient launcher. The server runs locally with no cloud service,
external fonts or third-party assets. It is intended for a trusted home network
and has no login.

The Python process serves `frontend/dist` and the API through Waitress. Node and
Vite are not used at runtime. You may build on another computer and copy
`frontend/dist/` onto the Pi at the same path, avoiding a Node installation on the
Pi. Run one server process per serial adapter. The shared connection opens on the
first command and stays open; a lock prevents interleaved writes. Busy requests
are rejected rather than queued, and failed writes are never retried automatically.

## Raspberry Pi startup

The user running the service needs serial access. On Raspberry Pi OS, add your
account to `dialout`, then log out and back in:

```sh
sudo usermod -aG dialout "$USER"
```

Edit `deploy/bk-remote.service` to match your username and checkout path. After
building the frontend and configuring `.env`, install the optional service:

```sh
sudo cp deploy/bk-remote.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bk-remote
journalctl -u bk-remote -f
```

Stop the service before using the standalone CLI or listener scripts with the
same serial adapter. They are separate processes and cannot share its connection.

## CLI and Python usage

The CLI uses the same `.env` serial settings. `--port`, `--zone` and `--address`
override the relevant settings for one command. Without an action it retains the
original behavior of sending `power_on`.

```sh
.venv/bin/python control.py --list-commands
.venv/bin/python control.py --list-unit-parameters
.venv/bin/python control.py --command volume_up
.venv/bin/python control.py --command input_3 --zone 2
.venv/bin/python control.py --get-unit serial_number
.venv/bin/python control.py --port /dev/ttyUSB1 --command power_off
```

Importing the static catalogs and packet builders does not open a serial port:

```python
from control import IR_COMMANDS, UNIT_PARAMETERS
from control import build_ir_command, build_unit_parameter_request

IR_COMMANDS["volume_up"].code              # 0x24
IR_COMMANDS["volume_up"].description       # "MASTER VOL +"
UNIT_PARAMETERS["serial_number"].code     # 0x10
packet = build_ir_command("volume_up", zone=1, address=0)
query = build_unit_parameter_request("serial_number", address=0)
```

## Development and verification

For a hardware-free preview, set `DRY_RUN=true` in `.env`, then start the Python
server. The remote labels preview mode and never opens the adapter. Set it back
to `false` before using the receiver.

The Svelte dev server supports hot reload with `cd frontend && npm run dev`.
Its API proxy targets Python at `127.0.0.1:8080`; update `frontend/vite.config.js`
if you change the backend port during development. The Python-hosted production
build always uses its own origin and needs no proxy or separate frontend port.

```sh
.venv/bin/python -m unittest discover -s tests -v
cd frontend
npm run check
npm run build
```

Tests use a fake serial adapter and cover configuration, all IR API commands,
input validation, concurrent presses, disconnect/reconnect behavior, preview mode
and CLI compatibility. Actual receiver behavior still needs hardware verification.

## License

[GNU GPL-3.0](LICENSE)

