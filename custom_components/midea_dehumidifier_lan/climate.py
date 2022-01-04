"""Adds climate entity for each air conditioner appliance."""

import logging
from typing import Final

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_SLEEP,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, TEMP_CELSIUS
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
    MAX_TARGET_TEMPERATURE,
    MIN_TARGET_TEMPERATURE,
)

_LOGGER = logging.getLogger(__name__)


FAN_SILENT = "Silent"
FAN_FULL = "Full"

HVAC_MODES: Final = [
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
]
FAN_MODES: Final = [
    FAN_SILENT,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    FAN_FULL,
    FAN_AUTO,
]

SWING_MODES: Final = [SWING_OFF, SWING_HORIZONTAL, SWING_VERTICAL, SWING_BOTH]

PRESET_MODES: Final = [PRESET_NONE, PRESET_ECO, PRESET_BOOST, PRESET_SLEEP]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up air conditioner entites"""
    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        AirConditionerEntity(c) for c in hub.coordinators if c.is_climate()
    )


class AirConditionerEntity(ApplianceEntity, ClimateEntity):
    """Air conditioner entity for Midea appliances """

    _attr_hvac_modes = HVAC_MODES
    _attr_fan_modes = FAN_MODES
    _attr_preset_modes = PRESET_MODES
    _attr_swing_modes = SWING_MODES
    _attr_max_temp = MAX_TARGET_TEMPERATURE
    _attr_min_temp = MIN_TARGET_TEMPERATURE
    _attr_precision = PRECISION_HALVES
    _attr_temperature_unit = TEMP_CELSIUS

    _name_suffix = ""

    _attr_supported_features = (
        SUPPORT_TARGET_TEMPERATURE
        | SUPPORT_FAN_MODE
        | SUPPORT_SWING_MODE
        | SUPPORT_PRESET_MODE
    )

    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def is_on(self) -> bool:
        return getattr(self.appliance.state, ATTR_RUNNING, False)

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return getattr(self.appliance.state, "indoor_temperature", 0.0)

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return getattr(self.appliance.state, "target_temperature", 0.0)

    @property
    def fan_mode(self):
        f = getattr(self.appliance.state, "fan_speed", False)
        if f <= 20:
            return FAN_SILENT
        elif f <= 40:
            return FAN_LOW
        elif f <= 60:
            return FAN_MEDIUM
        elif f <= 80:
            return FAN_HIGH
        elif f <= 100:
            return FAN_FULL
        else:
            return FAN_AUTO

    @property
    def preset_mode(self) -> str:
        t = getattr(self.appliance.state, "turbo", False)
        e = getattr(self.appliance.state, "eco_mode", False)
        s = getattr(self.appliance.state, "comfort_sleep", False)
        if t:
            return PRESET_BOOST
        elif e:
            return PRESET_ECO
        elif s:
            return PRESET_SLEEP
        else:
            return PRESET_NONE

    @property
    def swing_mode(self):
        v = getattr(self.appliance.state, "vertical_swing", False)
        h = getattr(self.appliance.state, "horizontal_swing", False)
        if v:
            if h:
                return SWING_BOTH

            return SWING_VERTICAL
        if h:
            return SWING_HORIZONTAL
        return SWING_OFF

    @property
    def hvac_mode(self):
        curr_mode = getattr(self.appliance.state, "mode", 1)
        if curr_mode == 1:
            return HVAC_MODE_AUTO
        if curr_mode == 2:
            return HVAC_MODE_COOL
        if curr_mode == 3:
            return HVAC_MODE_HEAT
        if curr_mode == 4:
            return HVAC_MODE_DRY
        if curr_mode == 5:
            return HVAC_MODE_FAN_ONLY
        _LOGGER.warning("Unknown mode %d", curr_mode)
        return HVAC_MODE_AUTO

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        self.apply(ATTR_RUNNING, True)

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self.apply(ATTR_RUNNING, False)

    def set_hvac_mode(self, mode) -> None:
        """Set new target hvac mode."""
        if mode == HVAC_MODE_AUTO:
            curr_mode = 1
        elif mode == HVAC_MODE_COOL:
            curr_mode = 2
        elif mode == HVAC_MODE_HEAT:
            curr_mode = 3
        elif mode == HVAC_MODE_DRY:
            curr_mode = 4
        elif mode == HVAC_MODE_FAN_ONLY:
            curr_mode = 5
        else:
            _LOGGER.warning("Unsupported climate mode %s", mode)
            curr_mode = 1
        self.apply("mode", curr_mode)

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE):
            self.apply("current_temperature", kwargs.get(ATTR_TEMPERATURE))

    def set_swing_mode(self, mode: str):
        if mode == SWING_VERTICAL:
            self.apply(vertical_swing=True, horizontal_swing=False)
        elif mode == SWING_HORIZONTAL:
            self.apply(vertical_swing=False, horizontal_swing=True)
        elif mode == SWING_BOTH:
            self.apply(vertical_swing=True, horizontal_swing=True)
        else:
            self.apply(vertical_swing=False, horizontal_swing=False)

    def set_fan_mode(self, mode: str):
        if mode == FAN_AUTO:
            self.apply(fan_speed=102)
        elif mode == FAN_FULL:
            self.apply(fan_speed=100)
        elif mode == FAN_HIGH:
            self.apply(fan_speed=80)
        elif mode == FAN_MEDIUM:
            self.apply(fan_speed=60)
        elif mode == FAN_LOW:
            self.apply(fan_speed=40)
        else:
            self.apply(fan_speed=20)

    def set_preset_mode(self, mode: str):
        if mode == PRESET_BOOST:
            self.apply(turbo=True, eco_mode=False, comfort_sleep=False)
        elif mode == PRESET_ECO:
            self.apply(turbo=False, eco_mode=True, comfort_sleep=False)
        elif mode == PRESET_SLEEP:
            self.apply(turbo=False, eco_mode=False, comfort_sleep=True)
        else:
            self.apply(turbo=False, eco_mode=False, comfort_sleep=False)
