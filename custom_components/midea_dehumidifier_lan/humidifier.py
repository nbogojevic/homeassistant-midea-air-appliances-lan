"""Adds dehumidifer entity for each dehumidifer appliance."""

from datetime import datetime
import logging
from typing import Final

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
)
from custom_components.midea_dehumidifier_lan.hub import (
    ApplianceEntity,
    ApplianceUpdateCoordinator,
    Hub,
)

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


# pylint: disable=too-many-ancestors
class DehumidifierEntity(ApplianceEntity, HumidifierEntity):
    """(de)Humidifer entity for Midea dehumidifier"""

    _attr_device_class = HumidifierDeviceClass.DEHUMIDIFIER
    _attr_max_humidity = MAX_TARGET_HUMIDITY
    _attr_min_humidity = MIN_TARGET_HUMIDITY
    _attr_supported_features = SUPPORT_MODES
    _name_suffix = ""

    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)
        supports = coordinator.appliance.state.capabilities

        self._last_error_code = 0
        self._last_error_code_time = datetime.now()
        self._attr_available_modes = [MODE_SET]
        if supports.get("auto", 0):
            self._attr_available_modes.append(MODE_SMART)
        self._attr_available_modes.append(MODE_CONTINOUS)
        if supports.get("dry_clothes", 0):
            self._attr_available_modes.append(MODE_DRY)

        more_modes = supports.get("mode", "0")
        if more_modes == 1:
            self._attr_available_modes.append(MODE_PURIFIER)
        elif more_modes == 2:
            self._attr_available_modes.append(MODE_ANTIMOULD)
        elif more_modes == 3:
            self._attr_available_modes.append(MODE_PURIFIER)
            self._attr_available_modes.append(MODE_ANTIMOULD)
        elif more_modes == 4:
            self._attr_available_modes.append(MODE_FAN)

    @property
    def is_on(self) -> bool:
        return self.dehumidifier().running

    @property
    def target_humidity(self) -> int:
        return self.dehumidifier().target_humidity

    _MODES = [
        (1, MODE_SET),
        (2, MODE_CONTINOUS),
        (3, MODE_SMART),
        (4, MODE_DRY),
        (6, MODE_PURIFIER),
        (7, MODE_ANTIMOULD),
    ]

    @property
    def mode(self):
        curr_mode = self.dehumidifier().mode
        mode = next((i[1] for i in self._MODES if i[0] == curr_mode), None)
        if mode is None:
            _LOGGER.warning("Unknown mode %d", curr_mode)
            return MODE_SET
        return mode

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        new_error_code = self.dehumidifier().error_code
        if new_error_code:
            self._last_error_code = new_error_code
            self._last_error_code_time = datetime.now()
        data = {
            "capabilities": str(self.appliance.state.capabilities),
            "last_data": self.appliance.state.latest_data.hex(),
            "capabilities_data": str(self.appliance.state.capabilities_data.hex()),
            "error_code": new_error_code,
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
        midea_mode = next((i[0] for i in self._MODES if i[1] == mode), None)
        if midea_mode is None:
            _LOGGER.warning("Unsupported dehumidifer mode %s", mode)
            midea_mode = 1
        self.apply("mode", midea_mode)

    def set_humidity(self, humidity) -> None:
        """Set new target humidity."""
        self.apply("target_humidity", humidity)
