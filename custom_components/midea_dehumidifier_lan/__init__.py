"""
The custom component for local network access to Midea appliances
"""

from __future__ import annotations
import asyncio

from datetime import timedelta
import logging
from typing import Any, cast, final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_DEVICES,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import slugify

from midea_beautiful.appliance import AirConditionerAppliance, DehumidifierAppliance
from midea_beautiful.cloud import MideaCloud
from midea_beautiful.exceptions import AuthenticationError, MideaError
from midea_beautiful.lan import LanDevice
from midea_beautiful.midea import DEFAULT_APP_ID, DEFAULT_APPKEY
import midea_beautiful as midea_beautiful_api

from .const import (
    APPLIANCE_REFRESH_COOLDOWN,
    APPLIANCE_REFRESH_INTERVAL,
    CONF_APPID,
    CONF_APPKEY,
    CONF_NETWORK_RANGE,
    CONF_TOKEN_KEY,
    CONF_USE_CLOUD,
    CURRENT_CONFIG_VERSION,
    UNIQUE_DEHUMIDIFIER_PREFIX,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


class MideaClient:
    """Delegate to midea API"""

    def connect_to_cloud(  # pylint: disable=no-self-use
        self, account: str, password: str, appkey=DEFAULT_APPKEY, appid=DEFAULT_APP_ID
    ):
        """Delegate to midea_beautiful_api.connect_to_cloud"""
        return midea_beautiful_api.connect_to_cloud(
            account=account, password=password, appkey=appkey, appid=appid
        )

    def appliance_state(  # pylint: disable=too-many-arguments,no-self-use
        self,
        address: str | None = None,
        token: str | None = None,
        key: str | None = None,
        cloud: MideaCloud = None,
        use_cloud: bool = False,
        appliance_id: str | None = None,
    ):
        """Delegate to midea_beautiful_api.appliance_state"""
        return midea_beautiful_api.appliance_state(
            address=address,
            token=token,
            key=key,
            cloud=cloud,
            use_cloud=use_cloud,
            appliance_id=appliance_id,
        )

    def find_appliances(  # pylint: disable=too-many-arguments,no-self-use
        self,
        cloud: MideaCloud | None = None,
        appkey: str | None = None,
        account: str = None,
        password: str = None,
        appid: str = None,
        networks: list[str] = None,
    ) -> list[LanDevice]:
        """Delegate to midea_beautiful_api.find_appliances"""
        return midea_beautiful_api.find_appliances(
            cloud=cloud,
            appkey=appkey,
            account=account,
            password=password,
            appid=appid,
            networks=networks,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})

    hub = Hub(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = hub
    await hub.start()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        domain: dict = hass.data[DOMAIN]
        if domain:
            domain.pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry to new version."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version < CURRENT_CONFIG_VERSION:

        conf = {**config_entry.data}
        dev_confs = []
        conf.setdefault(CONF_USE_CLOUD, False)

        for dev_data in config_entry.data[CONF_DEVICES]:
            dev_conf = {**dev_data}
            dev_conf.setdefault(CONF_USE_CLOUD, conf[CONF_USE_CLOUD])
            dev_confs.append(dev_conf)

        conf[CONF_DEVICES] = dev_confs
        if not conf.get(CONF_APPID) or not conf.get(CONF_APPKEY):
            conf[CONF_APPKEY] = DEFAULT_APPKEY
            conf[CONF_APPID] = DEFAULT_APP_ID
        conf.setdefault(CONF_NETWORK_RANGE, [])
        conf.setdefault(CONF_USE_CLOUD, False)

        config_entry.version = CURRENT_CONFIG_VERSION
        _LOGGER.debug("Migrating configuration from %s to %s", config_entry.data, conf)
        if hass.config_entries.async_update_entry(config_entry, data=conf):
            _LOGGER.info("Configuration migrated to version %s", config_entry.version)
        else:
            _LOGGER.debug(
                "Configuration didn't change during migration to version %s",
                config_entry.version,
            )
        return True

    return False


class Hub:  # pylint: disable=too-few-public-methods
    """Central class for interacting with appliances"""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.coordinators: list[ApplianceUpdateCoordinator] = []
        self.use_cloud: bool = False
        self.cloud: MideaCloud | None = None
        self.hass = hass
        self.entry = config_entry
        self.client = MideaClient()

    async def start(self) -> None:
        """
        Sets up appliances and creates an update coordinator for
        each one
        """
        updated_conf = False
        data = {**self.entry.data}
        self.coordinators: list[ApplianceUpdateCoordinator] = []
        self.use_cloud = data.get(CONF_USE_CLOUD, False)
        self.cloud = None
        for device in data[CONF_DEVICES]:
            if await self._process_appliance(data, device):
                updated_conf = True

        for coordinator in self.coordinators:
            await coordinator.async_config_entry_first_refresh()

        if updated_conf:
            self.hass.config_entries.async_update_entry(self.entry, data=data)

    async def _process_appliance(self, data: dict, device: dict):
        updated_conf = False
        use_cloud = device.get(CONF_USE_CLOUD, self.use_cloud)
        need_cloud = use_cloud
        version = device.get(CONF_API_VERSION, 3)
        need_token = version >= 3 and (
            not device[CONF_TOKEN] or not device[CONF_TOKEN_KEY]
        )
        if not use_cloud and need_token:
            _LOGGER.warning(
                "Appliance %s has no token, trying to get it from Midea cloud API",
                device[CONF_NAME],
            )
            need_cloud = True
        if need_cloud and self.cloud is None:
            try:
                self.cloud = await self.hass.async_add_executor_job(
                    self.client.connect_to_cloud,
                    data[CONF_USERNAME],
                    data[CONF_PASSWORD],
                    data[CONF_APPKEY],
                    data[CONF_APPID],
                )
            except AuthenticationError as ex:
                raise ConfigEntryAuthFailed(
                    f"Unable to login to Midea cloud {ex}"
                ) from ex
        try:
            appliance = await self.hass.async_add_executor_job(
                self.client.appliance_state,
                device[CONF_IP_ADDRESS] if not need_cloud else None,  # ip
                device[CONF_TOKEN],  # token
                device[CONF_TOKEN_KEY],  # key
                self.cloud,  # cloud
                use_cloud,  # use_cloud
                device[CONF_ID],  # id
            )
        except MideaError as err:
            _LOGGER.error(
                "Error while setting appliance id=%s ip=%s: %s",
                device[CONF_ID],
                device[CONF_IP_ADDRESS],
                err,
                exc_info=True,
            )
            appliance = None
        # For each appliance create a coordinator
        if appliance is not None:
            appliance.name = device[CONF_NAME]
            if not device.get(CONF_API_VERSION):
                device[CONF_API_VERSION] = appliance.version
                updated_conf = True
                _LOGGER.debug("Updating version for %s", appliance)
            if need_token and appliance.token and appliance.key:
                device[CONF_TOKEN] = appliance.token
                device[CONF_TOKEN_KEY] = appliance.key
                updated_conf = True
                _LOGGER.debug("Updating token for %s", appliance)
            coordinator = ApplianceUpdateCoordinator(self.hass, self, appliance, device)
            self.coordinators.append(coordinator)

        return updated_conf


class ApplianceUpdateCoordinator(DataUpdateCoordinator):
    """Single class to retrieve data from an appliance"""

    def __init__(
        self,
        hass: HomeAssistant,
        hub: Hub,
        appliance: LanDevice,
        config: dict[str, Any],
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="Midea appliance",
            update_method=self._async_appliance_refresh,
            update_interval=timedelta(seconds=APPLIANCE_REFRESH_INTERVAL),
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=APPLIANCE_REFRESH_COOLDOWN,
                immediate=True,
                function=self.async_refresh,
            ),
        )
        self.hub = hub
        self.appliance = appliance
        self.updating = {}
        self.wait_for_update = False
        self.use_cloud: bool = config.get(CONF_USE_CLOUD, False)

    def _cloud(self) -> MideaCloud | None:
        if self.use_cloud or self.hub.use_cloud:
            if not self.hub.cloud:
                raise UpdateFailed("Midea cloud API was not initialized")
            return self.hub.cloud
        return None

    async def _async_appliance_refresh(self) -> LanDevice:
        """Called to refresh appliance state"""

        if self.wait_for_update:
            return self.appliance
        try:
            if self.updating:
                self.wait_for_update = True
                _LOGGER.debug(
                    "Updating attributes for %s: %s for", self.appliance, self.updating
                )
                for attr in self.updating:
                    setattr(self.appliance.state, attr, self.updating[attr])
                self.updating = {}
                await self.hass.async_add_executor_job(
                    self.appliance.apply, self._cloud()
                )

            _LOGGER.debug("Refreshing %s", self.appliance)

            await self.hass.async_add_executor_job(
                self.appliance.refresh, self._cloud()
            )
        except MideaError as ex:
            raise UpdateFailed(str(ex)) from ex
        finally:
            self.wait_for_update = False
        return self.appliance

    def is_climate(self) -> bool:
        """True if appliance is air conditioner"""
        return AirConditionerAppliance.supported(self.appliance.type)

    def is_dehumidifier(self) -> bool:
        """True if appliance is dehumidifier"""
        return DehumidifierAppliance.supported(self.appliance.type)

    async def async_apply(self, args: dict) -> None:
        """Applies changes to device"""
        for key, value in args.items():
            self.updating[key] = value
        await self.async_request_refresh()


