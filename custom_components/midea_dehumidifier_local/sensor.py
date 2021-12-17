from midea_beautiful_dehumidifier.lan import LanDevice
from config.custom_components.midea_dehumidifier_local.const import DOMAIN
from homeassistant.components.sensor import SensorEntity
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
        CurrentHumiditySensor(appliance) for appliance in hub.appliances
    )


class CurrentHumiditySensor(SensorEntity):
    def __init__(self, appliance: LanDevice) -> None:
        super().__init__()
        self._appliance = appliance
        self._unique_id = f"midea_dehumidifier_humidity_{appliance.id}"

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the unique id."""
        return str(getattr(self._appliance.state, "name", self.unique_id)) + " Humidity"

    @property
    def device_class(self):
        return "humidity"

    @property
    def native_value(self):
        return getattr(self._appliance.state, "current_humidity", None)

    @property
    def native_unit_of_measurement(self):
        return "%"

    @property
    def state_class(self):
        return "measurement"

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