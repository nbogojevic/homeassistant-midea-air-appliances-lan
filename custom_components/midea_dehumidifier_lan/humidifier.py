"""Adds dehumidifer entity for each dehumidifer appliance."""

import logging
from typing import Final

from homeassistant.components.humidifier import HumidifierDeviceClass, HumidifierEntity
from homeassistant.components.humidifier.const import SUPPORT_MODES
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_lan import (
    ApplianceEntity,
    ApplianceUpdateCoordinator,
    Hub,
)
from custom_components.midea_dehumidifier_lan.const import (
    ATTR_RUNNING,
    DOMAIN,
    MAX_TARGET_HUMIDITY,
    MIN_TARGET_HUMIDITY,
)

_LOGGER = logging.getLogger(__name__)

MODE_SET: Final = "Set"
MODE_DRY: Final = "Dry"
MODE_SMART: Final = "Smart"
MODE_CONTINOUS: Final = "Continuous"
MODE_PURIFIER: Final = "Purifier"
MODE_ANTIMOULD: Final = "Antimould"
MODE_FAN: Final = "Fan"


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


class DehumidifierEntity(ApplianceEntity, HumidifierEntity):
    """(de)Humidifer entity for Midea appliances """

    _attr_device_class = HumidifierDeviceClass.DEHUMIDIFIER
    _attr_max_humidity = MAX_TARGET_HUMIDITY
    _attr_min_humidity = MIN_TARGET_HUMIDITY
    _attr_supported_features = SUPPORT_MODES
    _name_suffix = ""

    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)
        supports = getattr(coordinator.appliance.state, "supports", {})

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
        return getattr(self.appliance.state, ATTR_RUNNING, False)

    @property
    def target_humidity(self) -> int:
        return int(getattr(self.appliance.state, "target_humidity", 0))

    @property
    def mode(self):
        curr_mode = getattr(self.appliance.state, "mode", 1)
        if curr_mode == 1:
            return MODE_SET
        if curr_mode == 2:
            return MODE_CONTINOUS
        if curr_mode == 3:
            return MODE_SMART
        if curr_mode == 4:
            return MODE_DRY
        if curr_mode == 6:
            return MODE_PURIFIER
        if curr_mode == 7:
            return MODE_ANTIMOULD
        _LOGGER.warning("Unknown mode %d", curr_mode)
        return MODE_SET

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        self.apply(ATTR_RUNNING, True)

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self.apply(ATTR_RUNNING, False)

    def set_mode(self, mode) -> None:
        """Set new target preset mode."""
        if mode == MODE_SET:
            curr_mode = 1
        elif mode == MODE_CONTINOUS:
            curr_mode = 2
        elif mode == MODE_SMART:
            curr_mode = 3
        elif mode == MODE_DRY:
            curr_mode = 4
        elif mode == MODE_PURIFIER:
            curr_mode = 6
        elif mode == MODE_ANTIMOULD:
            curr_mode = 7
        else:
            _LOGGER.warning("Unsupported dehumidifer mode %s", mode)
            curr_mode = 1
        self.apply("mode", curr_mode)

    def set_humidity(self, humidity) -> None:
        """Set new target humidity."""
        self.apply("target_humidity", humidity)
