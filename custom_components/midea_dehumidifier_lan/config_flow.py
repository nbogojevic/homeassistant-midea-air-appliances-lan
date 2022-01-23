"""Config flow for Midea Air Appliance (Local) integration."""
from __future__ import annotations

import ipaddress
import logging
from typing import Any, Final

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import (
    ATTR_ID,
    ATTR_NAME,
    CONF_API_VERSION,
    CONF_BROADCAST_ADDRESS,
    CONF_DEVICES,
    CONF_DISCOVERY,
    CONF_ID,
    CONF_INCLUDE,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_TYPE,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowHandler, FlowResult
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from midea_beautiful.cloud import MideaCloud
from midea_beautiful.exceptions import (
    AuthenticationError,
    CloudAuthenticationError,
    CloudError,
    MideaError,
    MideaNetworkError,
    ProtocolError,
    RetryLaterError,
)
from midea_beautiful.lan import LanDevice
from midea_beautiful.midea import (
    APPLIANCE_TYPE_AIRCON,
    APPLIANCE_TYPE_DEHUMIDIFIER,
    DEFAULT_APP_ID,
    DEFAULT_APPKEY,
    SUPPORTED_APPS,
)

from custom_components.midea_dehumidifier_lan import Hub
from custom_components.midea_dehumidifier_lan.api import (
    MideaClient,
    supported_appliance,
)
from custom_components.midea_dehumidifier_lan.const import (
    APPLIANCE_SCAN_INTERVALS,
    CONF_ADVANCED_SETTINGS,
    CONF_APPID,
    CONF_APPKEY,
    CONF_MOBILE_APP,
    CONF_TOKEN_KEY,
    CURRENT_CONFIG_VERSION,
    DEFAULT_APP,
    DEFAULT_DISCOVERY_MODE,
    DEFAULT_PASSWORD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
    DISCOVERY_CLOUD,
    DISCOVERY_IGNORE,
    DISCOVERY_LAN,
    DISCOVERY_MODE_LABELS,
    DISCOVERY_WAIT,
    DOMAIN,
    LOCAL_BROADCAST,
    UNKNOWN_IP,
)

_LOGGER = logging.getLogger(__name__)


def _appliance_schema(
    name: str,
    address: str = UNKNOWN_IP,
    token: str = "",
    token_key: str = "",
    discovery_mode=DISCOVERY_WAIT,
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_DISCOVERY, default=str(discovery_mode)): vol.In(
                DISCOVERY_MODE_LABELS
            ),
            vol.Optional(
                CONF_IP_ADDRESS,
                default=address or UNKNOWN_IP,
            ): cv.string,
            vol.Required(CONF_NAME, default=name): cv.string,
            vol.Optional(CONF_TOKEN, default=token or ""): cv.string,
            vol.Optional(CONF_TOKEN_KEY, default=token_key or ""): cv.string,
        }
    )


# pylint: disable=too-many-arguments
def _advanced_settings_schema(
    username: str = "",
    password: str = "",
    appkey: str = "",
    appid: int = None,
    broadcast_address: str = "",
    appliances: list[str] = None,
) -> vol.Schema:
    appliances = appliances or [APPLIANCE_TYPE_DEHUMIDIFIER]
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=username): cv.string,
            vol.Required(CONF_PASSWORD, default=password): cv.string,
            vol.Required(CONF_APPKEY, default=appkey): cv.string,
            vol.Required(CONF_APPID, default=appid): cv.positive_int,
            vol.Optional(CONF_BROADCAST_ADDRESS, default=broadcast_address): cv.string,
            vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.In(
                APPLIANCE_SCAN_INTERVALS
            ),
            vol.Required(CONF_INCLUDE, default=appliances): vol.All(
                cv.multi_select(
                    {
                        APPLIANCE_TYPE_AIRCON: "Air conditioner",
                        APPLIANCE_TYPE_DEHUMIDIFIER: "Dehumidifier",
                    }
                ),
                vol.Length(min=1, msg="Must select at least one appliance category"),
            ),
        }
    )


def _reauth_schema(
    password: str,
    appkey: str,
    appid: int,
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_PASSWORD, default=password): cv.string,
            vol.Required(CONF_APPKEY, default=appkey): cv.string,
            vol.Required(CONF_APPID, default=appid): cv.positive_int,
        }
    )


