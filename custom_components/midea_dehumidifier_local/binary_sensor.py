from midea_beautiful_dehumidifier.lan import LanDevice
from config.custom_components.midea_dehumidifier_local.const import DOMAIN
from homeassistant.components.binary_sensor import BinarySensorEntity
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
        TankFullSensor(appliance) for appliance in hub.appliances
    )


class TankFullSensor(BinarySensorEntity):
    def __init__(self, appliance: LanDevice) -> None:
        super().__init__()
        self._appliance = appliance
        self._unique_id = f"midea_dehumidifier_tank_full_{appliance.id}"

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the unique id."""
        return str(getattr(self._appliance.state, "name", self.unique_id)) + " Tank Full"

    @property
    def is_on(self):
        return getattr(self._appliance.state, "tank_full", False)

    @property
    def device_info(self):
        return {
            "identifiers": {
                (DOMAIN, self._appliance.sn)
            },
            "name": self.name,
            "manufacturer": "Midea",
            "model": str(self._appliance.type),
        }