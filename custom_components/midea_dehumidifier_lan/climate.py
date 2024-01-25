"""Adds climate entity for each air conditioner appliance."""

import logging
from typing import Final

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
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
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_lan.appliance_coordinator import (
    ApplianceEntity,
)
from custom_components.midea_dehumidifier_lan.const import (
    ATTR_RUNNING,
    DOMAIN,
    MAX_TARGET_TEMPERATURE,
    MIN_TARGET_TEMPERATURE,
)
from custom_components.midea_dehumidifier_lan.hub import Hub

_LOGGER = logging.getLogger(__name__)


FAN_SILENT = "Silent"
FAN_FULL = "Full"

HVAC_MODES: Final = [
    HVACMode.OFF,
    HVACMode.AUTO,
    HVACMode.COOL,
    HVACMode.HEAT,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
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

_FAN_SPEEDS = {
    FAN_AUTO: 102,
    FAN_FULL: 100,
    FAN_HIGH: 80,
    FAN_MEDIUM: 60,
    FAN_LOW: 40,
    FAN_SILENT: 20,
}

_MODES_TO_MIDEA = {
    HVACMode.AUTO: 1,
    HVACMode.COOL: 2,
    HVACMode.DRY: 3,
    HVACMode.HEAT: 4,
    HVACMode.FAN_ONLY: 5,
}

_MIDEA_TO_MODES = {
    1: HVACMode.AUTO,
    2: HVACMode.COOL,
    3: HVACMode.DRY,
    4: HVACMode.HEAT,
    5: HVACMode.FAN_ONLY,
}

_HVAC_ACTIONS = {
    HVACMode.OFF: HVACAction.OFF,
    HVACMode.AUTO: None,
    HVACMode.COOL: HVACAction.COOLING,
    HVACMode.DRY: HVACAction.DRYING,
    HVACMode.HEAT: HVACAction.HEATING,
    HVACMode.FAN_ONLY: HVACAction.FAN,
}


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
    """Climate entity for Midea air conditioner"""

    _attr_hvac_modes = HVAC_MODES
    _attr_fan_modes = FAN_MODES
    _attr_preset_modes = PRESET_MODES
    _attr_swing_modes = SWING_MODES
    _attr_max_temp = MAX_TARGET_TEMPERATURE
    _attr_min_temp = MIN_TARGET_TEMPERATURE
    _attr_precision = PRECISION_HALVES
    _attr_temperature_unit = TEMP_CELSIUS

    _attr_supported_features = (
        SUPPORT_TARGET_TEMPERATURE
        | SUPPORT_FAN_MODE
        | SUPPORT_SWING_MODE
        | SUPPORT_PRESET_MODE
    )

    _name_suffix = ""
    _add_extra_attrs = True

    def on_update(self) -> None:
        aircon = self.airconditioner()
        self._attr_current_temperature = aircon.indoor_temperature
        self._attr_target_temperature = aircon.target_temperature
        self._attr_fan_mode = self._fan_mode()
        self._attr_preset_mode = self._preset_mode()
        self._attr_swing_mode = self._swing_mode()
        self._attr_hvac_mode = self._hvac_mode()
        self._attr_hvac_action = _HVAC_ACTIONS.get(self._attr_hvac_mode)
        super().on_update()

    def _fan_mode(self) -> str:
        fan_speed = self.airconditioner().fan_speed
        for mode, mode_speed in _FAN_SPEEDS.items():
            if fan_speed <= mode_speed:
                return mode
        return FAN_AUTO

    def _preset_mode(self) -> str:
        if self.airconditioner().turbo:
            return PRESET_BOOST
        if self.airconditioner().eco_mode:
            return PRESET_ECO
        if self.airconditioner().comfort_sleep:
            return PRESET_SLEEP
        return PRESET_NONE

    def _swing_mode(self) -> str:
        if self.airconditioner().vertical_swing:
            if self.airconditioner().horizontal_swing:
                return SWING_BOTH
            return SWING_VERTICAL
        if self.airconditioner().horizontal_swing:
            return SWING_HORIZONTAL
        return SWING_OFF

    def _hvac_mode(self) -> str:
        if not self.airconditioner().running:
            return HVACMode.OFF

        curr_mode = self.airconditioner().mode
        mode = _MIDEA_TO_MODES.get(curr_mode)
        if mode is None:
            mode = HVACMode.AUTO
            _LOGGER.warning("Unknown mode %d, reporting %s", curr_mode, mode)

        return mode

    def turn_on(self, **kwargs) -> None:  # pylint: disable=unused-argument
        """Turn the entity on."""
        self.apply(ATTR_RUNNING, True)

    def turn_off(self, **kwargs) -> None:  # pylint: disable=unused-argument
        """Turn the entity off."""
        self.apply(ATTR_RUNNING, False)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            self.turn_off()
            return
        midea_mode = _MODES_TO_MIDEA.get(hvac_mode)
        if midea_mode is None:
            _LOGGER.warning("Unsupported climate mode %s", hvac_mode)
            return
        # Make sure we are running
        if not self.airconditioner().running:
            self.turn_on()
        self.apply("mode", midea_mode)

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE):
            self.apply("target_temperature", kwargs.get(ATTR_TEMPERATURE))
        if kwargs.get(ATTR_HVAC_MODE):
            self.set_hvac_mode(kwargs.get(ATTR_HVAC_MODE))
        if kwargs.get(ATTR_SWING_MODE):
            self.set_swing_mode(kwargs.get(ATTR_SWING_MODE))
        if kwargs.get(ATTR_FAN_MODE):
            self.set_fan_mode(kwargs.get(ATTR_FAN_MODE))

    def set_swing_mode(self, swing_mode: str) -> None:
        if swing_mode == SWING_VERTICAL:
            self.apply(vertical_swing=True, horizontal_swing=False)
        elif swing_mode == SWING_HORIZONTAL:
            self.apply(vertical_swing=False, horizontal_swing=True)
        elif swing_mode == SWING_BOTH:
            self.apply(vertical_swing=True, horizontal_swing=True)
        else:
            self.apply(vertical_swing=False, horizontal_swing=False)

    def set_fan_mode(self, fan_mode: str) -> None:
        self.apply(fan_speed=_FAN_SPEEDS.get(fan_mode, 20))

    def set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == PRESET_BOOST:
            self.apply(turbo=True, eco_mode=False, comfort_sleep=False)
        elif preset_mode == PRESET_ECO:
            self.apply(turbo=False, eco_mode=True, comfort_sleep=False)
        elif preset_mode == PRESET_SLEEP:
            self.apply(turbo=False, eco_mode=False, comfort_sleep=True)
        else:
            self.apply(turbo=False, eco_mode=False, comfort_sleep=False)