def _user_schema(username: str, password: str, app: str) -> vol.Schema:

    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=username): cv.string,
            vol.Required(CONF_PASSWORD, default=password): cv.string,
            vol.Optional(CONF_MOBILE_APP, default=app): vol.In(SUPPORTED_APPS.keys()),
            vol.Required(CONF_ADVANCED_SETTINGS, default=False): bool,
        }
    )


# pylint: disable=too-many-instance-attributes
class _MideaFlow(FlowHandler):
    """Base class for Midea data flows"""

    def __init__(self) -> None:
        super().__init__()
        self.appliance_idx = -1
        self.appliances: list[LanDevice] = []
        self.client: Final = MideaClient()
        self.cloud: MideaCloud | None = None  # type: ignore
        self.conf = {}
        self.config_entry: ConfigEntry | None = None
        self.devices_conf: list[dict[str, Any]] = []
        self.discovered_appliances: list[LanDevice | None] = []
        self.error_cause: str = ""
        self.errors: dict[str, Any] = {}
        self.indexes_to_process = []

    def _process_exception(self: _MideaFlow, ex: Exception) -> None:
        if isinstance(ex, _FlowException):
            self.error_cause = str(ex.cause)
            self.errors["base"] = ex.message
        elif isinstance(ex, CloudAuthenticationError):
            self.error_cause = f"{ex.error_code} - {ex.message}"
            self.errors["base"] = "invalid_auth"
        elif isinstance(ex, CloudError):
            self.error_cause = f"{ex.error_code} - {ex.message}"
            self.errors["base"] = "midea_client"
        elif isinstance(ex, RetryLaterError):
            self.error_cause = f"{ex.error_code} - {ex.message}"
            self.errors["base"] = "retry_later"
        elif isinstance(ex, MideaError):
            self.error_cause = f"{ex.message}"
            self.errors["base"] = "midea_client"
        else:
            raise ex

    def _connect_to_cloud(self: _MideaFlow, extra_conf: dict[str, Any] = None) -> None:
        """Validates that cloud credentials are valid"""
        extra_conf = extra_conf or {}
        try:
            self.cloud = self.client.connect_to_cloud(
                account=self.conf[CONF_USERNAME],
                password=extra_conf.get(CONF_PASSWORD, self.conf[CONF_PASSWORD]),
                appkey=extra_conf.get(CONF_APPKEY, self.conf[CONF_APPKEY]),
                appid=extra_conf.get(CONF_APPID, self.conf[CONF_APPID]),
            )
        except MideaError as ex:
            raise _FlowException("no_cloud", str(ex)) from ex

    def _validate_appliance(
        self: _MideaFlow, appliance: LanDevice, device_conf: dict
    ) -> LanDevice | None:
        """
        Validates that appliance configuration is correct and matches physical
        device
        """
        discovery_mode = device_conf.get(CONF_DISCOVERY, DEFAULT_DISCOVERY_MODE)
        if discovery_mode == DISCOVERY_IGNORE:
            _LOGGER.debug("Ignoring appliance %s", appliance)
            return None
        if discovery_mode == DISCOVERY_WAIT:
            _LOGGER.debug(
                "Attempt to discover appliance %s will be made later",
                appliance,
            )
            return None
        try:
            if discovery_mode == DISCOVERY_CLOUD:
                discovered = self.client.appliance_state(
                    appliance_id=appliance.appliance_id,
                    cloud=self.cloud,
                    use_cloud=True,
                )
            else:  # DISCOVERY_LAN
                if appliance.address == UNKNOWN_IP:
                    raise _FlowException("invalid_ip_address", appliance.address)
                try:
                    ipaddress.IPv4Address(appliance.address)
                except Exception as ex:
                    _LOGGER.debug(
                        "Invalid appliance address %s", appliance.address, exc_info=True
                    )
                    raise _FlowException(
                        "invalid_ip_address", appliance.address
                    ) from ex
                discovered = self.client.appliance_state(
                    address=appliance.address,
                    cloud=self.cloud,
                )
        except ProtocolError as ex:
            raise _FlowException("connection_error", str(ex)) from ex
        except AuthenticationError as ex:
            raise _FlowException("invalid_auth", str(ex)) from ex
        except MideaNetworkError as ex:
            raise _FlowException("cannot_connect", str(ex)) from ex
        except MideaError as ex:
            raise _FlowException("not_discovered", str(ex)) from ex
        if discovered is None:
            raise _FlowException("not_discovered", appliance.address)
        return discovered

    async def _async_add_entry(self: _MideaFlow) -> FlowResult:
        supported_devices_conf = []
        for i, appliance in enumerate(self.appliances):
            if not supported_appliance(self.conf, appliance):
                continue
            device_conf = self.devices_conf[i]

            if device_conf.get(CONF_DISCOVERY) != DISCOVERY_IGNORE:
                device_conf.update(
                    {
                        CONF_API_VERSION: appliance.version,
                        CONF_ID: appliance.appliance_id,
                        CONF_IP_ADDRESS: (
                            appliance.address
                            or device_conf[CONF_IP_ADDRESS]
                            or UNKNOWN_IP
                        ),
                        CONF_NAME: appliance.name,
                        CONF_TOKEN_KEY: appliance.key,
                        CONF_TOKEN: appliance.token,
                        CONF_TYPE: appliance.type,
                        CONF_UNIQUE_ID: appliance.serial_number,
                    }
                )
                suggested_discovery = (
                    DISCOVERY_LAN
                    if device_conf[CONF_IP_ADDRESS] != UNKNOWN_IP
                    else DISCOVERY_WAIT
                )
                device_conf.get(CONF_DISCOVERY, suggested_discovery)
                supported_devices_conf.append(device_conf)
        self.devices_conf = supported_devices_conf
        self.conf[CONF_DEVICES] = self.devices_conf

        # Remove not used elements
        self.conf.pop(CONF_ADVANCED_SETTINGS, None)
        self.conf.pop(CONF_MOBILE_APP, None)
        _LOGGER.debug("Congfigured: %s", self.conf)
        if self.config_entry:
            _LOGGER.debug("Updating configuration data %s", self.conf)
            self.hass.config_entries.async_update_entry(
                entry=self.config_entry,
                data=self.conf,
            )
            # Reload the config entry otherwise devices will remain unavailable
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )

        if len(self.devices_conf) == 0:
            _LOGGER.debug("There are no configured appliances %s", self.conf)
            return self.async_abort(reason="no_configured_devices")
        _LOGGER.debug("Creating configuration data %s", self.conf)
        return self.async_create_entry(
            title="Midea Air Appliance",
            data=self.conf,
        )

    async def _async_step_appliance(  # pylint: disable=too-many-locals
        self: _MideaFlow,
        step_id: str,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Manage an appliances"""

        errors: dict = {}
        self.error_cause = ""
        _LOGGER.debug("Processing step %d", self.appliance_idx)
        appliance = self.appliances[self.appliance_idx]
        device_conf = self.devices_conf[self.appliance_idx]
        discovery_mode = device_conf.get(CONF_DISCOVERY, DEFAULT_DISCOVERY_MODE)
        ip_address = appliance.address or UNKNOWN_IP
        if user_input is not None:
            try:
                _LOGGER.debug("appliance user_input %s", user_input)

                ip_address = user_input.get(
                    CONF_IP_ADDRESS, device_conf.get(CONF_IP_ADDRESS, UNKNOWN_IP)
                )
                self._check_ip_address_unique(ip_address)

                discovery_mode = user_input.get(CONF_DISCOVERY, discovery_mode)
                if discovery_mode not in [
                    DISCOVERY_WAIT,
                    DISCOVERY_LAN,
                    DISCOVERY_IGNORE,
                    DISCOVERY_CLOUD,
                ]:
                    discovery_mode = (
                        DISCOVERY_LAN
                        if ip_address and ip_address != UNKNOWN_IP
                        else DISCOVERY_CLOUD
                    )
                device_conf[CONF_DISCOVERY] = discovery_mode

                appliance.address = ip_address
                appliance.name = user_input.get(CONF_NAME, appliance.name)
                appliance.token = user_input.get(CONF_TOKEN, "")
                appliance.key = user_input.get(CONF_TOKEN_KEY, "")

                if not self.cloud:
                    await self.hass.async_add_executor_job(self._connect_to_cloud)

                discovered = await self.hass.async_add_executor_job(
                    self._validate_appliance,
                    appliance,
                    device_conf,
                )
                self.discovered_appliances[self.appliance_idx] = discovered

                if not self.indexes_to_process:
                    self._update_appliances_after_flow()

                    return await self._async_add_entry()

                self.appliance_idx = self.indexes_to_process.pop(0)
                appliance = self.appliances[self.appliance_idx]
                device_conf = self.devices_conf[self.appliance_idx]
                ip_address = appliance.address or device_conf[CONF_IP_ADDRESS]
                user_input = None
                discovery_mode = DEFAULT_DISCOVERY_MODE

            except _FlowException as ex:
                self.error_cause = str(ex.cause)
                errors["base"] = ex.message

            except Exception as ex:  # pylint: disable=broad-except
                self._process_exception(ex)

        name = appliance.name
        extra = {
            "index": str(self.appliance_idx + 1),
            "count": str(len(self.appliances)),
            "serial_number": appliance.serial_number,
        }
        placeholders = self._placeholders(appliance, extra)
        schema_arg = {
            "name": name,
            "address": device_conf.get(CONF_IP_ADDRESS, ip_address),
            "token": device_conf.get(CONF_TOKEN, appliance.token),
            "token_key": device_conf.get(CONF_TOKEN_KEY, appliance.key),
            "discovery_mode": device_conf.get(CONF_DISCOVERY, discovery_mode),
        }
        _LOGGER.debug("appliance form arguments %s", schema_arg)
        schema = _appliance_schema(**schema_arg)
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            description_placeholders=placeholders,
            errors=errors,
            last_step=len(self.indexes_to_process) == 0,
        )

    def _check_ip_address_unique(self, ip_address) -> None:
        if ip_address and ip_address != UNKNOWN_IP:
            for i in range(self.appliance_idx):
                if self.devices_conf[i][CONF_IP_ADDRESS] == ip_address:
                    raise _FlowException(
                        "duplicate_ip_provided", self.devices_conf[i][CONF_NAME]
                    )

    def _update_appliances_after_flow(self) -> None:
        for i, discovered in enumerate(self.discovered_appliances):
            if discovered:
                old_address = self.appliances[i].address
                self.appliances[i].update(discovered)
                if not discovered.address:
                    self.appliances[i].address = old_address

    def _placeholders(
        self: _MideaFlow, appliance: LanDevice = None, extra: dict[str, str] = None
    ) -> dict[str, str]:
        placeholders = {
            "cause": self.error_cause or "",
        }
        if extra:
            placeholders.update(extra)
        if appliance:
            placeholders[ATTR_ID] = (
                appliance.serial_number or f"{appliance.appliance_id} (Missing S/N)"
            )
            placeholders[ATTR_NAME] = appliance.name

        return placeholders


def _get_broadcast_addresses(user_input: dict[str, Any]) -> list[str]:
    address_entry = str(user_input.get(CONF_BROADCAST_ADDRESS, ""))
    addresses = [LOCAL_BROADCAST]
    specified_addresses = [
        addr.strip() for addr in address_entry.split(",") if addr.strip()
    ]
    for addr in specified_addresses:
        _LOGGER.debug("Trying IPv4 %s", addr)
        try:
            ipaddress.IPv4Network(addr)
            addresses.append(addr)
        except ValueError as ex:
            raise _FlowException("invalid_ip_range", str(ex)) from ex
        except Exception as ex:
            _LOGGER.debug("Invalid IP address %s", addr, exc_info=True)
            raise _FlowException("invalid_ip_range", addr) from ex
    return addresses


class _FlowException(Exception):
    def __init__(self, message, cause: str = None) -> None:
        super().__init__()
        self.message = message
        self.cause = cause


# pylint: disable=too-many-instance-attributes
class MideaConfigFlow(ConfigFlow, _MideaFlow, domain=DOMAIN):
    """
    Configuration flow for Midea dehumidifiers on local network uses discovery based on
    Midea cloud, so it first requires credentials for it.
    If some appliances are registered in the cloud, but not discovered, configuration
    flow will prompt for additional information.
    """

    VERSION = CURRENT_CONFIG_VERSION

    def __init__(self) -> None:
        super().__init__()
        self.discovered_appliances: list[LanDevice | None] = []
        self.appliances: list[LanDevice] = []
        self.config_entry: ConfigEntry | None = None
        self.advanced_settings = False

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Define the config flow to handle options."""
        return MideaOptionsFlow(config_entry)

    def _connect_and_discover(self: MideaConfigFlow) -> None:
        """Validates that cloud credentials are valid and discovers local appliances"""

        self._connect_to_cloud()
        conf_addresses = self.conf.get(CONF_BROADCAST_ADDRESS, [])
        if isinstance(conf_addresses, str):
            conf_addresses = [conf_addresses]
        addresses = []
        for addr in conf_addresses:
            addresses.append(str(ipaddress.IPv4Network(addr).broadcast_address))
        self.appliances = self.client.find_appliances(self.cloud, addresses=addresses)
        if self.appliances:
            self.devices_conf = [{} for _ in self.appliances]
        else:
            self.devices_conf = []

    async def _validate_discovery_phase(
        self, user_input: dict[str, Any] | None
    ) -> FlowResult:
        assert user_input is not None
        self.conf[CONF_USERNAME] = user_input[CONF_USERNAME]
        self.conf[CONF_PASSWORD] = user_input[CONF_PASSWORD]

        if self.advanced_settings:
            assert self.conf is not None
            self.conf[CONF_APPID] = user_input[CONF_APPID]
            self.conf[CONF_APPKEY] = user_input[CONF_APPKEY]
            self.conf[CONF_BROADCAST_ADDRESS] = _get_broadcast_addresses(user_input)
            self.conf[CONF_INCLUDE] = user_input[CONF_INCLUDE]
            self.conf[CONF_SCAN_INTERVAL] = user_input[CONF_SCAN_INTERVAL]
            _LOGGER.debug("include=%s", self.conf[CONF_INCLUDE])
        else:
            app = user_input.get(CONF_MOBILE_APP, DEFAULT_APP)
            self.conf.update(SUPPORTED_APPS.get(app, SUPPORTED_APPS[DEFAULT_APP]))
            if user_input.get(CONF_ADVANCED_SETTINGS):
                return await self.async_step_advanced_settings()

            self.conf[CONF_BROADCAST_ADDRESS] = []
            self.conf[CONF_INCLUDE] = [APPLIANCE_TYPE_DEHUMIDIFIER]
            self.conf[CONF_SCAN_INTERVAL] = DEFAULT_SCAN_INTERVAL

        await self.hass.async_add_executor_job(self._connect_and_discover)

        self.indexes_to_process = []

        for i, appliance in enumerate(self.appliances):
            if supported_appliance(self.conf, appliance) and (
                not appliance.address or appliance.address == UNKNOWN_IP
            ):
                self.indexes_to_process.append(i)
        if self.indexes_to_process:
            _LOGGER.debug("Pages to show %s", self.indexes_to_process)
            self.appliance_idx = self.indexes_to_process.pop(0)
            self.discovered_appliances = [None] * len(self.devices_conf)
            return await self.async_step_unreachable_appliance()

        return await self._async_add_entry()

    async def _do_validate(self, user_input: dict[str, Any]) -> FlowResult | None:
        try:
            return await self._validate_discovery_phase(user_input)
        except Exception as ex:  # pylint: disable=broad-except
            self._process_exception(ex)
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        self.advanced_settings = False
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        self.errors = {}
        self.error_cause = ""

        username = DEFAULT_USERNAME
        password = DEFAULT_PASSWORD
        app = DEFAULT_APP
        if user_input is not None:
            username = user_input.get(CONF_USERNAME, username)
            password = user_input.get(CONF_PASSWORD, password)
            app = user_input.get(CONF_MOBILE_APP, app)
            res = await self._do_validate(user_input)
            if res:
                return res

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(username=username, password=password, app=app),
            description_placeholders=self._placeholders(),
            errors=self.errors,
        )

    async def async_step_advanced_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step for managing advanced settings"""
        self.errors = {}
        self.error_cause = ""
        self.advanced_settings = True
        if user_input is not None:

            res = await self._do_validate(user_input)
            if res:
                return res
        else:
            user_input = {}

        username = user_input.get(
            CONF_USERNAME, self.conf.get(CONF_USERNAME, DEFAULT_USERNAME)
        )
        password = user_input.get(
            CONF_PASSWORD, self.conf.get(CONF_PASSWORD, DEFAULT_PASSWORD)
        )
        appkey = user_input.get(CONF_APPKEY, DEFAULT_APPKEY)
        appid = user_input.get(CONF_APPID, DEFAULT_APP_ID)
        broadcast_addresses = user_input.get(
            CONF_BROADCAST_ADDRESS, ",".join(self.conf.get(CONF_BROADCAST_ADDRESS, []))
        )

        return self.async_show_form(
            step_id="advanced_settings",
            data_schema=_advanced_settings_schema(
                username=username,
                password=password,
                appkey=appkey,
                appid=appid,
                broadcast_address=broadcast_addresses,
            ),
            description_placeholders=self._placeholders(),
            errors=self.errors,
        )

    async def async_step_unreachable_appliance(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the appliances that were not discovered automatically on LAN."""
        _LOGGER.debug("Pages to show %s", self.indexes_to_process)
        _LOGGER.debug("Current configuration %s", self.conf)
        _LOGGER.debug(
            "Saved configuration %s", self.config_entry and self.config_entry.data
        )

        return await self._async_step_appliance(
            step_id="unreachable_appliance",
            user_input=user_input,
        )

    async def _async_add_entry(self) -> FlowResult:
        assert self.conf is not None
        self.config_entry = await self.async_set_unique_id(self.conf[CONF_USERNAME])
        return await super()._async_add_entry()

    async def async_step_reauth(self, config) -> FlowResult:
        """Handle reauthorization request from Abode."""
        self.conf = {**config}

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauthorization flow."""
        self.errors = {}
        password = ""
        appkey = self.conf.get(CONF_APPKEY, DEFAULT_APPKEY)
        appid = self.conf.get(CONF_APPID, DEFAULT_APP_ID)
        if user_input is not None:
            extra_conf = {
                CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
                CONF_APPKEY: user_input.get(CONF_APPKEY, appkey),
                CONF_APPID: user_input.get(CONF_APPID, appid),
            }
            try:
                await self.hass.async_add_executor_job(
                    self._connect_to_cloud, extra_conf
                )
            except Exception as ex:  # pylint: disable=broad-except
                self._process_exception(ex)
            else:
                self.conf[CONF_PASSWORD] = password
                self.conf[CONF_APPKEY] = appkey
                self.conf[CONF_APPID] = appid
                return await self._async_add_entry()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_reauth_schema(
                password=password,
                appkey=appkey,
                appid=appid,
            ),
            description_placeholders=self._placeholders(),
            errors=self.errors,
        )


class MideaOptionsFlow(OptionsFlow, _MideaFlow):
    """Handle Midea options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Midea options flow."""
        super().__init__()
        self.config_entry = config_entry
        self.conf = {**config_entry.data}
        self.devices_conf = self.conf.get(CONF_DEVICES, [])

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Starts options flow"""
        self._build_appliance_list()
        return await self.async_step_appliance(user_input)

    async def async_step_appliance(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Options for an appliance"""
        _LOGGER.debug("Pages to show %s", self.indexes_to_process)
        _LOGGER.debug("Current configuration %s", self.conf)
        _LOGGER.debug(
            "Saved configuration %s", self.config_entry and self.config_entry.data
        )

        return await self._async_step_appliance(
            step_id="appliance",
            user_input=user_input,
        )

    def _build_appliance_list(self) -> None:
        assert self.config_entry
        hub: Hub = self.hass.data[DOMAIN][self.config_entry.entry_id]
        self.appliances = []
        self.devices_conf = self.conf[CONF_DEVICES]
        device: dict[str, Any]
        for device in self.devices_conf:
            for coord in hub.coordinators:
                if device[CONF_UNIQUE_ID] == coord.appliance.serial_number:
                    self.appliances.append(coord.appliance)
                    break
            else:
                appliance = LanDevice(
                    appliance_id=device[CONF_ID],
                    serial_number=device[CONF_UNIQUE_ID],
                    appliance_type=device[CONF_TYPE],
                )
                appliance.name = device[CONF_NAME]
                appliance.address = device.get(CONF_IP_ADDRESS, UNKNOWN_IP)
                self.appliances.append(appliance)
        self.indexes_to_process = list(range(len(self.appliances)))
        self.appliance_idx = self.indexes_to_process.pop(0)
        self.discovered_appliances = [None] * len(self.devices_conf)
