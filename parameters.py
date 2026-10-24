"""Typed BKC-DIP parameters, independent of serial transport and UI state.

Definitions describe wire values; readings retain both the raw value and its
meaning. Add model-specific definitions here rather than scattering conversions
through API handlers. Series I Appendix A, pp. 6-9 is the source below.
"""

from dataclasses import dataclass
import re
from typing import Literal

from control import build_bk_command


@dataclass(frozen=True)
class Parameter:
    name: str
    code: int
    description: str
    kind: Literal["integer", "text", "boolean", "enum", "bitmask"] = "integer"
    maximum: int = 255
    minimum: int = 0
    unit: str | None = None
    scale: float = 1
    offset: float = 0
    choices: tuple[tuple[int, str], ...] = ()
    special_values: tuple[tuple[int, str], ...] = ()
    note: str = ""

    def validate(self, raw):
        if self.kind == "text":
            # Quotes and packet delimiters are deliberately not allowed in the
            # Series I text format. Appendix H lists the accepted characters.
            if not isinstance(raw, str) or len(raw) > self.maximum or not re.fullmatch(r"[A-Za-z0-9 +/?='\-]*", raw):
                raise ValueError(f"{self.name} requires up to {self.maximum} display characters")
            return
        if type(raw) is not int or not self.minimum <= raw <= self.maximum:
            raise ValueError(f"{self.name} must be an integer from {self.minimum} to {self.maximum}")
        if self.kind == "boolean" and raw not in (0, 1):
            raise ValueError(f"{self.name} must be 0 or 1")
        if self.kind == "enum" and raw not in dict(self.choices):
            raise ValueError(f"Unknown {self.name} choice")

    def encode(self, raw):
        self.validate(raw)
        return f'"{raw}"' if self.kind == "text" else f"{raw:X}"

    def decode(self, token):
        if self.kind == "text":
            if len(token) < 2 or not token.startswith('"') or not token.endswith('"'):
                raise ValueError("Expected a quoted display string")
            raw = token[1:-1]
        else:
            if not re.fullmatch(r"[0-9a-fA-F]+", token):
                raise ValueError("Expected a hexadecimal value")
            raw = int(token, 16)
        return self.reading(raw)

    def reading(self, raw):
        self.validate(raw)
        special = dict(self.special_values).get(raw)
        if self.kind == "text":
            value = raw
        elif self.kind == "boolean":
            value = bool(raw)
        elif special is not None:
            value = None
        else:
            value = raw * self.scale + self.offset
        return {"raw": raw, "value": value, "unit": self.unit,
                "label": special or dict(self.choices).get(raw)}

    def metadata(self):
        return {"name": self.name, "code": f"{self.code:02X}",
                "description": self.description, "kind": self.kind,
                "minimum": self.minimum, "maximum": self.maximum,
                "unit": self.unit, "scale": self.scale, "offset": self.offset,
                "choices": dict(self.choices), "special_values": dict(self.special_values),
                "note": self.note}


# Common to both Series I preset zones. Model/zone-specific entries can use
# separate catalogs; the same identifier can have different meanings by zone.
PRESET_PARAMETERS = {
    "title": Parameter("title", 0, "Preset title", kind="text", maximum=0x0D),
    "volume": Parameter("volume", 1, "Volume", maximum=0x6F, unit="dB", offset=-96,
                        special_values=((0, "Mute"),), note="Appendix A, Note 1"),
    "balance": Parameter("balance", 2, "Balance", maximum=0x30,
                         note="Note 15: 18h is centered; each step attenuates one side by 0.5 dB"),
    "tuner_band": Parameter("tuner_band", 4, "Tuner band", kind="enum", maximum=1,
                            choices=((0, "AM"), (1, "FM")), note="Note 4"),
    "tuner_fm_mode": Parameter("tuner_fm_mode", 7, "FM stereo", kind="boolean", maximum=1,
                               choices=((0, "Mono"), (1, "Stereo")), note="Note 7"),
}
VOLUME = PRESET_PARAMETERS["volume"]

