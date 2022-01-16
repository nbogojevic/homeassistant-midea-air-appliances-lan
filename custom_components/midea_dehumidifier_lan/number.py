from homeassistant.components.number import (
    NumberEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.midea_dehumidifier_lan.const import (
    DOMAIN,
)
from custom_components.midea_dehumidifier_lan.hub import ApplianceEntity, Hub


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sets up appliance binary sensors"""
    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    # Dehumidifier sensors
    async_add_entities(
        _ErrorCode(c) for c in hub.coordinators if c.is_dehumidifier() or c.is_climate()
    )


class _ErrorCode(ApplianceEntity, NumberEntity):

    _name_suffix = " Error Code"

    @property
    def value(self) -> float:
        """Return the value of the sensor property."""
        return self.dehumidifier().error_code
