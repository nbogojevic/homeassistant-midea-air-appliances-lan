"""
The custom component for local network access to Midea appliances
"""

from __future__ import annotations
import asyncio

from dataclasses import dataclass
from datetime import timedelta
import ipaddress
import itertools
import logging
from typing import Any, Final, Iterator, cast, final

from homeassistant.components.network import async_get_ipv4_broadcast_addresses
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_BROADCAST_ADDRESS,
    CONF_DEVICES,
    CONF_DISCOVERY,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_TYPE,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import slugify

from midea_beautiful.appliance import AirConditionerAppliance, DehumidifierAppliance
from midea_beautiful.exceptions import AuthenticationError, MideaError
from midea_beautiful.lan import LanDevice

from custom_components.midea_dehumidifier_lan.api import (
    MideaClient,
    is_climate,
    is_dehumidifier,
    supported_appliance,
)
from custom_components.midea_dehumidifier_lan.const import (
    APPLIANCE_REFRESH_COOLDOWN,
    APPLIANCE_REFRESH_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    CONF_APPID,
    CONF_APPKEY,
    CONF_TOKEN_KEY,
    DEFAULT_DISCOVERY_MODE,
    DISCOVERY_CLOUD,
    DISCOVERY_IGNORE,
    DISCOVERY_LAN,
    DISCOVERY_MODE_EXPLANATION,
    DISCOVERY_WAIT,
    DOMAIN,
    LOCAL_BROADCAST,
    NAME,
    UNIQUE_DEHUMIDIFIER_PREFIX,
    UNKNOWN_IP,
)


_LOGGER = logging.getLogger(__name__)

_DISCOVER_BATCH_SIZE: Final = 64


def empty_address_iterator():
    """No addresses to iterate"""
    yield from ()


def _redact_key(redacted_data: dict[str, Any], key: str, char="*"):
    if redacted_data.get(key):
        redacted_data[key] = char * len(redacted_data[key])


