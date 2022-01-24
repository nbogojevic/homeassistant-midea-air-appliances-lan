"""Adds fan entity for each dehumidifer appliance."""

import logging
from typing import Any, Final

from homeassistant.components.fan import (
    SUPPORT_PRESET_MODE,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_lan.const import ATTR_FAN_SPEED, DOMAIN
from custom_components.midea_dehumidifier_lan.appliance_coordinator import (
    ApplianceEntity,
    ApplianceUpdateCoordinator,
)
from custom_components.midea_dehumidifier_lan.hub import Hub

_LOGGER = logging.getLogger(__name__)

MODE_NONE: Final = "None"
MODE_AUTO: Final = "Auto"
MODE_LOW: Final = "Low"
MODE_MEDIUM: Final = "Medium"
MODE_HIGH: Final = "High"

PRESET_MODES_7: Final = [MODE_LOW, MODE_MEDIUM, MODE_HIGH]
PRESET_MODES_3: Final = [MODE_LOW, MODE_HIGH]
PRESET_MODES_2: Final = [MODE_AUTO]


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

    _attr_supported_features = SUPPORT_PRESET_MODE
    _name_suffix = " Fan"

    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)
        supports = coordinator.appliance.state.capabilities
        fan_capability = supports.get("fan_speed", 0)

        if fan_capability == 3:
            self._attr_preset_modes = PRESET_MODES_3
        elif fan_capability == 2:
            self._attr_preset_modes = PRESET_MODES_2
        else:
            self._attr_preset_modes = PRESET_MODES_7
        self._attr_speed_count = len(self._attr_preset_modes)
        self._fan_speeds = {
            MODE_NONE: 0,
            MODE_LOW: 40,
            MODE_MEDIUM: 60,
            MODE_HIGH: 80 if self._attr_speed_count == 3 else 60,
            MODE_AUTO: 101,
        }

    @property
    def is_on(self) -> bool:
        """Assume fan is off when in silent mode"""
        return self.dehumidifier().fan_speed > self._fan_speeds[MODE_LOW]

    @property
    def percentage(self) -> int:
        """Return the current speed percentage."""
        return self.dehumidifier().fan_speed

    @property
    def preset_mode(self) -> str:
        fan_speed = self.dehumidifier().fan_speed
        for mode, mode_speed in self._fan_speeds.items():
            if fan_speed <= mode_speed:
                return mode
        return MODE_NONE

    def _is_speed(self, speed: int) -> bool:
        return self._attr_speed_count == speed

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        speed = self._fan_speeds.get(preset_mode, None)
        if speed is not None:
            self.apply(ATTR_FAN_SPEED, speed)
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
        if not updated and self.percentage < self._fan_speeds[MODE_MEDIUM]:
            self.set_preset_mode(MODE_MEDIUM)

    def turn_off(self, **kwargs: Any) -> None:
        """Turns fan to silent speed."""
        self.set_preset_mode(MODE_LOW)
