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

from custom_components.midea_dehumidifier_lan import (
    ApplianceEntity,
    ApplianceUpdateCoordinator,
    Hub,
)
from custom_components.midea_dehumidifier_lan.const import DOMAIN


_LOGGER = logging.getLogger(__name__)

MODE_SILENT: Final = "Silent"
MODE_MEDIUM: Final = "Medium"
MODE_TURBO: Final = "Turbo"
MODE_NONE: Final = "None"
MODE_AUTO: Final = "Auto"
MODE_LOW: Final = "Low"
MODE_HIGH: Final = "High"

PRESET_SPEEDS_7: Final = [40, 60, 80]
PRESET_SPEEDS_3: Final = [40, 80]
PRESET_SPEEDS_2: Final = [100]
PRESET_MODES_7: Final = [MODE_SILENT, MODE_MEDIUM, MODE_TURBO]
PRESET_MODES_3: Final = [MODE_LOW, MODE_HIGH]
PRESET_MODES_2: Final = [MODE_AUTO]


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

    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)
        supports = getattr(coordinator.appliance.state, "supports", {})
        self.fan_capability = supports.get("fan_speed", 0)

        if self.fan_capability == 3:
            self._preset_modes = PRESET_MODES_3
            self._preset_speeds = PRESET_SPEEDS_3
        elif self.fan_capability == 2:
            self._preset_modes = PRESET_MODES_2
            self._preset_speeds = PRESET_SPEEDS_2
        else:
            self._preset_modes = PRESET_MODES_7
            self._preset_speeds = PRESET_SPEEDS_7

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return " Fan"

    @property
    def is_on(self) -> bool:
        """Assume fan is off when in silent mode"""
        speed = getattr(self.appliance.state, "fan_speed", 0)
        return speed > 40

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed percentage."""
        speed = getattr(self.appliance.state, "fan_speed", 0)
        return ordered_list_item_to_percentage(self._preset_speeds, speed)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(self._preset_speeds)

    @property
    def supported_features(self) -> int:
        return SUPPORT_PRESET_MODE | SUPPORT_SET_SPEED

    @property
    def preset_modes(self) -> list[str]:
        return self._preset_modes

    @property
    def preset_mode(self) -> str:
        speed = getattr(self.appliance.state, "fan_speed", 0)
        if self.fan_capability == 2:
            return MODE_AUTO
        elif self.fan_capability == 3:
            if speed == 40:
                return MODE_LOW
            if speed == 80:
                return MODE_HIGH
        else:
            if speed == 40:
                return MODE_SILENT
            if speed == 60:
                return MODE_MEDIUM
            if speed == 80:
                return MODE_TURBO
        return MODE_NONE

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode == MODE_SILENT or preset_mode == MODE_LOW:
            self.apply("fan_speed", 40)
        elif preset_mode == MODE_MEDIUM:
            self.apply("fan_speed", 60)
        elif preset_mode == MODE_TURBO or preset_mode == MODE_HIGH:
            self.apply("fan_speed", 80)
        elif preset_mode == MODE_AUTO:
            self.apply("fan_speed", 101)
        else:
            _LOGGER.warning("Unsupported fan mode %s", preset_mode)

    def set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        speed = percentage_to_ordered_list_item(self._preset_speeds, percentage)
        self.apply("fan_speed", speed)

    def turn_on(self, **kwargs) -> None:
        """Turns fan to medium speed."""
        if self.fan_capability == 3:
            self.set_preset_mode(MODE_HIGH)
        elif self.fan_capability != 2:
            self.set_preset_mode(MODE_MEDIUM)

    def turn_off(self, **kwargs) -> None:
        """Turns fan to silent speed."""
        if self.fan_capability == 3:
            self.set_preset_mode(MODE_LOW)
        elif self.fan_capability != 2:
            self.set_preset_mode(MODE_SILENT)
