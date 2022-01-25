"""Utilities for Midea Air Appliances integration"""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Tuple, cast, final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
    CONF_ID,
    CONF_INCLUDE,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
import midea_beautiful as midea_beautiful_api
from midea_beautiful.appliance import AirConditionerAppliance, DehumidifierAppliance
from midea_beautiful.cloud import MideaCloud
from midea_beautiful.lan import LanDevice
from midea_beautiful.midea import (
    APPLIANCE_TYPE_AIRCON,
    APPLIANCE_TYPE_DEHUMIDIFIER,
    DEFAULT_APP_ID,
    DEFAULT_APPKEY,
)

from custom_components.midea_dehumidifier_lan.const import (
    _ALWAYS_CREATE,
    CONF_TOKEN_KEY,
    UNKNOWN_IP,
)

_SUPPORTABLE_APPLIANCES = {
    APPLIANCE_TYPE_AIRCON: AirConditionerAppliance.supported,
    APPLIANCE_TYPE_DEHUMIDIFIER: DehumidifierAppliance.supported,
}


def _redact(data: dict[str, Any], key: str, char="*", length: int = 0) -> None:
    """Redacts/obfuscates key in disctionary"""
    if data.get(key) is not None:
        to_redact = str(data[key])
        if length <= 0 or length >= len(to_redact):
            data[key] = char * len(to_redact)
        else:
            data[key] = to_redact[:-length] + char * length


def _redact_device_conf(device) -> None:
    _redact(device, CONF_TOKEN)
    _redact(device, CONF_TOKEN_KEY)
    _redact(device, CONF_UNIQUE_ID, length=8)
    _redact(device, CONF_ID, length=4)


class RedactedConf:
    """Outputs redacted configuration dictionary by removing or masking
    confidential data."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Remove sensitive information from configuration"""
        self.conf = data

    @property
    def __dict__(self) -> dict[str, Any]:
        conf = deepcopy(self.conf)
        _redact(conf, CONF_USERNAME)
        _redact(conf, CONF_PASSWORD)
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


def is_climate(appliance: LanDevice) -> bool:
    """True if appliance is air conditioner"""
    return AirConditionerAppliance.supported(appliance.type)


def is_dehumidifier(appliance: LanDevice) -> bool:
    """True if appliance is dehumidifier"""
    return DehumidifierAppliance.supported(appliance.type)


def supported_appliance(conf: dict, appliance: LanDevice) -> bool:
    """Checks if appliance is supported by integration"""
    included = conf.get(CONF_INCLUDE, [])
    for type_id, check in _SUPPORTABLE_APPLIANCES.items():
        if type_id in included and check(appliance.type):
            return True
    return False


class ApplianceCoordinator(ABC):  # pylint: disable=too-few-public-methods
    """Abstract interface for Appliance update coordinators"""

    appliance: LanDevice
    available: bool
    device: dict[str, Any]

    def is_climate(self) -> bool:
        """True if appliance is air conditioner"""
        return is_climate(self.appliance)

    def is_dehumidifier(self) -> bool:
        """True if appliance is dehumidifier"""
        return is_dehumidifier(self.appliance)

    @final
    def dehumidifier(self) -> DehumidifierAppliance:
        """Returns state as dehumidifier"""
        return cast(DehumidifierAppliance, self.appliance.state)

    @final
    def airconditioner(self) -> AirConditionerAppliance:
        """Returns state as air conditioner"""
        return cast(AirConditionerAppliance, self.appliance.state)


class AbstractHub(ABC):
    """Interface for central class for interacting with appliances"""

    coordinators: list[ApplianceCoordinator]
    config: dict[str, Any]
    errors: dict[str, Any]

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.client = MideaClient()
        self.cloud: MideaCloud | None = None
        self.hass = hass
        self.config_entry = config_entry

    @abstractmethod
    async def async_discover_device(
        self, device: dict[str, Any], initial_discovery=False
    ) -> Tuple[bool, LanDevice | None]:
        """Finds device on local network or cloud"""
        return False, None

    @abstractmethod
    async def async_update_config(self) -> None:
        """Updates config entry from Hub's data"""


class MideaClient:
    """Delegate to midea API"""

    def connect_to_cloud(  # pylint: disable=no-self-use
        self, account: str, password: str, appkey=DEFAULT_APPKEY, appid=DEFAULT_APP_ID
    ):
        """Delegate to midea_beautiful_api.connect_to_cloud"""
        return midea_beautiful_api.connect_to_cloud(
            account=account, password=password, appkey=appkey, appid=appid
        )

    def appliance_state(  # pylint: disable=too-many-arguments,no-self-use
        self,
        address: str = None,
        token: str = None,
        key: str = None,
        cloud: MideaCloud = None,
        use_cloud: bool = False,
        appliance_id: str = None,
    ):
        """Delegate to midea_beautiful_api.appliance_state"""
        return midea_beautiful_api.appliance_state(
            address=address,
            token=token,
            key=key,
            cloud=cloud,
            use_cloud=use_cloud,
            appliance_id=appliance_id,
            retries=5,
            cloud_timeout=6,
        )

    def find_appliances(  # pylint: disable=too-many-arguments,no-self-use
        self,
        cloud: MideaCloud = None,
        appkey: str = None,
        account: str = None,
        password: str = None,
        appid: str = None,
        addresses: list[str] = None,
        retries: int = 3,
        timeout: int = 3,
    ) -> list[LanDevice]:
        """Delegate to midea_beautiful_api.find_appliances"""
        return midea_beautiful_api.find_appliances(
            cloud=cloud,
            appkey=appkey,
            account=account,
            password=password,
            appid=appid,
            addresses=addresses,
            retries=retries,
            timeout=timeout,
        )


def address_ok(address: str | None) -> bool:
    """Returns True if address is not known"""
    return address is not None and address != UNKNOWN_IP
