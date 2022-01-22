"""Adds climate entity for each air conditioner appliance."""

from datetime import datetime
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

from custom_components.midea_dehumidifier_lan.const import (
    ATTR_RUNNING,
    DOMAIN,
    MAX_TARGET_TEMPERATURE,
    MIN_TARGET_TEMPERATURE,
)
from custom_components.midea_dehumidifier_lan.hub import (
    ApplianceEntity,
    ApplianceUpdateCoordinator,
    Hub,
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
    """Climate entity for Midea air conditioner"""

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
        self._last_error_code = 0
        self._last_error_code_time = datetime.now()

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.airconditioner().running

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self.airconditioner().indoor_temperature

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self.airconditioner().target_temperature

    @property
    def fan_mode(self):
        fan = self.airconditioner().fan_speed
        if fan <= 20:
            return FAN_SILENT
        if fan <= 40:
            return FAN_LOW
        if fan <= 60:
            return FAN_MEDIUM
        if fan <= 80:
            return FAN_HIGH
        if fan <= 100:
            return FAN_FULL
        return FAN_AUTO

    @property
    def preset_mode(self) -> str:
        if self.airconditioner().turbo:
            return PRESET_BOOST
        if self.airconditioner().eco_mode:
            return PRESET_ECO
        if self.airconditioner().comfort_sleep:
            return PRESET_SLEEP
        return PRESET_NONE

    @property
    def swing_mode(self):
        if self.airconditioner().vertical_swing:
            if self.airconditioner().horizontal_swing:
                return SWING_BOTH
            return SWING_VERTICAL
        if self.airconditioner().horizontal_swing:
            return SWING_HORIZONTAL
        return SWING_OFF

    @property
    def hvac_mode(self):
        curr_mode = self.airconditioner().mode
        mode = next((i[1] for i in self._MODES if i[0] == curr_mode), None)
        if mode is None:
            _LOGGER.warning("Unknown mode %d", curr_mode)
            return HVAC_MODE_AUTO
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

    _MODES = [
        (1, HVAC_MODE_AUTO),
        (2, HVAC_MODE_COOL),
        (3, HVAC_MODE_HEAT),
        (4, HVAC_MODE_DRY),
        (5, HVAC_MODE_FAN_ONLY),
    ]

    def turn_on(self, **kwargs) -> None:  # pylint: disable=unused-argument
        """Turn the entity on."""
        self.apply(ATTR_RUNNING, True)

    def turn_off(self, **kwargs) -> None:  # pylint: disable=unused-argument
        """Turn the entity off."""
        self.apply(ATTR_RUNNING, False)

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        midea_mode = next((i[0] for i in self._MODES if i[1] == hvac_mode), None)
        if midea_mode is None:
            _LOGGER.warning("Unsupported climate mode %s", hvac_mode)
            midea_mode = 1
        self.apply("mode", midea_mode)

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE):
            self.apply("current_temperature", kwargs.get(ATTR_TEMPERATURE))

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
        if fan_mode == FAN_AUTO:
            self.apply(fan_speed=102)
        elif fan_mode == FAN_FULL:
            self.apply(fan_speed=100)
        elif fan_mode == FAN_HIGH:
            self.apply(fan_speed=80)
        elif fan_mode == FAN_MEDIUM:
            self.apply(fan_speed=60)
        elif fan_mode == FAN_LOW:
            self.apply(fan_speed=40)
        else:
            self.apply(fan_speed=20)

    def set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == PRESET_BOOST:
            self.apply(turbo=True, eco_mode=False, comfort_sleep=False)
        elif preset_mode == PRESET_ECO:
            self.apply(turbo=False, eco_mode=True, comfort_sleep=False)
        elif preset_mode == PRESET_SLEEP:
            self.apply(turbo=False, eco_mode=False, comfort_sleep=True)
        else:
            self.apply(turbo=False, eco_mode=False, comfort_sleep=False)