def redacted_conf(data: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive information from configuration"""
    conf = {**data}
    if conf.get(CONF_USERNAME):
        old_username = conf[CONF_USERNAME]
        _redact_key(conf, CONF_USERNAME)
        conf[CONF_USERNAME][0] = old_username[0]
    _redact_key(conf, CONF_PASSWORD)
    if conf.get(CONF_DEVICES):
        for device in conf[CONF_DEVICES]:
            _redact_key(device, CONF_TOKEN)
            _redact_key(device, CONF_TOKEN_KEY)
    return conf


class _ApplianceDiscoveryHelper:
    def __init__(self, hub: Hub) -> None:
        self.hub = hub
        self.hass = hub.hass
        self.new_devices: list[LanDevice] = []
        self.changed_devices: list[_ChangedDevice] = []
        self.broadcast_addresses: list[str] = []
        self.address_iterator: Iterator[list[str]] = empty_address_iterator()
        self.notifed_addresses: set[str] = set()

    @staticmethod
    def iterator(conf_addresses, batch_size: int = _DISCOVER_BATCH_SIZE):
        """Generator for one batch of ip addresses to scan"""
        net_addrs = []
        addr_count = 0
        for addr in conf_addresses:
            # If local broadcast address we don't need to expand it
            if addr == LOCAL_BROADCAST:
                continue
            # Get network corresponding to address
            net = ipaddress.IPv4Network(addr)
            # If network references a block:
            if net.num_addresses > 1:
                _LOGGER.debug(
                    "Got network block %s with %d addresses", net, net.num_addresses
                )
                # collect all hosts from the block
                net_addrs.append(net.hosts())
                addr_count += net.num_addresses

        # If we do have addresses to scan
        if net_addrs:
            # we will iterate over all of available addresses in batches
            # having batch_size items
            all_addrs = itertools.chain(*net_addrs)
            for _ in range(0, addr_count, batch_size):
                yield list(
                    # We use filter to remove empty addresses
                    filter(
                        None,
                        map(
                            (lambda _: (x := next(all_addrs)) and str(x)),
                            range(batch_size),
                        ),
                    )
                )

    def admit_new(self, dev_confs: list[dict]) -> bool:
        """Admits new devices into configurations"""
        need_reload = False
        added_devices = []
        for new in self.new_devices:
            for known in dev_confs:
                if known[CONF_UNIQUE_ID] == new.serial_number:
                    if self._admit_known_device(known, new):
                        need_reload = True
                    break
            else:
                name = f"{new.model} {new.mac[-4] if new.mac else new.serial_number}"
                update = {
                    CONF_DISCOVERY: DISCOVERY_IGNORE,
                    CONF_API_VERSION: new.version,
                    CONF_ID: new.appliance_id,
                    CONF_IP_ADDRESS: new.address,
                    CONF_NAME: name,
                    CONF_TOKEN_KEY: new.key,
                    CONF_TOKEN: new.token,
                    CONF_TYPE: new.type,
                    CONF_UNIQUE_ID: new.serial_number,
                }
                added_devices.append(update)
                need_reload = True

                _LOGGER.debug("Found unknown device %s at %s.", name, new.address)
                msg = (
                    f"Found previously unknown device {name} found on {new.address}."
                    f" [Check it out.](/config/integrations)"
                )
                self.hass.components.persistent_notification.async_create(
                    title=NAME,
                    message=msg,
                    notification_id=f"midea_unknown_{new.serial_number}",
                )
        if added_devices:
            dev_confs += added_devices
        return need_reload

    def _admit_known_device(self, known: dict[str, Any], new: LanDevice) -> bool:
        need_reload = False
        if known[CONF_DISCOVERY] == DISCOVERY_WAIT:
            update = {
                CONF_DISCOVERY: DISCOVERY_LAN,
                CONF_API_VERSION: new.version,
                CONF_ID: new.appliance_id,
                CONF_IP_ADDRESS: new.address,
                CONF_TOKEN_KEY: new.key,
                CONF_TOKEN: new.token,
                CONF_TYPE: new.type,
                CONF_UNIQUE_ID: new.serial_number,
            }
            _LOGGER.debug(
                "Updating discovered device %s, previous conf %s, conf update %s",
                new,
                known,
                update,
            )

            msg = (
                "Device %(name)s,"
                " which was waiting to be discovered,"
                " was found on address %(address)s."
                " It will now be activated."
            ) % {
                "name": known[CONF_NAME],
                "address": new.address,
            }
            self.hass.components.persistent_notification.async_create(
                title=NAME,
                message=msg,
                notification_id=f"midea_wait_discovery_{new.serial_number}",
            )
            known.update(update)
            need_reload = True
        elif new.address and known[CONF_DISCOVERY] != DISCOVERY_LAN:
            self._possible_lan_notification(new, known, new.address)

        return need_reload

    def _possible_lan_notification(
        self,
        device: LanDevice,
        known: dict[str, Any],
        address: str,
    ):
        if address not in self.notifed_addresses:
            _LOGGER.warning(
                "Device %s in mode %s found on address %s. "
                " It can be configured for local network access.",
                known[CONF_NAME],
                known[CONF_DISCOVERY],
                address,
            )
            self.notifed_addresses.add(address)

            discovery_label = DISCOVERY_MODE_EXPLANATION.get(
                known[CONF_DISCOVERY], known[CONF_DISCOVERY]
            )
            msg = (
                "Device %(name)s,"
                " which is %(discovery_label)s,"
                " was found on address %(address)s."
                " It can be configured for local network access."
                " [Check it out.](/config/integrations)"
            ) % {
                "name": known[CONF_NAME],
                "discovery_label": discovery_label,
                "address": address,
            }

            self.hass.components.persistent_notification.async_create(
                title=NAME,
                message=msg,
                notification_id=f"midea_non_lan_discovery_{device.serial_number}",
            )

    async def async_discover(self, devices: list[LanDevice]) -> None:
        """Trigger config flows for discovered devices."""

        conf = self.hub.data
        dev_confs: list[dict] = []
        for dev_data in conf[CONF_DEVICES]:
            dev_conf = {**dev_data}
            dev_conf.setdefault(CONF_DISCOVERY, DEFAULT_DISCOVERY_MODE)
            dev_conf.setdefault(CONF_IP_ADDRESS, UNKNOWN_IP)
            dev_confs.append(dev_conf)
        conf[CONF_DEVICES] = dev_confs

        self._iterate_devices(devices)

        need_reload = self.admit_new(dev_confs)
        devices_changed = self.merge_with_configuration(dev_confs)

        if devices_changed or need_reload:
            _LOGGER.debug("Config entry needs to be updated")
            self.hass.config_entries.async_update_entry(
                entry=self.hub.config_entry,
                data=self.hub.data,
            )
        if need_reload:
            _LOGGER.debug("Config entry needs to be reloaded")
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.hub.config_entry.entry_id)
            )

    def _iterate_devices(
        self,
        devices: list[LanDevice],
    ):
        self.new_devices = []
        self.changed_devices = []
        for device in devices:
            if not device.address:
                continue
            coordinator = next(
                (
                    coord
                    for coord in self.hub.coordinators
                    if coord.appliance.serial_number == device.serial_number
                ),
                None,
            )
            if coordinator:
                # If address changed, we need to handle it
                if device.address and device.address != coordinator.appliance.address:
                    _LOGGER.debug(
                        "Device %s changed address to %s",
                        coordinator.appliance,
                        device.address,
                    )
                    self.changed_devices.append(_ChangedDevice(device, coordinator))
            elif supported_appliance(self.hub.data, device):
                _LOGGER.debug("Discovered new device %s", device)
                self.new_devices.append(device)
        _LOGGER.debug("Changed configuration for devices: %s", self.changed_devices)
        _LOGGER.debug("Newly discovered new devices: %s", self.new_devices)

    def merge_with_configuration(
        self: _ApplianceDiscoveryHelper,
        dev_confs: list[dict],
    ) -> bool:
        """Merges list of changed devices with existing config entry configuration"""
        updated_conf = False
        for changed in self.changed_devices:
            for known in dev_confs:
                coordinator = changed.coordinator
                device = changed.device
                if known[CONF_UNIQUE_ID] == coordinator.appliance.serial_number:
                    coordinator.appliance.address = device.address
                    known[CONF_IP_ADDRESS] = device.address
                    updated_conf = True
                    if device.address and known[CONF_DISCOVERY] != DISCOVERY_LAN:
                        self._possible_lan_notification(
                            coordinator.appliance,
                            known,
                            device.address,
                        )
                    break

        return updated_conf

    def setup(self, data: dict[str, Any]):
        """
        Initializes address iterator.
        Address iterator allows iterating over adresses to broadcast to.
        It will iterate over all addresses in specified ranges.
        """
        self.notifed_addresses.clear()
        conf_addresses: list[str] = []
        has_discovrable = False
        device: dict[str, Any]
        for device in data[CONF_DEVICES]:
            if device.get(CONF_DISCOVERY) != DISCOVERY_LAN:
                has_discovrable = True
                if device[CONF_IP_ADDRESS] and device[CONF_IP_ADDRESS] != UNKNOWN_IP:
                    conf_addresses.append(device[CONF_IP_ADDRESS])
        conf_addresses += [
            item
            for item in data.get(CONF_BROADCAST_ADDRESS, [])
            if item and item != LOCAL_BROADCAST
        ]
        self.broadcast_addresses = [LOCAL_BROADCAST]
        for addr in conf_addresses:
            net = ipaddress.IPv4Network(addr)
            self.broadcast_addresses.append(str(net.broadcast_address))

        _LOGGER.debug("Discovery via broadcast addresses %s", self.broadcast_addresses)

        if has_discovrable and conf_addresses:
            _LOGGER.debug("Discovery via configured addresses %s", conf_addresses)
            self.address_iterator = itertools.cycle(
                _ApplianceDiscoveryHelper.iterator(conf_addresses, _DISCOVER_BATCH_SIZE)
            )
        else:
            self.address_iterator = empty_address_iterator()


@dataclass
class _ChangedDevice:
    device: LanDevice
    coordinator: ApplianceUpdateCoordinator


class Hub:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Central class for interacting with appliances"""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.client = MideaClient()
        self.cloud = None
        self.config_entry = config_entry
        self.coordinators: list[ApplianceUpdateCoordinator] = []
        self.data = {}
        self.errors = []
        self.failed_setup = []
        self.hass = hass
        self.remove_discovery: CALLBACK_TYPE | None = None
        self.updated_conf = False
        self.discovery_helper = _ApplianceDiscoveryHelper(self)

    async def _setup_discovery(self) -> None:
        """Startup-time setup"""

        if self.remove_discovery:
            _LOGGER.debug("Removed periodic discovery")
            self.remove_discovery()
            self.remove_discovery = None

        self.discovery_helper.setup(self.data)
        self._setup_discovery_callback()

    def _setup_discovery_callback(self):
        scan_interval = self.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        if scan_interval:
            _LOGGER.debug(
                "Staring periodic discovery with interval %s minute(s)", scan_interval
            )

            self.remove_discovery = async_track_time_interval(
                self.hass, self._async_discover, timedelta(minutes=scan_interval)
            )

    async def async_unload(self) -> None:
        """Stops discovery and coordinators"""
        _LOGGER.debug("Unloading hub")
        if self.remove_discovery:
            _LOGGER.debug("Removed periodic discovery %s", self.remove_discovery)

            self.remove_discovery()
            self.remove_discovery = None
        for coord in self.coordinators:
            # Stop coordinators
            coord.update_interval = None

    async def async_setup(self) -> None:
        """
        Sets up appliances and creates an update coordinator for
        each one
        """
        self.data = {**self.config_entry.data}
        self.errors = {}
        self.updated_conf = False

        devices = []
        for device_conf in self.data[CONF_DEVICES]:
            device = {**device_conf}
            await self._process_appliance(device)
            devices.append(device)
        self.data[CONF_DEVICES] = devices
        for coordinator in self.coordinators:
            await coordinator.async_config_entry_first_refresh()

        if self.updated_conf:
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self.data
            )

        await self._setup_discovery()

        if self.errors:
            raise ConfigEntryNotReady(str(self.errors))

    async def _async_discover(self, *_: Any) -> None:
        """Discover Midea appliances on configured network interfaces."""
        addresses = list(
            address for address in self.discovery_helper.broadcast_addresses
        )
        if new_addresses := next(self.discovery_helper.address_iterator, None):
            addresses += new_addresses
        if not addresses:
            iface_broadcast = await async_get_ipv4_broadcast_addresses(self.hass)
            addresses += [str(address) for address in iface_broadcast]
        _LOGGER.debug("Initiated discovery via %s", addresses)
        if result := self.client.find_appliances(
            addresses=addresses, retries=1, timeout=1
        ):
            await self.discovery_helper.async_discover(result)

    async def _process_appliance(self, device: dict):
        discovery_mode = device.get(CONF_DISCOVERY)
        # We are waiting for appliance to come online
        if discovery_mode == DISCOVERY_IGNORE:
            _LOGGER.debug("Ignored appliance for discovery %s", device)
            return
        if discovery_mode == DISCOVERY_WAIT:
            _LOGGER.debug("Waiting for appliance discovery %s", device)
            return
        use_cloud = discovery_mode == DISCOVERY_CLOUD
        need_cloud = use_cloud
        lan_mode = discovery_mode == DISCOVERY_LAN
        version = device.get(CONF_API_VERSION, 3)
        need_token = (
            discovery_mode == DISCOVERY_LAN
            and version >= 3
            and (not device.get(CONF_TOKEN) or not device.get(CONF_TOKEN_KEY))
        )
        if need_token:
            _LOGGER.debug(
                "Appliance %s, id=%s has no token,"
                " trying to obtain it from Midea cloud API",
                device.get(CONF_NAME),
                device.get(CONF_ID),
            )
            need_cloud = True
        if need_cloud and self.cloud is None:
            try:
                self.cloud = await self.hass.async_add_executor_job(
                    self.client.connect_to_cloud,
                    self.data[CONF_USERNAME],
                    self.data[CONF_PASSWORD],
                    self.data[CONF_APPKEY],
                    self.data[CONF_APPID],
                )
            except AuthenticationError as ex:
                raise ConfigEntryAuthFailed(
                    f"Unable to login to Midea cloud {ex}"
                ) from ex
            except Exception as ex:  # pylint: disable=broad-except
                self.errors[device[CONF_UNIQUE_ID]] = str(ex)
                return

        try:
            ip_address = device[CONF_IP_ADDRESS] if lan_mode else None
            if not ip_address and not use_cloud:
                _LOGGER.error(
                    "Missing ip_address and cloud discovery not used: %s."
                    "Will fall-back to cloud discovery, full configuration %s",
                    redacted_conf(device),
                    redacted_conf(self.data),
                )
                use_cloud = True
            appliance = await self.hass.async_add_executor_job(
                self.client.appliance_state,
                device[CONF_IP_ADDRESS] if lan_mode else None,  # ip
                device.get(CONF_TOKEN),  # token
                device.get(CONF_TOKEN_KEY),  # key
                self.cloud,  # cloud
                use_cloud,  # use_cloud
                device[CONF_ID],  # id
            )

            self._create_coordinator(appliance, device, need_token)
        except Exception as ex:  # pylint: disable=broad-except
            self.errors[device[CONF_UNIQUE_ID]] = str(ex)
            _LOGGER.error(
                "Error while setting appliance %s, full configuration %s, cause %s",
                redacted_conf(device),
                redacted_conf(self.data),
                ex,
                exc_info=True,
            )

    def _create_coordinator(self, appliance: LanDevice, device: dict, need_token: bool):
        appliance.name = device[CONF_NAME]
        if not device.get(CONF_API_VERSION):
            device[CONF_API_VERSION] = appliance.version
            self.updated_conf = True
            _LOGGER.debug("Updating version for %s", appliance)
        if need_token and appliance.token and appliance.key:
            device[CONF_TOKEN] = appliance.token
            device[CONF_TOKEN_KEY] = appliance.key
            self.updated_conf = True
            _LOGGER.debug("Updating token for %s", appliance)
        coordinator = ApplianceUpdateCoordinator(self.hass, self, appliance, device)

        _LOGGER.debug("Created coordinator for %s", device)
        self.coordinators.append(coordinator)


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
            name=appliance.name,
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
        self.discovery_mode = config.get(CONF_DISCOVERY, DISCOVERY_IGNORE)
        self.use_cloud: bool = self.discovery_mode == DISCOVERY_CLOUD

    def _cloud(self):
        if self.use_cloud:
            if not self.hub.cloud:
                raise UpdateFailed(
                    f"Midea cloud API was not initialized, {self.appliance}"
                    f" configuration={redacted_conf(self.hub.data)}"
                )
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
        return is_climate(self.appliance)

    def is_dehumidifier(self) -> bool:
        """True if appliance is dehumidifier"""
        return is_dehumidifier(self.appliance)

    @final
    def dehumidifier(self) -> DehumidifierAppliance:
        """Returns state as dehumidifier"""
        return cast(DehumidifierAppliance, self.appliance.state)

    @final
    def airconditioner(self) -> AirConditionerAppliance:
        """Returns state as air conditioner"""
        return cast(AirConditionerAppliance, self.appliance.state)

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
        self._attr_unique_id = f"{self.unique_id_prefix}{self.appliance.serial_number}"
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
        identifier = str(self.appliance.serial_number or self.appliance.serial_number)
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
