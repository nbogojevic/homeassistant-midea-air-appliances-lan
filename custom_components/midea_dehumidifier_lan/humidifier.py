"""Adds dehumidifer entity for each dehumidifer appliance."""

import logging
from typing import Final

from homeassistant.components.humidifier import HumidifierDeviceClass, HumidifierEntity
from homeassistant.components.humidifier.const import (
    SUPPORT_MODES,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_lan import ApplianceEntity, Hub
from custom_components.midea_dehumidifier_lan.const import (
    DOMAIN,
    MAX_TARGET_HUMIDITY,
    MIN_TARGET_HUMIDITY,
)


_LOGGER = logging.getLogger(__name__)

MODE_SET: Final = "Set"
MODE_DRY: Final = "Dry"
MODE_SMART: Final = "Smart"
MODE_CONTINOUS: Final = "Continuous"

AVAILABLE_MODES: Final = [MODE_SMART, MODE_SET, MODE_DRY, MODE_CONTINOUS]


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

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return ""

    @property
    def is_on(self) -> bool:
        return getattr(self.appliance.state, "running", False)

    @property
    def device_class(self) -> str:
        return HumidifierDeviceClass.DEHUMIDIFIER

    @property
    def target_humidity(self) -> int:
        return int(getattr(self.appliance.state, "target_humidity", 0))

    @property
    def supported_features(self) -> int:
        return SUPPORT_MODES

    @property
    def available_modes(self) -> list[str]:
        return AVAILABLE_MODES

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
        _LOGGER.warning("Unknown mode %d", curr_mode)
        return MODE_SET

    @property
    def min_humidity(self) -> int:
        """Return the min humidity that can be set."""
        return MIN_TARGET_HUMIDITY

    @property
    def max_humidity(self) -> int:
        """Return the max humidity that can be set."""
        return MAX_TARGET_HUMIDITY

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        self.apply("running", True)

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self.apply("running", False)

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
        else:
            _LOGGER.warning("Unsupported dehumidifer mode %s", mode)
            curr_mode = 1
        self.apply("mode", curr_mode)

    def set_humidity(self, humidity) -> None:
        """Set new target humidity."""
        self.apply("target_humidity", humidity)
