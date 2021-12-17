from midea_beautiful_dehumidifier.lan import LanDevice
from config.custom_components.midea_dehumidifier_local.const import DOMAIN
from homeassistant.components.fan import SUPPORT_SET_SPEED, FanEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub = hass.data[DOMAIN][config_entry.entry_id]

    # Add all entities to HA
    async_add_entities(
        DehumidiferFan(appliance) for appliance in hub.appliances
    )


class DehumidiferFan(FanEntity):
    def __init__(self, appliance: LanDevice) -> None:
        super().__init__()
        self._appliance = appliance
        self._unique_id = f"midea_dehumidifier_fan_{appliance.id}"

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the unique id."""
        return str(getattr(self._appliance.state, "name", self.unique_id)) + " Fan"

    @property
    def percentage(self):
        return getattr(self._appliance.state, "fan_speed", 0)

    @property
    def supported_features(self):
        return SUPPORT_SET_SPEED
    
    def set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        setattr(self._appliance.state, "fan_speed", percentage)
        self._appliance.apply()

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._appliance.sn)
            },
            "name": str(getattr(self._appliance.state, "name", self.unique_id)),
            "manufacturer": "Midea",
            "model": str(self._appliance.type),
        }