"""
The custom component for local network access to Midea appliances
"""

from __future__ import annotations

import logging
from typing import Any, Tuple

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_DEVICES,
    CONF_DISCOVERY,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_TYPE,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from midea_beautiful.exceptions import AuthenticationError
from midea_beautiful.lan import LanDevice

from custom_components.midea_dehumidifier_lan.appliance_coordinator import (
    ApplianceUpdateCoordinator,
)
from custom_components.midea_dehumidifier_lan.appliance_discovery import (
    ApplianceDiscoveryHelper,
)
from custom_components.midea_dehumidifier_lan.const import (
    CONF_APPID,
    CONF_APPKEY,
    CONF_TOKEN_KEY,
    DISCOVERY_CLOUD,
    DISCOVERY_IGNORE,
    DISCOVERY_LAN,
    DISCOVERY_WAIT,
    NAME,
    UNKNOWN_IP,
)
from custom_components.midea_dehumidifier_lan.util import AbstractHub, redacted_conf

_LOGGER = logging.getLogger(__name__)


def _assure_valid_device_configuration(
    conf: dict[str, Any], device: dict[str, Any]
) -> bool:
    """Checks device configuration.
    If configuration is correct returns ``True``.
    If it is not complete, updates it and returns ``False``.
    For example, if discovery mode is not set-up corectly it will try to deduce
    correct setting."""
    discovery_mode = device.get(CONF_DISCOVERY)
    _LOGGER.debug(
        "Device %s %s has discovery mode %s",
        device.get(CONF_NAME),
        device.get(CONF_UNIQUE_ID),
        discovery_mode,
    )
    if discovery_mode in [
        DISCOVERY_IGNORE,
        DISCOVERY_WAIT,
        DISCOVERY_LAN,
        DISCOVERY_CLOUD,
    ]:
        return True
    ip_address = device.get(CONF_IP_ADDRESS)
    token = device.get(CONF_TOKEN)
    key = device.get(CONF_TOKEN_KEY)
    if ip_address and ip_address != UNKNOWN_IP:
        device[CONF_DISCOVERY] = DISCOVERY_LAN if token and key else DISCOVERY_WAIT
    elif token and key:
        device[CONF_DISCOVERY] = DISCOVERY_WAIT
    else:
        username = conf.get(CONF_USERNAME)
        password = conf.get(CONF_PASSWORD)
        device[CONF_DISCOVERY] = (
            DISCOVERY_CLOUD if username and password else DISCOVERY_IGNORE
        )
    _LOGGER.warning(
        "Updated discovery mode for device %s.",
        redacted_conf(device),
    )
    return False


def _get_placeholder_appliance(device: dict[str, Any]) -> LanDevice:
    appliance = LanDevice(
        appliance_id=device[CONF_ID],
        serial_number=device[CONF_UNIQUE_ID],
        appliance_type=device[CONF_TYPE],
        token=device.get(CONF_TOKEN),
        key=device.get(CONF_TOKEN_KEY) or "",
        address=device.get(CONF_IP_ADDRESS, UNKNOWN_IP),
        version=device.get(CONF_API_VERSION, 3),
    )
    appliance.name = device[CONF_NAME]
    return appliance