# Appendix A, current input aliases (Note 13): these apply to Zone 1 only.
# Note 9 gives two different meanings for command 2 depending on model; keep
# both rather than silently identifying an unconfigured model.
CURRENT_INPUT_PARAMETERS = {
    "surround_mode": Parameter("surround_mode", 0xF3, "Surround mode", kind="enum", maximum=6,
        choices=((0, "Surround"), (1, "3 Hall"), (2, "Stereo 3"), (3, "Stereo Hall"),
                 (4, "Stereo Front/Rear"), (5, "Stereo"), (6, "Stereo Lt/Rt")), note="Note 8"),
    "surround_command": Parameter("surround_command", 0xF4, "Surround command", kind="enum", maximum=3,
        choices=((0, "Auto"), (1, "Lock Analog"), (2, "Lock DTS / AC3 compression"), (3, "AC3 compression")),
        note="Note 9: command 2 is Lock DTS on REF20/AVR202, AC3 compression on REF10/AVR101"),
    "center_level": Parameter("center_level", 0xF5, "Center level", maximum=0x30,
        unit="dB", scale=0.5, offset=-12, note="Note 2"),
    "center_delay": Parameter("center_delay", 0xF6, "Center delay", maximum=5, unit="ms", note="Note 10"),
    "rear_level": Parameter("rear_level", 0xF7, "Rear level", maximum=0x30,
        unit="dB", scale=0.5, offset=-12, note="Note 2"),
    "rear_delay": Parameter("rear_delay", 0xF8, "Rear delay", maximum=0x0F, unit="ms",
        note="Note 11: raw 0-F is 0-15 ms outside Pro Logic; the manual specifies 16-30 ms in Pro Logic without an exact mapping"),
    "sub_level": Parameter("sub_level", 0xF9, "Sub level", maximum=0x30,
        unit="dB", scale=0.5, offset=-12, note="Note 2"),
}


@dataclass(frozen=True)
class ParameterAddress:
    """A value's identity includes its block, zone and preset, not just its ID.

    Preset FF is the live working preset, never a stored preset to recall/save.
    Other blocks can represent system (S), realtime (R) or unit (F4) parameters.
    """
    block: Literal["preset", "system", "realtime", "unit"] = "preset"
    zone: int | None = 1
    preset: int = 0xFF

    def selector(self):
        if self.block != "preset":
            if self.zone is not None:
                raise ValueError("Only preset parameters have a zone selector")
            return {"system": "S", "realtime": "R", "unit": "F4"}[self.block]
        if type(self.zone) is not int or not 1 <= self.zone <= 255:
            raise ValueError("Choose a valid zone")
        if type(self.preset) is not int or not (0 <= self.preset <= 0xFD or self.preset == 0xFF):
            raise ValueError("Preset FE is reserved")
        return f"P{self.zone:X}={self.preset:X}"

    def get(self, parameter: Parameter, address=0):
        return self.get_many((parameter,), address)

    def get_many(self, parameters, address=0):
        identifiers = ",".join(f"{parameter.code:X}" for parameter in parameters)
        if not identifiers:
            raise ValueError("Choose at least one parameter")
        return build_bk_command(f"{address:02X},G,{self.selector()},{identifiers}")

    def read_many(self, parameters, response):
        # A receiver may return all parameters in one frame or split replies
        # across multiple frames. Never stop on an echo or a partial batch.
        return {parameter.name: self.read(parameter, response) for parameter in parameters}

    def set(self, parameter: Parameter, raw, address=0):
        if self.block in {"realtime", "unit"}:
            raise ValueError("This parameter block is read-only")
        return build_bk_command(f"{address:02X},S,{self.selector()},{parameter.code:X}={parameter.encode(raw)}")

    def read(self, parameter: Parameter, response):
        """Accept R replies, not echoed G/S packets or another zone/preset.

        Receive and transmit IDs are independent in BKC-DIP; a dedicated serial
        receiver is assumed. Verify optional checksums before using state.
        """
        for match in re.finditer(rb"\(([^()]*)\)", response):
            try:
                body, checksum = match[1].decode("ascii").rsplit(";", 1)
                if checksum.strip() and (not re.fullmatch(r"[0-9A-Fa-f]{4}", checksum.strip())
                                         or int(checksum, 16) != sum((body + ";").encode("ascii"))):
                    continue
                parts = [part.strip() for part in body.split(",")]
                if len(parts) < 4 or parts[1].upper() != "R":
                    continue
                parts = parts[2:]
                if parts[0].upper() == "G":  # Some V2 replies include the originating command.
                    parts = parts[1:]
                selector = re.fullmatch(r"P([0-9A-F]+)=([0-9A-F]+)", parts[0].upper())
                if self.block == "preset":
                    matches = selector and (int(selector[1], 16), int(selector[2], 16)) == (self.zone, self.preset)
                else:
                    matches = parts[0].upper() == self.selector()
                if not matches:
                    continue
                for item in parts[1:]:
                    value = re.fullmatch(r"([0-9a-fA-F]+)=(.*)", item)
                    if value and int(value[1], 16) == parameter.code:
                        return parameter.decode(value[2].strip())
            except (UnicodeError, ValueError, IndexError):
                continue
        return None

    def read_volume(self, response):
        return self.read(VOLUME, response)
