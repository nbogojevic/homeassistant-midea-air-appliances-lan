"""Adds binary sensors for appliances."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from midea_beautiful.midea import ERROR_CODE_BUCKET_FULL, ERROR_CODE_BUCKET_REMOVED

from custom_components.midea_dehumidifier_lan.const import (
    DOMAIN,
    UNIQUE_DEHUMIDIFIER_PREFIX,
)
from custom_components.midea_dehumidifier_lan.appliance_coordinator import (
    ApplianceEntity,
    ApplianceUpdateCoordinator,
)
from custom_components.midea_dehumidifier_lan.hub import Hub
from custom_components.midea_dehumidifier_lan.util import is_enabled_by_capabilities


def _is_enabled(coordinator: ApplianceUpdateCoordinator, capability: str) -> bool:
    return is_enabled_by_capabilities(
        coordinator.appliance.state.capabilities, capability
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up appliance binary sensors"""
    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    # Dehumidifier sensors
    async_add_entities(
        TankFullSensor(c) for c in hub.coordinators if c.is_dehumidifier()
    )
    # Add tank removed sensor if pump is supported
    async_add_entities(
        TankRemovedSensor(c)
        for c in hub.coordinators
        if c.is_dehumidifier() and _is_enabled(c, "pump")
    )
    async_add_entities(
        FilterReplacementSensor(c)
        for c in hub.coordinators
        if c.is_dehumidifier() and _is_enabled(c, "filter")
    )
    async_add_entities(
        DefrostingSensor(c) for c in hub.coordinators if c.is_dehumidifier()
    )


class TankFullSensor(ApplianceEntity, BinarySensorEntity):
    """
    Describes full tank binary sensors (indicated as problem as it prevents
    dehumidifier from operating)
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _name_suffix = " Tank Full"

    def on_update(self) -> None:
        self._attr_is_on = (
            self.dehumidifier().tank_full
            or self.dehumidifier().error_code == ERROR_CODE_BUCKET_FULL
        )


class TankRemovedSensor(ApplianceEntity, BinarySensorEntity):
    """
    Shows that tank has been removed binary sensors (indicated as problem as it prevents
    dehumidifier from operating)
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _name_suffix = " Tank Removed"
    _capability_attr = "pump"

    def on_update(self) -> None:
        self._attr_is_on = self.dehumidifier().error_code == ERROR_CODE_BUCKET_REMOVED


class FilterReplacementSensor(ApplianceEntity, BinarySensorEntity):
    """
    Describes filter replacement binary sensors (indicated as problem)
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_registry_enabled_default = False
    _name_suffix = " Replace Filter"
    _capability_attr = "filter"

    @property
    def unique_id_prefix(self) -> str:
        """Prefix for entity id"""
        return f"{UNIQUE_DEHUMIDIFIER_PREFIX}filter_"

    def on_update(self) -> None:
        self._attr_is_on = self.dehumidifier().filter_indicator


class DefrostingSensor(ApplianceEntity, BinarySensorEntity):
    """
    Describes defrosting mode binary sensors (indicated as cold)
    """

    _attr_device_class = BinarySensorDeviceClass.COLD
    _attr_entity_registry_enabled_default = False
    _name_suffix = " Defrosting"

    def on_update(self) -> None:
        self._attr_is_on = self.dehumidifier().defrosting
