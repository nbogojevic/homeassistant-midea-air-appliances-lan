"""Adds dehumidifer entity for each dehumidifer appliance."""

from datetime import datetime
import logging
from typing import Any, Final

from homeassistant.components.humidifier import HumidifierDeviceClass, HumidifierEntity
from homeassistant.components.humidifier.const import SUPPORT_MODES
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_lan.const import (
    ATTR_RUNNING,
    DOMAIN,
    MAX_TARGET_HUMIDITY,
    MIN_TARGET_HUMIDITY,
    NAME,
)
from custom_components.midea_dehumidifier_lan.appliance_coordinator import (
    ApplianceEntity,
    ApplianceUpdateCoordinator,
)
from custom_components.midea_dehumidifier_lan.hub import Hub

_LOGGER = logging.getLogger(__name__)

MODE_SET: Final = "Set"
MODE_DRY: Final = "Dry"
MODE_SMART: Final = "Smart"
MODE_CONTINOUS: Final = "Continuous"
MODE_PURIFIER: Final = "Purifier"
MODE_ANTIMOULD: Final = "Antimould"
MODE_FAN: Final = "Fan"

ENTITY_ID_FORMAT = DOMAIN + ".{}"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up dehumidifier entites"""
    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        DehumidifierEntity(c) for c in hub.coordinators if c.is_dehumidifier()
    )


_MODES = [
    (1, MODE_SET),
    (2, MODE_CONTINOUS),
    (3, MODE_SMART),
    (4, MODE_DRY),
    (6, MODE_PURIFIER),
    (7, MODE_ANTIMOULD),
]


# pylint: disable=too-many-ancestors,too-many-instance-attributes
class DehumidifierEntity(ApplianceEntity, HumidifierEntity):
    """(de)Humidifer entity for Midea dehumidifier"""

    _attr_device_class = HumidifierDeviceClass.DEHUMIDIFIER
    _attr_max_humidity = MAX_TARGET_HUMIDITY
    _attr_min_humidity = MIN_TARGET_HUMIDITY
    _attr_supported_features = SUPPORT_MODES
    _name_suffix = ""

    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)

        self._attr_mode = None
        self._error_code = None
        self._last_error_code = None
        self._last_error_code_time = datetime.now()
        self._capabilities = None
        self._last_data = None
        self._capabilities_data = None
        self._attr_available_modes = [MODE_SET]

    def on_online(self, update: bool) -> None:
        supports = self.coordinator.appliance.state.capabilities

        self._attr_available_modes = [MODE_SET]
        if supports.get("auto"):
            self._attr_available_modes.append(MODE_SMART)
        self._attr_available_modes.append(MODE_CONTINOUS)
        if supports.get("dry_clothes"):
            self._attr_available_modes.append(MODE_DRY)

        more_modes = supports.get("mode")
        if more_modes == 1:
            self._attr_available_modes.append(MODE_PURIFIER)
        elif more_modes == 2:
            self._attr_available_modes.append(MODE_ANTIMOULD)
        elif more_modes == 3:
            self._attr_available_modes.append(MODE_PURIFIER)
            self._attr_available_modes.append(MODE_ANTIMOULD)
        elif more_modes == 4:
            self._attr_available_modes.append(MODE_FAN)

        super().on_online(update)

    def on_update(self) -> None:
        """Allows additional processing after the coordinator updates data"""
        dehumidifier = self.dehumidifier()
        curr_mode = dehumidifier.mode
        self._attr_mode = next((i[1] for i in _MODES if i[0] == curr_mode), None)
        if self._attr_mode is None:
            self._attr_mode = MODE_SET
            _LOGGER.warning("Mode %s is not supported by %s.", curr_mode, NAME)
        self._attr_target_humidity = dehumidifier.target_humidity
        self._attr_is_on = dehumidifier.running
        self._error_code = dehumidifier.error_code
        if self._error_code:
            self._last_error_code = self._error_code
            self._last_error_code_time = datetime.now()
        self._capabilities = self.appliance.state.capabilities
        self._last_data = self.appliance.state.latest_data.hex()
        self._capabilities_data = str(self.appliance.state.capabilities_data.hex())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        data = {
            "capabilities": self._capabilities,
            "last_data": self._last_data,
            "capabilities_data": self._capabilities_data,
            "error_code": self._error_code,
            "last_error_code": self._last_error_code,
            "last_error_time": self._last_error_code_time,
        }

        return data

    def turn_on(self, **kwargs) -> None:  # pylint: disable=unused-argument
        """Turn the entity on."""
        self.apply(ATTR_RUNNING, True)

    def turn_off(self, **kwargs) -> None:  # pylint: disable=unused-argument
        """Turn the entity off."""
        self.apply(ATTR_RUNNING, False)

    def set_mode(self, mode) -> None:
        """Set new target preset mode."""
        midea_mode = next((i[0] for i in _MODES if i[1] == mode), None)
        if midea_mode is None:
            _LOGGER.debug("Unsupported dehumidifer mode %s", mode)
            midea_mode = 1
        self.apply("mode", midea_mode)

    def set_humidity(self, humidity) -> None:
        """Set new target humidity."""
        self.apply("target_humidity", humidity)
