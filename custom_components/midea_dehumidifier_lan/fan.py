"""Adds fan entity for each dehumidifer appliance."""

import logging
from typing import Final, Optional
from homeassistant.components.fan import (
    SUPPORT_PRESET_MODE,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from custom_components.midea_dehumidifier_lan import ApplianceEntity, Hub
from custom_components.midea_dehumidifier_lan.const import DOMAIN


_LOGGER = logging.getLogger(__name__)

MODE_SILENT: Final = "Silent"
MODE_MEDIUM: Final = "Medium"
MODE_TURBO: Final = "Turbo"
MODE_NONE: Final = "None"

PRESET_MODES: Final = [MODE_SILENT, MODE_MEDIUM, MODE_TURBO]
PRESET_SPEEDS: Final = [40, 60, 80]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up fan entity for managing dehumidifer fan"""

    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        DehumidiferFan(c) for c in hub.coordinators if c.is_dehumidifier()
    )


class DehumidiferFan(ApplianceEntity, FanEntity):
    """Entity for managing dehumidifer fan"""

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return " Fan"

    @property
    def unique_id_prefix(self) -> str:
        """Prefix for entity id"""
        return "midea_dehumidifier_fan_"

    @property
    def is_on(self) -> bool:
        speed = getattr(self.appliance.state, "fan_speed", 0)
        return speed > 40

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed percentage."""
        speed = getattr(self.appliance.state, "fan_speed", 0)
        return ordered_list_item_to_percentage(PRESET_SPEEDS, speed)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(PRESET_SPEEDS)

    @property
    def supported_features(self) -> int:
        return SUPPORT_PRESET_MODE | SUPPORT_SET_SPEED

    @property
    def preset_modes(self) -> list[str]:
        return PRESET_MODES

    @property
    def preset_mode(self) -> str:
        speed = getattr(self.appliance.state, "fan_speed", 0)
        if speed == 40:
            return MODE_SILENT
        if speed == 60:
            return MODE_MEDIUM
        if speed == 80:
            return MODE_TURBO
        return MODE_NONE

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode == MODE_SILENT:
            self.apply("fan_speed", 40)
        elif preset_mode == MODE_MEDIUM:
            self.apply("fan_speed", 60)
        elif preset_mode == MODE_TURBO:
            self.apply("fan_speed", 80)
        else:
            _LOGGER.warning("Unsupported fan mode %s", preset_mode)

    def set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        speed = percentage_to_ordered_list_item(PRESET_SPEEDS, percentage)
        self.apply("fan_speed", speed)

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        self.set_preset_mode(MODE_MEDIUM)

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self.set_preset_mode(MODE_SILENT)
