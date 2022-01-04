"""Support for different Midea appliances switches"""

from dataclasses import dataclass
import logging
from typing import Final
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_lan import (
    ApplianceEntity,
    ApplianceUpdateCoordinator,
    Hub,
)
from custom_components.midea_dehumidifier_lan.const import (
    DOMAIN,
    UNIQUE_CLIMATE_PREFIX,
    UNIQUE_DEHUMIDIFIER_PREFIX,
)


@dataclass
class MideaSwitchDescriptor:
    attr: str
    name: str
    icon: str
    capability: str
    prefix: str


_DISABLED_BY_DEFAULT: Final = ""

ION_MODE_SWITCH: Final = MideaSwitchDescriptor(
    attr="ion_mode",
    name="Ion Mode",
    icon="mdi:air-purifier",
    capability="ion",
    prefix=UNIQUE_DEHUMIDIFIER_PREFIX,
)
PUMP_SWITCH: Final = MideaSwitchDescriptor(
    attr="pump",
    name="Pump",
    icon="mdi:pump",
    capability="pump",
    prefix=UNIQUE_DEHUMIDIFIER_PREFIX,
)
SLEEP_SWITCH: Final = MideaSwitchDescriptor(
    attr="sleep",
    name="Sleep",
    icon="mdi:weather-night",
    capability=_DISABLED_BY_DEFAULT,
    prefix=UNIQUE_DEHUMIDIFIER_PREFIX,
)
DEHUMIDIFIER_BEEP_SWITCH: Final = MideaSwitchDescriptor(
    attr="beep_prompt",
    name="Beep",
    icon="mdi:bell-check",
    capability=_DISABLED_BY_DEFAULT,
    prefix=UNIQUE_DEHUMIDIFIER_PREFIX,
)
DEHIMIDIFER_SWITCHES: Final = [
    DEHUMIDIFIER_BEEP_SWITCH,
    ION_MODE_SWITCH,
    PUMP_SWITCH,
    SLEEP_SWITCH,
]
# Climate
CLIMATE_BEEP_SWITCH: Final = MideaSwitchDescriptor(
    attr="beep_prompt",
    name="Beep",
    icon="mdi:bell-check",
    capability=_DISABLED_BY_DEFAULT,
    prefix=UNIQUE_CLIMATE_PREFIX,
)
FAHRENHEIT_SWITCH: Final = MideaSwitchDescriptor(
    attr="fahrenheit",
    name="Fahrenheit",
    icon="mdi:temperature-fahrenheit",
    capability="fahrenheit",
    prefix=UNIQUE_CLIMATE_PREFIX,
)
DRYER_SWITCH: Final = MideaSwitchDescriptor(
    attr="dryer",
    name="Dry Mode",
    icon="mdi:water-opacity",
    capability="_DISABLED_BY_DEFAULT",
    prefix=UNIQUE_CLIMATE_PREFIX,
)
PURIFIER_SWITCH: Final = MideaSwitchDescriptor(
    attr="purifier",
    name="Purifier",
    icon="mdi:air-purifier",
    capability="anion",
    prefix=UNIQUE_CLIMATE_PREFIX,
)
TURBO_FAN_SWITCH: Final = MideaSwitchDescriptor(
    attr="turbo_fan",
    name="Turbo Fan",
    icon="mdi:fan-alert",
    capability="strong_fan",
    prefix=UNIQUE_CLIMATE_PREFIX,
)
SCREEN_SWITCH: Final = MideaSwitchDescriptor(
    attr="show_screen",
    name="Show Screen",
    icon="mdi:clock-digital",
    capability="screen_display",
    prefix=UNIQUE_CLIMATE_PREFIX,
)
CLIMATE_SWITCHES: Final = [
    CLIMATE_BEEP_SWITCH,
    DRYER_SWITCH,
    FAHRENHEIT_SWITCH,
    SCREEN_SWITCH,
    PURIFIER_SWITCH,
    TURBO_FAN_SWITCH,
]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up appliance switches"""

    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    switches = []
    # Dehumidifier sensors
    for s in DEHIMIDIFER_SWITCHES:
        for c in hub.coordinators:
            if c.is_dehumidifier():
                switches.append(MideaSwitch(c, s))

    # Air conditioner entities
    for s in CLIMATE_SWITCHES:
        for c in hub.coordinators:
            if c.is_climate():
                switches.append(MideaSwitch(c, s))

    async_add_entities(switches)


class MideaSwitch(ApplianceEntity, SwitchEntity):
    """Generic attr based switch"""

    def __init__(
        self, coordinator: ApplianceUpdateCoordinator, descriptor: MideaSwitchDescriptor
    ) -> None:
        self._unique_id_prefix = descriptor.prefix
        self.attr = descriptor.attr
        self._name_suffix = " " + descriptor.name.strip()
        self._attr_icon = descriptor.icon
        self._attr_entity_registry_enabled_default = False
        if descriptor.capability:
            supports = getattr(coordinator.appliance.state, "supports", {})
            if supports.get(descriptor.capability, 0):
                self._attr_entity_registry_enabled_default = True

        super().__init__(coordinator)

    @property
    def is_on(self) -> bool:
        return getattr(self.appliance.state, self.attr, False)

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        self.apply(self.attr, True)

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self.apply(self.attr, False)
