"""Support for different Midea appliances switches"""

from dataclasses import dataclass
from typing import Final
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_lan.hub import (
    Hub,
)
from custom_components.midea_dehumidifier_lan.appliance_coordinator import (
    ApplianceEntity,
    ApplianceUpdateCoordinator,
)
from custom_components.midea_dehumidifier_lan.const import (
    ENTITY_DISABLED_BY_DEFAULT,
    DOMAIN,
    UNIQUE_CLIMATE_PREFIX,
    UNIQUE_DEHUMIDIFIER_PREFIX,
)
from custom_components.midea_dehumidifier_lan.util import is_enabled_by_capabilities


@dataclass
class _MideaSwitchDescriptor:
    attr: str
    name: str
    icon: str
    capability: str
    prefix: str


ION_MODE_SWITCH: Final = _MideaSwitchDescriptor(
    attr="ion_mode",
    name="Ion Mode",
    icon="mdi:air-purifier",
    capability="ion",
    prefix=UNIQUE_DEHUMIDIFIER_PREFIX,
)
PUMP_SWITCH: Final = _MideaSwitchDescriptor(
    attr="pump",
    name="Pump",
    icon="mdi:pump",
    capability="pump",
    prefix=UNIQUE_DEHUMIDIFIER_PREFIX,
)
PUMP_SWITCH_ENABLED: Final = _MideaSwitchDescriptor(
    attr="pump_enabled",
    name="Pump Enabled",
    icon="mdi:electric-switch",
    capability="pump",
    prefix=UNIQUE_DEHUMIDIFIER_PREFIX,
)
DEHUMIDIFIER_BEEP_SWITCH: Final = _MideaSwitchDescriptor(
    attr="beep_prompt",
    name="Beep",
    icon="mdi:bell-check",
    capability=ENTITY_DISABLED_BY_DEFAULT,
    prefix=UNIQUE_DEHUMIDIFIER_PREFIX,
)
DEHUMIDIFER_SWITCHES: Final = [
    DEHUMIDIFIER_BEEP_SWITCH,
    ION_MODE_SWITCH,
    PUMP_SWITCH,
    PUMP_SWITCH_ENABLED,
]
# Climate
CLIMATE_BEEP_SWITCH: Final = _MideaSwitchDescriptor(
    attr="beep_prompt",
    name="Beep",
    icon="mdi:bell-check",
    capability=ENTITY_DISABLED_BY_DEFAULT,
    prefix=UNIQUE_CLIMATE_PREFIX,
)
FAHRENHEIT_SWITCH: Final = _MideaSwitchDescriptor(
    attr="fahrenheit",
    name="Fahrenheit",
    icon="mdi:temperature-fahrenheit",
    capability="fahrenheit",
    prefix=UNIQUE_CLIMATE_PREFIX,
)
DRYER_SWITCH: Final = _MideaSwitchDescriptor(
    attr="dryer",
    name="Dry Mode",
    icon="mdi:water-opacity",
    capability="_DISABLED_BY_DEFAULT",
    prefix=UNIQUE_CLIMATE_PREFIX,
)
PURIFIER_SWITCH: Final = _MideaSwitchDescriptor(
    attr="purifier",
    name="Purifier",
    icon="mdi:air-purifier",
    capability="anion",
    prefix=UNIQUE_CLIMATE_PREFIX,
)
TURBO_FAN_SWITCH: Final = _MideaSwitchDescriptor(
    attr="turbo_fan",
    name="Turbo Fan",
    icon="mdi:fan-alert",
    capability="strong_fan",
    prefix=UNIQUE_CLIMATE_PREFIX,
)
SCREEN_SWITCH: Final = _MideaSwitchDescriptor(
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


def _is_enabled(
    coordinator: ApplianceUpdateCoordinator, switch: _MideaSwitchDescriptor
) -> bool:
    return is_enabled_by_capabilities(
        coordinator.appliance.state.capabilities, switch.capability
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up appliance switches"""

    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    switches = []
    # Dehumidifier sensors
    for switch in DEHUMIDIFER_SWITCHES:
        for coord in hub.coordinators:
            if coord.is_dehumidifier() and _is_enabled(coord, switch):
                switches.append(MideaSwitch(coord, switch))

    # Air conditioner entities
    for switch in CLIMATE_SWITCHES:
        for coord in hub.coordinators:
            if coord.is_climate() and _is_enabled(coord, switch):
                switches.append(MideaSwitch(coord, switch))

    async_add_entities(switches)


# pylint: disable=too-many-ancestors
class MideaSwitch(ApplianceEntity, SwitchEntity):
    """Generic attr based switch"""

    def __init__(
        self,
        coordinator: ApplianceUpdateCoordinator,
        descriptor: _MideaSwitchDescriptor,
    ) -> None:
        self._switch_descriptor = descriptor
        self._unique_id_prefix = descriptor.prefix
        self._name_suffix = " " + descriptor.name.strip()
        super().__init__(coordinator)

        self._attr_icon = descriptor.icon
        self._attribute_name = descriptor.attr

    def on_online(self, update: bool) -> None:
        super()._set_enabled_for_capability(self._switch_descriptor.capability)

        return super().on_online(update)

    def on_update(self) -> None:
        self._attr_is_on = getattr(self.appliance.state, self._attribute_name, None)

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        self.apply(self._attribute_name, True)

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self.apply(self._attribute_name, False)
