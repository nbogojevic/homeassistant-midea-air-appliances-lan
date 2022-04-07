"""Config flow for Midea Air Appliance (Local) integration."""
from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network
import logging
from typing import Any

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
    CONF_TTL,
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
    APPLIANCE_TYPE_DEHUMIDIFIER,
    SUPPORTED_APPS,
)

from custom_components.midea_dehumidifier_lan import Hub
from custom_components.midea_dehumidifier_lan.const import (
    NAME,
    CURRENT_CONFIG_VERSION,
    SUPPORTED_APPLIANCES,
    CONF_ADVANCED_SETTINGS,
    CONF_DEBUG,
    CONF_MOBILE_APP,
    CONF_TOKEN_KEY,
    DEFAULT_APP,
    DEFAULT_DISCOVERY_MODE,
    DEFAULT_PASSWORD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TTL,
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
from custom_components.midea_dehumidifier_lan.util import (
    MideaClient,
    RedactedConf,
    address_ok,
    supported_appliance,
)

_LOGGER = logging.getLogger(__name__)


def _appliance_schema(  # pylint: disable=too-many-arguments
    name: str,
    address: str = UNKNOWN_IP,
    ttl: int = DEFAULT_TTL,
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
            vol.Required(
                CONF_TTL,
                msg="Test",
                default=ttl,
                description={"suffix": "minutes"},
            ): cv.positive_int,
            vol.Optional(CONF_TOKEN, default=token or ""): cv.string,
            vol.Optional(CONF_TOKEN_KEY, default=token_key or ""): cv.string,
        }
    )


# pylint: disable=too-many-arguments
def _advanced_settings_schema(
    username: str = "",
    password: str = "",
    app: str = DEFAULT_APP,
    broadcast_address: str = "",
    appliances: list[str] = None,
    debug: bool = False,
) -> vol.Schema:
    appliances = appliances or [APPLIANCE_TYPE_DEHUMIDIFIER]
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=username): cv.string,
            vol.Required(CONF_PASSWORD, default=password): cv.string,
            vol.Optional(CONF_MOBILE_APP, default=app): vol.In(SUPPORTED_APPS.keys()),
            vol.Optional(CONF_BROADCAST_ADDRESS, default=broadcast_address): cv.string,
            vol.Required(
                CONF_SCAN_INTERVAL,
                msg="Test",
                default=DEFAULT_SCAN_INTERVAL,
                description={"suffix": "minutes"},
            ): cv.positive_int,
            vol.Required(CONF_INCLUDE, default=appliances): vol.All(
                cv.multi_select(SUPPORTED_APPLIANCES),
                vol.Length(min=1, msg="Must select at least one appliance category"),
            ),
            vol.Required(CONF_DEBUG, default=debug): bool,
        }
    )


