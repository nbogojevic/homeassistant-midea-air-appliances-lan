"""Utilities for Midea Air Appliances integration"""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Tuple

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
    CONF_ID,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from midea_beautiful.cloud import MideaCloud
from midea_beautiful.lan import LanDevice

from custom_components.midea_dehumidifier_lan.api import MideaClient
from custom_components.midea_dehumidifier_lan.const import (
    _ALWAYS_CREATE,
    CONF_TOKEN_KEY,
)


def _redact_key(
    redacted_data: dict[str, Any], key: str, char="*", length: int = 0
) -> None:
    if redacted_data.get(key) is not None:
        to_redact = str(redacted_data[key])
        if length <= 0 or length >= len(to_redact):
            redacted_data[key] = char * len(to_redact)
        else:
            redacted_data[key] = to_redact[:-length] + char * length


def _redact_device_conf(device) -> None:
    _redact_key(device, CONF_TOKEN)
    _redact_key(device, CONF_TOKEN_KEY)
    _redact_key(device, CONF_UNIQUE_ID, length=8)
    _redact_key(device, CONF_ID, length=4)


class RedactedConf:
    """Outputs redacted configuration dictionary by removing or masking
    confidential data."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Remove sensitive information from configuration"""
        self.conf = data

    @property
    def __dict__(self) -> dict[str, Any]:
        conf = deepcopy(self.conf)
        _redact_key(conf, CONF_USERNAME)
        _redact_key(conf, CONF_PASSWORD)
        _redact_device_conf(conf)
        if conf.get(CONF_DEVICES) and isinstance(conf.get(CONF_DEVICES), list):
            for device in conf[CONF_DEVICES]:
                if device and isinstance(device, dict):
                    _redact_device_conf(device)
        return conf

    def __str__(self) -> str:
        """Remove sensitive information from configuration"""

        return str(self.__dict__)


def is_enabled_by_capabilities(capabilities: dict[str, Any], capability: str) -> bool:
    """Returns True if given capability is enabled"""
    if capability in _ALWAYS_CREATE:
        return True
    if not capabilities or capabilities.get(capability, False):
        return True
    return False


class AbstractHub(ABC):
    """Interface for central class for interacting with appliances"""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.client = MideaClient()
        self.cloud: MideaCloud | None = None
        self.config_entry = config_entry
        self.config: dict[str, Any] = {}
        self.errors: dict[str, Any] = {}
        self.hass = hass

    @abstractmethod
    async def async_discover_device(
        self, device: dict[str, Any], initial_discovery=False
    ) -> Tuple[bool, LanDevice | None]:
        """Finds device on local network or cloud"""
        return False, None

    @abstractmethod
    async def async_update_config(self) -> None:
        """Updates config entry from Hub's data"""
