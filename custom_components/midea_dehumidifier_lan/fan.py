"""Adds fan entity for each dehumidifer appliance."""

import logging
from typing import Any, Final

from homeassistant.components.fan import (
    SUPPORT_PRESET_MODE,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_lan.const import ATTR_FAN_SPEED, DOMAIN
from custom_components.midea_dehumidifier_lan.hub import ApplianceEntity, Hub

_LOGGER = logging.getLogger(__name__)

MODE_MEDIUM: Final = "Medium"
MODE_NONE: Final = "None"
MODE_AUTO: Final = "Auto"
MODE_LOW: Final = "Low"
MODE_HIGH: Final = "High"

PRESET_MODES_7: Final = [MODE_LOW, MODE_MEDIUM, MODE_HIGH]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up fan entity for dehumidifer"""

    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        DehumidiferFan(c) for c in hub.coordinators if c.is_dehumidifier()
    )


# pylint: disable=too-many-ancestors
class DehumidiferFan(ApplianceEntity, FanEntity):
    """Entity for managing dehumidifer fan"""

    _attr_speed_count = 3
    _attr_preset_modes = PRESET_MODES_7
    _attr_supported_features = SUPPORT_PRESET_MODE | SUPPORT_SET_SPEED
    _name_suffix = " Fan"

    @property
    def is_on(self) -> bool:
        """Assume fan is off when in silent mode"""
        return self.dehumidifier().fan_speed > 40

    @property
    def percentage(self) -> int:
        """Return the current speed percentage."""
        return self.dehumidifier().fan_speed

    @property
    def preset_mode(self) -> str:
        speed = self.dehumidifier().fan_speed

        if speed == 0:
            return MODE_NONE
        if speed <= 40:
            return MODE_LOW
        if speed <= 60:
            return MODE_MEDIUM
        if speed <= 80:
            return MODE_HIGH
        return MODE_AUTO

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode == MODE_LOW:
            self.apply(ATTR_FAN_SPEED, 40)
        elif preset_mode == MODE_MEDIUM:
            self.apply(ATTR_FAN_SPEED, 60)
        elif preset_mode == MODE_HIGH:
            self.apply(ATTR_FAN_SPEED, 80)
        elif preset_mode == MODE_AUTO:
            self.apply(ATTR_FAN_SPEED, 101)
        else:
            _LOGGER.warning("Unsupported fan mode %s", preset_mode)

    def set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        self.apply(ATTR_FAN_SPEED, percentage)

    def turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turns fan to medium speed."""
        updated = False
        if preset_mode is not None:
            self.set_preset_mode(preset_mode)
            updated = True
        if percentage is not None:
            self.set_percentage(percentage)
            updated = True
        if speed is not None:
            self.set_speed(speed)
            updated = True
        if not updated and self.percentage <= 40:
            self.set_preset_mode(MODE_MEDIUM)

    def turn_off(self, **kwargs: Any) -> None:
        """Turns fan to silent speed."""
        self.set_preset_mode(MODE_LOW)
