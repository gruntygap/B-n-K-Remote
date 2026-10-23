"""Shared CLI/server settings. Environment variables override the project .env."""

from dataclasses import dataclass
import math
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    serial_port: str = "/dev/ttyUSB0"
    serial_baudrate: int = 9600
    serial_bytesize: int = 8
    serial_parity: str = "N"
    serial_stopbits: float = 1
    serial_timeout: float = 0.15
    serial_write_timeout: float = 1
    device_address: int = 0
    default_zone: int = 1
    remote_zones: tuple = (1, 2)
    web_host: str = "0.0.0.0"
    web_port: int = 8080
    dry_run: bool = False

    @classmethod
    def load(cls, env_file=ROOT / ".env"):
        load_dotenv(env_file, override=False)
        dry_run = os.getenv("DRY_RUN", "false").lower()
        if dry_run not in {"true", "false", "1", "0"}:
            raise ValueError("DRY_RUN must be true or false")
        settings = cls(
            serial_port=os.getenv("SERIAL_PORT", "/dev/ttyUSB0"),
            serial_baudrate=int(os.getenv("SERIAL_BAUDRATE", "9600")),
            serial_bytesize=int(os.getenv("SERIAL_BYTESIZE", "8")),
            serial_parity=os.getenv("SERIAL_PARITY", "N").upper(),
            serial_stopbits=float(os.getenv("SERIAL_STOPBITS", "1")),
            serial_timeout=float(os.getenv("SERIAL_TIMEOUT", "0.15")),
            serial_write_timeout=float(os.getenv("SERIAL_WRITE_TIMEOUT", "1")),
            device_address=int(os.getenv("DEVICE_ADDRESS", "0"), 0),
            default_zone=int(os.getenv("DEFAULT_ZONE", "1")),
            remote_zones=tuple(dict.fromkeys(int(z.strip()) for z in os.getenv("REMOTE_ZONES", "1,2").split(","))),
            web_host=os.getenv("WEB_HOST", "0.0.0.0"),
            web_port=int(os.getenv("WEB_PORT", "8080")),
            dry_run=dry_run in {"true", "1"},
        )
        settings.validate()
        return settings

    def validate(self):
        if not self.serial_port or self.serial_baudrate <= 0:
            raise ValueError("SERIAL_PORT and a positive SERIAL_BAUDRATE are required")
        if self.serial_bytesize not in {5, 6, 7, 8} or self.serial_parity not in {"N", "E", "O", "M", "S"}:
            raise ValueError("Invalid SERIAL_BYTESIZE or SERIAL_PARITY")
        if self.serial_stopbits not in {1, 1.5, 2}:
            raise ValueError("SERIAL_STOPBITS must be 1, 1.5 or 2")
        if any(not math.isfinite(t) or not 0 < t <= 5 for t in (self.serial_timeout, self.serial_write_timeout)):
            raise ValueError("Serial timeouts must be greater than 0 and at most 5 seconds")
        if not 0 <= self.device_address <= 255:
            raise ValueError("DEVICE_ADDRESS must be between 0 and 255")
        if not self.remote_zones or any(not 1 <= z <= 255 for z in self.remote_zones):
            raise ValueError("REMOTE_ZONES must contain zone numbers between 1 and 255")
        if self.default_zone not in self.remote_zones:
            raise ValueError("DEFAULT_ZONE must be included in REMOTE_ZONES")
        if not self.web_host or not 1 <= self.web_port <= 65535:
            raise ValueError("WEB_HOST and WEB_PORT (1-65535) are required")