def _reauth_schema(
    username: str,
    password: str,
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=username): cv.string,
            vol.Required(CONF_PASSWORD, default=password): cv.string,
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
        self._client: MideaClient | None = None
        self.cloud: MideaCloud | None = None  # type: ignore
        self.conf = {}
        self.config_entry: ConfigEntry | None = None
        self.devices_conf: list[dict[str, Any]] = []
        self.discovered_appliances: list[LanDevice | None] = []
        self.error_cause: str = ""
        self.errors: dict[str, Any] = {}
        self.indexes_to_process = []

    @property
    def client(self) -> MideaClient:
        """Returns instance of MideaClient."""
        if not self._client:
            self._client = MideaClient(self.hass)
        return self._client

    def _process_exception(self: _MideaFlow, ex: Exception) -> None:
        if isinstance(ex, _FlowException):
            _LOGGER.warning(
                "Caught flow exception during appliance step %s", ex, exc_info=True
            )
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
        cfg = self.conf | (extra_conf or {})
        try:
            self.cloud = self.client.connect_to_cloud(cfg)
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
                ip_address = appliance.address
                if not address_ok(ip_address):
                    raise _FlowException("invalid_ip_address", ip_address)
                try:
                    IPv4Address(ip_address)
                except Exception as ex:
                    _LOGGER.debug("Invalid appliance address %s: %s", ip_address, ex)
                    raise _FlowException("invalid_ip_address", ip_address) from ex
                discovered = self.client.appliance_state(
                    address=ip_address, cloud=self.cloud
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
                device_conf |= {
                    CONF_API_VERSION: appliance.version,
                    CONF_ID: appliance.appliance_id,
                    CONF_IP_ADDRESS: (
                        appliance.address or device_conf[CONF_IP_ADDRESS] or UNKNOWN_IP
                    ),
                    CONF_NAME: appliance.name,
                    CONF_TOKEN_KEY: appliance.key,
                    CONF_TOKEN: appliance.token,
                    CONF_TYPE: appliance.type,
                    CONF_UNIQUE_ID: appliance.serial_number,
                }
                suggested_discovery = (
                    DISCOVERY_LAN
                    if address_ok(device_conf[CONF_IP_ADDRESS])
                    else DISCOVERY_WAIT
                )
                device_conf.get(CONF_DISCOVERY, suggested_discovery)
                supported_devices_conf.append(device_conf)
        self.devices_conf = supported_devices_conf
        self.conf[CONF_DEVICES] = self.devices_conf

        # Remove not used elements
        self.conf.pop(CONF_ADVANCED_SETTINGS, None)
        if self.config_entry:
            _LOGGER.debug("Updating configuration data %s", RedactedConf(self.conf))
            self.hass.config_entries.async_update_entry(
                entry=self.config_entry, data=self.conf
            )
            # Reload the config entry otherwise devices will remain unavailable
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry.entry_id)
            )

        if not self.devices_conf:
            _LOGGER.debug("No configured appliances %s", RedactedConf(self.conf))
            return self.async_abort(reason="no_configured_devices")
        _LOGGER.debug("Creating configuration data %s", RedactedConf(self.conf))
        return self.async_create_entry(title=NAME, data=self.conf)

    async def _async_step_appliance(  # pylint: disable=too-many-locals
        self: _MideaFlow,
        step_id: str,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Manage an appliances"""

        self.errors.clear()
        self.error_cause = ""
        appliance = self.appliances[self.appliance_idx]
        device_conf = self.devices_conf[self.appliance_idx]
        discovery_mode = device_conf.get(CONF_DISCOVERY, DEFAULT_DISCOVERY_MODE)
        ttl = device_conf.get(CONF_TTL, DEFAULT_TTL)
        ip_address = appliance.address or UNKNOWN_IP
        if user_input is not None:
            try:

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
                        DISCOVERY_LAN if address_ok(ip_address) else DISCOVERY_CLOUD
                    )
                device_conf[CONF_DISCOVERY] = discovery_mode
                device_conf[CONF_TTL] = user_input.get(CONF_TTL, ttl)
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
                ip_address = appliance.address or UNKNOWN_IP
                user_input = None
                discovery_mode = DEFAULT_DISCOVERY_MODE
                ttl = DEFAULT_TTL

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
            "ttl": device_conf.get(CONF_TTL, ttl),
            "discovery_mode": device_conf.get(CONF_DISCOVERY, discovery_mode),
        }
        schema = _appliance_schema(**schema_arg)
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            description_placeholders=placeholders,
            errors=self.errors,
            last_step=len(self.indexes_to_process) == 0,
        )

    def _check_ip_address_unique(self, ip_address) -> None:
        if address_ok(ip_address):
            for i in range(self.appliance_idx):
                if (
                    self.devices_conf[i].get(CONF_IP_ADDRESS) == ip_address
                    or ip_address == self.appliances[i].address
                ):
                    raise _FlowException(
                        "duplicate_ip_provided", self.appliances[i].name
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
        extra = extra or {}
        placeholders = {
            "cause": self.error_cause or "",
            **extra,
        }
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
            IPv4Network(addr)
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
    """Configuration flow for Midea dehumidifiers on local network uses
    discovery based on Midea cloud, so it first requires credentials for it.
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
        addresses = [
            str(IPv4Network(addr).broadcast_address) for addr in conf_addresses
        ]
        self.appliances.clear()
        self.appliances += self.client.find_appliances(self.cloud, addresses)
        self.devices_conf = [{} for _ in self.appliances]

    async def _validate_discovery_phase(
        self, user_input: dict[str, Any] | None
    ) -> FlowResult:
        assert user_input is not None
        self.conf[CONF_USERNAME] = user_input[CONF_USERNAME]
        self.conf[CONF_PASSWORD] = user_input[CONF_PASSWORD]

        if self.advanced_settings:
            assert self.conf is not None
            self.conf[CONF_MOBILE_APP] = user_input.get(CONF_MOBILE_APP, DEFAULT_APP)
            self.conf[CONF_INCLUDE] = user_input[CONF_INCLUDE]
            self.conf[CONF_SCAN_INTERVAL] = user_input[CONF_SCAN_INTERVAL]
            self.conf[CONF_DEBUG] = user_input[CONF_DEBUG]
            self.conf[CONF_BROADCAST_ADDRESS] = _get_broadcast_addresses(user_input)

        else:
            self.conf[CONF_MOBILE_APP] = user_input.get(CONF_MOBILE_APP, DEFAULT_APP)
            if user_input.get(CONF_ADVANCED_SETTINGS):
                return await self.async_step_advanced_settings()

            self.conf[CONF_BROADCAST_ADDRESS] = []
            self.conf[CONF_INCLUDE] = [APPLIANCE_TYPE_DEHUMIDIFIER]
            self.conf[CONF_SCAN_INTERVAL] = DEFAULT_SCAN_INTERVAL

        if self.conf.get(CONF_DEBUG, False):
            await self.client.async_debug_mode(True)
        await self.hass.async_add_executor_job(self._connect_and_discover)

        self.indexes_to_process = [
            index
            for index, appliance in enumerate(self.appliances)
            if supported_appliance(self.conf, appliance)
            and not address_ok(appliance.address)
        ]
        if self.indexes_to_process:
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

        self.errors.clear()
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
            if res := await self._do_validate(user_input):
                return res
        else:
            user_input = {}

        username = user_input.get(
            CONF_USERNAME, self.conf.get(CONF_USERNAME, DEFAULT_USERNAME)
        )
        password = user_input.get(
            CONF_PASSWORD, self.conf.get(CONF_PASSWORD, DEFAULT_PASSWORD)
        )
        app = user_input.get(CONF_MOBILE_APP, DEFAULT_APP)
        broadcast_addresses = user_input.get(
            CONF_BROADCAST_ADDRESS, ",".join(self.conf.get(CONF_BROADCAST_ADDRESS, []))
        )

        return self.async_show_form(
            step_id="advanced_settings",
            data_schema=_advanced_settings_schema(
                username=username,
                password=password,
                app=app,
                broadcast_address=broadcast_addresses,
            ),
            description_placeholders=self._placeholders(),
            errors=self.errors,
        )

    async def async_step_unreachable_appliance(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the appliances that were not discovered automatically on LAN."""

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
        self.errors.clear()
        password = ""
        username = self.conf.get(CONF_USERNAME, "")
        app = self.conf.get(CONF_MOBILE_APP, DEFAULT_APP)
        if user_input is not None:
            extra_conf = {
                CONF_USERNAME: user_input.get(CONF_USERNAME, ""),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
                CONF_MOBILE_APP: user_input.get(CONF_MOBILE_APP, app),
            }
            try:
                await self.hass.async_add_executor_job(
                    self._connect_to_cloud, extra_conf
                )
            except Exception as ex:  # pylint: disable=broad-except
                self._process_exception(ex)
            else:
                self.conf[CONF_USERNAME] = username
                self.conf[CONF_PASSWORD] = password
                self.conf[CONF_MOBILE_APP] = app
                return await self._async_add_entry()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_reauth_schema(
                username=username,
                password=password,
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

        return await self._async_step_appliance(
            step_id="appliance",
            user_input=user_input,
        )

    def _build_appliance_list(self) -> None:
        assert self.config_entry
        hub: Hub = self.hass.data[DOMAIN][self.config_entry.entry_id]
        self.appliances.clear()
        self.devices_conf = self.conf[CONF_DEVICES]
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
