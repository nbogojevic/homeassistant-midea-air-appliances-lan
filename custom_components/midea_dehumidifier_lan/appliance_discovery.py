"""The custom component for local network access to Midea appliances"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import ipaddress
from itertools import chain, cycle
import logging
from typing import Any, Iterator, cast

from homeassistant.core import CALLBACK_TYPE
from homeassistant.components.network import async_get_ipv4_broadcast_addresses
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_BROADCAST_ADDRESS,
    CONF_DEVICES,
    CONF_DISCOVERY,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_TYPE,
    CONF_UNIQUE_ID,
)
from homeassistant.helpers.event import async_track_time_interval
from midea_beautiful.lan import LanDevice

from custom_components.midea_dehumidifier_lan.appliance_coordinator import (
    ApplianceUpdateCoordinator,
)
from custom_components.midea_dehumidifier_lan.const import (
    CONF_TOKEN_KEY,
    DEFAULT_DISCOVERY_MODE,
    DEFAULT_SCAN_INTERVAL,
    DISCOVERY_BATCH_SIZE,
    DISCOVERY_IGNORE,
    DISCOVERY_LAN,
    DISCOVERY_MODE_EXPLANATION,
    DISCOVERY_WAIT,
    LOCAL_BROADCAST,
    NAME,
    UNKNOWN_IP,
)
from custom_components.midea_dehumidifier_lan.util import (
    AbstractHub,
    RedactedConf,
    address_ok,
    supported_appliance,
)

_LOGGER = logging.getLogger(__name__)


def empty_address_iterator():
    """No addresses to iterate"""
    yield from ()


def _add_if_discoverable(conf_addresses: list[str], device: dict[str, Any]):
    if device.get(CONF_DISCOVERY) != DISCOVERY_LAN:
        if address_ok(device[CONF_IP_ADDRESS]):
            conf_addresses.append(device[CONF_IP_ADDRESS])


@dataclass
class _ChangedDevice:
    device: LanDevice
    coordinator: ApplianceUpdateCoordinator


class ApplianceDiscoveryHelper:  # pylint: disable=too-many-instance-attributes
    """Utility class to discover Midea appliances on local network"""

    def __init__(
        self,
        hub: AbstractHub,
    ) -> None:
        self.hass = hub.hass
        self.hub = hub
        self.new_devices: list[LanDevice] = []
        self.changed_devices: list[_ChangedDevice] = []
        self.broadcast_addresses: list[str] = []
        self.address_iterator: Iterator[list[str]] = empty_address_iterator()
        self.notifed_addresses: set[str] = set()
        self.remove_discovery: CALLBACK_TYPE | None = None
        self.conf_addresses: list[str] = []

    def _admit_new(self) -> bool:
        """Admits new devices into configurations"""
        need_reload = False
        added_devices: list[dict[str, Any]] = []
        dev_confs = self.hub.config[CONF_DEVICES]
        for new in self.new_devices:
            for known in dev_confs:
                if self._admitted_known_device(known, new):
                    need_reload = True
                break
            else:
                added_devices.append(self._admit_not_known_device(new))
                need_reload = True

        if added_devices:
            dev_confs += added_devices
        return need_reload

    def _admit_not_known_device(self, new: LanDevice) -> dict[str, Any]:
        name = f"{new.model} {new.mac[-4] if new.mac else new.serial_number}"
        new_device = {
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
        return new_device

    def _admitted_known_device(self, known: dict[str, Any], new: LanDevice) -> bool:
        need_reload = False
        if known[CONF_UNIQUE_ID] == new.serial_number:
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
                known |= update
                need_reload = True
            elif new.address and known[CONF_DISCOVERY] != DISCOVERY_LAN:
                self._possible_lan_notification(new, known, new.address)

        return need_reload

    def _possible_lan_notification(
        self, device: LanDevice, known: dict[str, Any], address: str
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

    def _address_generator(self, batch_size: int = DISCOVERY_BATCH_SIZE):
        """Generator for one batch of ip addresses to scan"""
        net_addrs = []
        addr_count = 0
        for addr in self.conf_addresses:
            # If local broadcast address we don't need to expand it
            if addr == LOCAL_BROADCAST:
                continue
            # Get network corresponding to address
            net = ipaddress.IPv4Network(addr)
            # If network references a block:
            if net.num_addresses > 1:
                _LOGGER.debug("Block %s with %d addresses", net, net.num_addresses)
                # collect all hosts from the block
                net_addrs.append(net.hosts())
                addr_count += net.num_addresses

        # If we do have addresses to scan
        if net_addrs:
            # we will iterate over all of available addresses in batches
            # having batch_size items
            all_addrs = chain(*net_addrs)
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

    async def _async_run_discovery(self, devices: list[LanDevice]) -> None:
        """Trigger config flows for discovered devices."""

        dev_confs: list[dict[str, Any]] = self.hub.config[CONF_DEVICES]
        for dev_conf in dev_confs:
            dev_conf.setdefault(CONF_DISCOVERY, DEFAULT_DISCOVERY_MODE)
            dev_conf.setdefault(CONF_IP_ADDRESS, UNKNOWN_IP)

        self._iterate_devices(devices)

        need_reload = self._admit_new()
        devices_changed = self._merge_with_configuration()

        if devices_changed or need_reload:
            _LOGGER.debug("Config entry needs to be updated")
            self.hass.config_entries.async_update_entry(
                entry=self.hub.config_entry,
                data=self.hub.config,
            )
        if need_reload:
            _LOGGER.debug("Config entry needs to be reloaded")
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.hub.config_entry.entry_id)
            )

    def _iterate_devices(self, devices: list[LanDevice]):
        self.new_devices.clear()
        self.changed_devices.clear()
        for device in devices:
            if not device.address:
                continue
            coordinator = next(
                (
                    cast(ApplianceUpdateCoordinator, coord)
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
                        coordinator.name,
                        device.address,
                    )
                    self.changed_devices.append(_ChangedDevice(device, coordinator))
            elif supported_appliance(self.hub.config, device):
                _LOGGER.debug("Discovered new device %s", device)
                self.new_devices.append(device)

    def _merge_with_configuration(self: ApplianceDiscoveryHelper) -> bool:
        """Merges list of changed devices with existing config entry configuration"""
        dev_confs: list[dict[str, Any]] = self.hub.config[CONF_DEVICES]
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

    def _setup(self) -> None:
        """Initializes address iterator.
        Address iterator allows iterating over adresses to broadcast to.
        It will iterate over all addresses in specified ranges.
        """
        self.notifed_addresses.clear()
        self.conf_addresses.clear()
        has_discoverable = False
        device: dict[str, Any]
        for device in self.hub.config[CONF_DEVICES]:
            if _add_if_discoverable(self.conf_addresses, device):
                has_discoverable = True
        for coordinator in self.hub.coordinators:
            if not coordinator.available:
                if _add_if_discoverable(self.conf_addresses, coordinator.device):
                    has_discoverable = True
        self.conf_addresses += [
            item
            for item in self.hub.config.get(CONF_BROADCAST_ADDRESS, []) or []
            if item and item != LOCAL_BROADCAST
        ]
        self.broadcast_addresses = [LOCAL_BROADCAST]
        for addr in self.conf_addresses:
            net = ipaddress.IPv4Network(addr)
            self.broadcast_addresses.append(str(net.broadcast_address))

        if has_discoverable and self.conf_addresses:
            _LOGGER.debug("Discovery via configured addresses %s", self.conf_addresses)
            self.address_iterator = cycle(self._address_generator())
        else:
            self.address_iterator = empty_address_iterator()

    def start(self) -> None:
        """Starts periodic disovery of devices"""
        self.stop()
        try:
            self._setup()
            scan_interval = self.hub.config.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )
            if scan_interval:
                _LOGGER.debug(
                    "Starting periodic discovery with interval %s minute(s),"
                    " broadcast %s, configured %s",
                    scan_interval,
                    self.broadcast_addresses,
                    self.conf_addresses,
                )
                self.remove_discovery = async_track_time_interval(
                    self.hass, self._async_discover, timedelta(minutes=scan_interval)
                )
        except Exception as ex:
            _LOGGER.error(
                "Unable to setup up periodic discovery."
                " Please remove integration and then reinstall it to check if problem"
                " can be fixed."
                " Cause: %s"
                " Configuration: %s",
                ex,
                RedactedConf(self.hub.config),
            )
            self.stop()
            raise ex

    def stop(self) -> None:
        """Stops periodic disovery of devices"""
        if self.remove_discovery:
            _LOGGER.debug("Stopping periodic discovery")

            self.remove_discovery()
            self.remove_discovery = None

    async def _async_discover(self, _: datetime) -> None:
        """Discover Midea appliances on configured network interfaces."""

        addresses = list(address for address in self.broadcast_addresses)
        if new_addresses := next(self.address_iterator, None):
            addresses += new_addresses
        if not addresses:
            iface_broadcast = await async_get_ipv4_broadcast_addresses(self.hass)
            addresses += [str(address) for address in iface_broadcast]
        _LOGGER.debug("Initiated discovery via %s", addresses)
        result = self.hub.client.find_appliances(None, addresses, retries=1, timeout=1)
        if result:
            await self._async_run_discovery(result)
