# B&K Serial Webremote

A local receiver remote for Raspberry Pi, with a Python backend and a Svelte
frontend sized for an iPhone. Physical-style controls cover power, volume, menu
navigation, inputs, tuner, tone and the number pad. All 80 configured IR commands
are available in the searchable **All IR commands** drawer.

The volume dial beside the volume buttons supports touch rotation and keyboard
arrows (Page Up/Down adjust five steps). It polls the selected zone once per
second while visible and reads the receiver back after dial changes and IR
commands. Touching the dial does not jump the volume. Fast rotations combine
pending changes into the latest requested setting instead of queuing old moves.
The dial shows the live reading in dB, or an unavailable state when there is no
matching reply. During rotation, its caption distinguishes live volume from the
requested setting.

A second LCD below the wheel shows the current input's surround mode, surround
command, center/rear/sub levels and center/rear delays. Levels use half-decibel
steps from -12 to +12 dB. These `F3..F9` aliases are documented for Zone 1 only;
Zone 2 displays an availability message. Missing or invalid replies show dashes.
Surround command 2 retains both model-specific meanings. Rear delay is shown
for non-Pro Logic; the PDF gives a 16-30 ms Pro Logic range without an exact
raw-value mapping, so the display notes that distinction.
Surround mode and sub-level +/- buttons below this display send Series I IR
codes `00`/`64` and `B8`/`78`, respectively, then refresh the reported values.

The top indicator shows the selected zone's reported power as On, Off or Unknown
(Preview without a receiver). Power is read from Appendix D realtime parameter
`13` for Zone 1 or `14` for Zone 2; Note 14 defines `0` as Off and `1` as On.

The existing 42 Unit Parameters, packet builders and command-line tools remain
available. The LCD still shows the last IR command; the selected input is not
queried. An IR send means bytes were written, not that the receiver acknowledged
or acted on them.

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
Opening the web remote now queries volume and opens the adapter; loading only
the `/api/remote` catalog does not transmit anything.

## Parameters and live volume

`parameters.py` defines `Parameter` metadata (identifier, wire type, bounds,
choices, unit, scale/offset and special values) separately from `ParameterAddress`
(block, zone and preset). This supports text, integer, boolean, enum and bitmask
values, and preset, system, realtime and unit blocks. A reading retains `raw`
alongside the converted `value`, `unit` and `label`. For example, volume raw
`0x38` is `{raw: 56, value: -40, unit: "dB", label: null}`; raw zero is mute,
with a null numeric value. The initial common preset catalog covers title,
volume, balance, tuner band and FM mode. It is not a complete model catalog.
Parameters whose meanings depend on model, zone, tuning region or surround mode
need their own definitions/conversion context; identifier alone is not a key.
`CURRENT_INPUT_PARAMETERS` holds the separate Zone 1 alias definitions.

Volume follows the included Series I appendix, pages 6-8: preset parameter `01`,
with `FF` selecting the live working preset. Note 1 defines `00` as mute and
`01..6F` as -95..+15 dB (`raw - 96`). Reads use `(00,G,P1=FF,1;checksum)`;
dial writes use `(00,S,P1=FF,1=value;checksum)` followed by a read under the same
serial lock. Stored presets are not modified. Configure the receiver's RS-232
port and receive/transmit settings to permit replies; the dedicated adapter is
assumed to connect to one receiver. Compatibility still depends on receiver model.

`GET /api/volume?zone=1` returns the reported reading. `POST /api/volume` accepts
`{"zone": 1, "raw": 56}` and returns actual readback rather than echoing the target.
Echoes, other zones/presets, invalid values and bad optional checksums do not
count as a reading. A missing matching reply returns 504; serial contention
returns 429. Reads and writes are bounded and failed writes are not retried.
Preview mode returns no live volume and leaves the dial inactive; the original
IR volume buttons remain available to preview commands.

The UI polls `GET /api/status?zone=1`, which combines volume and the seven
current-input aliases in one request to the receiver. `ParameterAddress.get_many`
and `read_many` handle batched requests and replies split across serial frames.
The same serial transaction also sends `(00,G,R,13;checksum)` for Zone 1 power
or `(00,G,R,14;checksum)` for Zone 2. Power is confirmed only by a matching
realtime reply; silence does not imply Off. If a sleeping receiver replies only
with power Off, that state is retained even without preset data. Undocumented
zones have unknown power rather than a guessed identifier.
Partial replies retain valid readings and return null for missing fields with
`complete: false`. Preview mode returns no fabricated values. Polls and writes
share the frontend request coordination and the backend serial lock.

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
node --test src/volume.test.js src/parameter-display.test.js
```

Tests use a fake serial adapter and cover configuration, all IR API commands,
input validation, concurrent presses, disconnect/reconnect behavior, preview mode
and CLI compatibility. Volume tests cover Note 1 conversions, typed parameter
validation, reply filtering/checksums, atomic set/readback, timeouts and dial
rotation across the angle seam. Actual receiver behavior still needs hardware verification.

## License

[GNU GPL-3.0](LICENSE)