class ApplianceEntity(CoordinatorEntity):
    """Represents an appliance that gets data from a coordinator"""

    _unique_id_prefx = UNIQUE_DEHUMIDIFIER_PREFIX
    _name_suffix = ""

    def __init__(self, coordinator: ApplianceUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.appliance = coordinator.appliance
        self._attr_unique_id = f"{self.unique_id_prefix}{self.appliance.appliance_id}"
        self._attr_name = str(self.appliance.name or self.unique_id) + self.name_suffix
        self._applying = False

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_listener(self._updated_data))

    @callback
    def _updated_data(self):
        """Called when data has been updated by coordinator"""
        self.appliance = self.coordinator.appliance
        self._attr_available = self.appliance.online
        self.process_update()

    def process_update(self):
        """Allows additional processing after the coordinator updates data"""

    @final
    def dehumidifier(self) -> DehumidifierAppliance:
        """Returns state as dehumidifier"""
        return cast(DehumidifierAppliance, self.appliance.state)

    @final
    def airconditioner(self) -> AirConditionerAppliance:
        """Returns state as air conditioner"""
        return cast(AirConditionerAppliance, self.appliance.state)

    @property
    def name_suffix(self) -> str:
        """Suffix to append to entity name"""
        return self._name_suffix

    @property
    def unique_id_prefix(self) -> str:
        """Prefix for entity id"""
        strip = self.name_suffix.strip()
        if len(strip) == 0:
            return self._unique_id_prefx
        slug = slugify(strip)
        return f"{self._unique_id_prefx}{slug}_"

    @property
    def device_info(self) -> DeviceInfo:
        identifier = str(self.appliance.serial_number or self.appliance.appliance_id)
        return DeviceInfo(
            identifiers={(DOMAIN, str(identifier))},
            name=self.appliance.name,
            manufacturer="Midea",
            model=str(self.appliance.model),
            sw_version=self.appliance.firmware_version,
        )

    def apply(self, *args, **kwargs) -> None:
        """Applies changes to device"""
        if len(args) % 2 != 0:
            raise ValueError(f"Expecting attribute/value pairs, had {len(args)} items")
        aargs = {}
        for i in range(0, len(args), 2):
            aargs[args[i]] = args[i + 1]
        for key, value in kwargs.items():
            aargs[key] = value
        asyncio.run_coroutine_threadsafe(
            self.coordinator.async_apply(aargs), self.hass.loop
        ).result()