class Hub(AbstractHub):  # pylint: disable=too-many-instance-attributes
    """Central class for interacting with appliances"""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(hass, config_entry)
        self.discovery = ApplianceDiscoveryHelper(hass, config_entry, self.client)
        self.coordinators: list[ApplianceUpdateCoordinator] = []
        self.updated_conf = False

    async def async_unload(self) -> None:
        """Stops discovery and coordinators"""
        _LOGGER.debug("Unloading hub")

        for coordinator in self.coordinators:
            # Stop coordinators
            coordinator.update_interval = None

    async def async_update_config(self) -> None:
        """Updates config entry from Hub's data"""
        self.hass.config_entries.async_update_entry(self.config_entry, data=self.config)

    async def async_setup(self) -> None:
        """Sets up appliances and creates an update coordinator for
        each one
        """
        self.config = {**self.config_entry.data}
        devices = [{**device} for device in self.config.get(CONF_DEVICES, [])]
        self.config[CONF_DEVICES] = devices
        self.errors = {}
        self.updated_conf = False

        devices = []
        for device in self.config[CONF_DEVICES]:
            if not _assure_valid_device_configuration(self.config, device):
                self.updated_conf = True
            coordinator = await self._process_appliance(device)
            if coordinator and not coordinator.not_detected:
                await coordinator.async_config_entry_first_refresh()
            devices.append(device)

        if self.updated_conf:
            await self.async_update_config()

        self.discovery.start(self.config, self.coordinators)

        self._notify_setup_errors()

    def _notify_setup_errors(self):
        if self.errors:
            if not self.coordinators:
                raise ConfigEntryNotReady(str(self.errors))
            for unique_id, error in self.errors.items():
                self.hass.components.persistent_notification.async_create(
                    title=NAME,
                    message=(
                        f"{error}.\n\n"
                        f"Device may be offline or unreachable, trying again later."
                    ),
                    notification_id=f"midea_error_{unique_id}",
                )

    async def _process_appliance(
        self, device: dict[str, Any]
    ) -> ApplianceUpdateCoordinator | None:
        discovery_mode = device.get(CONF_DISCOVERY)
        # We are waiting for appliance to come online
        if discovery_mode == DISCOVERY_IGNORE:
            _LOGGER.debug("Ignored appliance for discovery %s", device)
            return None
        if discovery_mode == DISCOVERY_WAIT:
            _LOGGER.debug("Waiting for appliance discovery %s", device)
            return None
        need_token, appliance = await self.async_discover_device(
            device, initial_discovery=True
        )
        return self._create_coordinator(appliance, device, need_token)

    async def async_discover_device(
        self, device: dict[str, Any], initial_discovery=False
    ) -> Tuple[bool, LanDevice | None]:
        """Finds device on local network or cloud"""
        discovery_mode = device.get(CONF_DISCOVERY)

        use_cloud = discovery_mode == DISCOVERY_CLOUD
        need_cloud = use_cloud
        lan_mode = discovery_mode == DISCOVERY_LAN
        version = device.get(CONF_API_VERSION, 3)
        need_token = (
            discovery_mode == DISCOVERY_LAN
            and version >= 3
            and (not device.get(CONF_TOKEN) or not device.get(CONF_TOKEN_KEY))
        )
        if need_token:
            _LOGGER.debug(
                "Appliance %s %s has no token,"
                " trying to obtain it from Midea cloud API",
                device.get(CONF_NAME),
                device.get(CONF_UNIQUE_ID),
            )
            need_cloud = True
        if not await self._async_get_cloud_if_needed(device, need_cloud, need_token):
            return need_token, None
        ip_address = device[CONF_IP_ADDRESS] if lan_mode else None
        if not ip_address and not use_cloud:
            _LOGGER.error(
                "Missing ip_address and cloud discovery is not used for %s."
                "Will fall-back to cloud discovery, full configuration is %s",
                device.get(CONF_UNIQUE_ID),
                redacted_conf(self.config),
            )
            use_cloud = True
        appliance = None
        try:
            appliance = await self.hass.async_add_executor_job(
                self.client.appliance_state,
                device[CONF_IP_ADDRESS] if lan_mode else None,
                device.get(CONF_TOKEN),
                device.get(CONF_TOKEN_KEY),
                self.cloud,
                use_cloud,
                device[CONF_ID],
            )

        except Exception as ex:  # pylint: disable=broad-except
            self.errors[
                device[CONF_UNIQUE_ID]
            ] = f"Unable to get state of device {device[CONF_NAME]}: {ex}"
            if initial_discovery:
                _LOGGER.error(
                    "Error '%s' while setting up appliance %s,"
                    " full configuration %s",
                    ex,
                    device.get(CONF_UNIQUE_ID),
                    redacted_conf(self.config),
                    exc_info=True,
                )
            else:
                _LOGGER.debug(
                    "Error '%s' while setting up appliance %s",
                    ex,
                    redacted_conf(device),
                )
        return need_token, appliance

    async def _async_get_cloud_if_needed(
        self, device: dict[str, Any], need_cloud: bool, need_token: bool
    ) -> bool:
        if need_cloud and self.cloud is None:
            self._validate_auth_config_complete(device, need_token)
            try:
                self.cloud = await self.hass.async_add_executor_job(
                    self.client.connect_to_cloud,
                    self.config[CONF_USERNAME],
                    self.config[CONF_PASSWORD],
                    self.config[CONF_APPKEY],
                    self.config[CONF_APPID],
                )
            except AuthenticationError as ex:
                raise ConfigEntryAuthFailed(
                    f"Unable to login to Midea cloud {ex}"
                ) from ex
            except Exception as ex:  # pylint: disable=broad-except
                self.errors[device[CONF_UNIQUE_ID]] = str(ex)
                return False
        return True

    def _validate_auth_config_complete(self, device, need_token):
        if not self.config.get(CONF_USERNAME) or not self.config.get(CONF_PASSWORD):
            if not device:
                cause = ""
            elif need_token:
                cause = f" because {device.get(CONF_NAME)} is missing token,"
            else:
                cause = f" because {device.get(CONF_NAME)} uses cloud polling,"
            raise ConfigEntryAuthFailed(
                f"Integration needs to connect to Midea cloud,"
                f"{cause}"
                f" but username or password are not configured."
            )

    def _create_coordinator(
        self, appliance: LanDevice | None, device: dict[str, Any], need_token: bool
    ) -> ApplianceUpdateCoordinator:
        not_detected = appliance is None
        if not_detected:
            appliance = _get_placeholder_appliance(device)
        appliance.name = device[CONF_NAME]
        self._fix_version_if_missing(appliance, device)
        self._update_token(appliance, device, need_token)
        coordinator = ApplianceUpdateCoordinator(
            self.hass, self, appliance, device, not_detected=not_detected
        )

        _LOGGER.debug("Created coordinator for %s", device)
        self.coordinators.append(coordinator)
        return coordinator

    def _update_token(
        self, appliance: LanDevice, device: dict[str, Any], need_token: bool
    ) -> None:
        if need_token and appliance.token and appliance.key:
            device[CONF_TOKEN] = appliance.token
            device[CONF_TOKEN_KEY] = appliance.key
            self.updated_conf = True
            _LOGGER.debug("Updating token for %s", appliance)

    def _fix_version_if_missing(
        self, appliance: LanDevice, device: dict[str, Any]
    ) -> None:
        if not device.get(CONF_API_VERSION):
            device[CONF_API_VERSION] = appliance.version
            self.updated_conf = True
            _LOGGER.debug("Updating version for %s", appliance)
