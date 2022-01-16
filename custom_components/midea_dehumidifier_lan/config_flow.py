"""Config flow for Midea Dehumidifier (Local) integration."""
from __future__ import annotations

import ipaddress
import logging
from typing import Any, Final

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
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
from homeassistant.data_entry_flow import FlowResult
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
    APPLIANCE_SCAN_INTERVAL,
    CONF_ADVANCED_SETTINGS,
    CONF_APPID,
    CONF_APPKEY,
    CONF_MOBILE_APP,
    CONF_TOKEN_KEY,
    CURRENT_CONFIG_VERSION,
    DEFAULT_APP,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    DISCOVERY_CLOUD,
    DISCOVERY_IGNORE,
    DISCOVERY_LAN,
    DISCOVERY_WAIT,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    UNKNOWN_IP,
)


_LOGGER = logging.getLogger(__name__)


def _unreachable_appliance_schema(
    name: str,
    address: str = UNKNOWN_IP,
    token: str = "",
    token_key: str = "",
    discovery_mode=DISCOVERY_WAIT,
):
    return vol.Schema(
        {
            vol.Optional(CONF_DISCOVERY, default=str(discovery_mode)): vol.In(
                {
                    DISCOVERY_IGNORE: "Exclude appliance",
                    DISCOVERY_LAN: "Provide appliance's IPv4 address",
                    DISCOVERY_WAIT: "Wait for appliance to come online",
                    DISCOVERY_CLOUD: "Use cloud API to poll devices",
                }
            ),
            vol.Optional(
                CONF_IP_ADDRESS,
                default=address or UNKNOWN_IP,
            ): cv.string,
            vol.Optional(CONF_NAME, default=name): cv.string,
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
):
    appliances = [APPLIANCE_TYPE_DEHUMIDIFIER]
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=username): cv.string,
            vol.Required(CONF_PASSWORD, default=password): cv.string,
            vol.Required(CONF_APPKEY, default=appkey): cv.string,
            vol.Required(CONF_APPID, default=appid): cv.positive_int,
            vol.Optional(CONF_BROADCAST_ADDRESS, default=broadcast_address): cv.string,
            vol.Optional(
                CONF_SCAN_INTERVAL, default=2, description={"suffix": "minutes"}
            ): vol.All(
                vol.Coerce(int),
                vol.Clamp(
                    min=MIN_SCAN_INTERVAL,
                    msg=f"Scan interval should be at least {MIN_SCAN_INTERVAL} minutes",
                ),
            ),
            vol.Optional(CONF_INCLUDE, default=appliances): vol.All(
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
):
    return vol.Schema(
        {
            vol.Required(CONF_PASSWORD, default=password): cv.string,
            vol.Required(CONF_APPKEY, default=appkey): cv.string,
            vol.Required(CONF_APPID, default=appid): cv.positive_int,
        }
    )


def _user_schema(username: str, password: str, app: str):

    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=username): cv.string,
            vol.Required(CONF_PASSWORD, default=password): cv.string,
            vol.Optional(CONF_MOBILE_APP, default=app): vol.In(SUPPORTED_APPS.keys()),
            vol.Required(CONF_ADVANCED_SETTINGS, default=False): bool,
        }
    )


def _placeholders(
    error_cause=None, appliance: LanDevice = None, extra: dict[str, str] = None
) -> dict[str, str]:
    placeholders = {
        "cause": error_cause or "",
    }
    if extra:
        placeholders.update(extra)
    if appliance:
        placeholders[ATTR_ID] = appliance.unique_id
        placeholders[ATTR_NAME] = appliance.name

    return placeholders


def _validate_appliance(
    flow: MideaConfigFlow | MideaOptionsFlow, appliance: LanDevice, device_conf: dict
) -> LanDevice | None:
    """
    Validates that appliance configuration is correct and matches physical
    device
    """
    discovery_mode = device_conf.get(CONF_DISCOVERY, DISCOVERY_LAN)
    if discovery_mode == DISCOVERY_IGNORE:
        _LOGGER.debug("Ignored appliance with id=%s", appliance.appliance_id)
        return None
    if discovery_mode == DISCOVERY_WAIT:
        _LOGGER.debug(
            "Attempt to discover appliance with id=%s will be made later",
            appliance.appliance_id,
        )
        return None
    try:
        if discovery_mode == DISCOVERY_CLOUD:
            discovered = flow.client.appliance_state(
                cloud=flow.cloud,
                use_cloud=True,
                appliance_id=appliance.appliance_id,
            )
        else:
            if appliance.address == UNKNOWN_IP:
                raise _FlowException("invalid_ip_address", appliance.address)
            try:
                ipaddress.IPv4Address(appliance.address)
            except Exception as ex:
                raise _FlowException("invalid_ip_address", appliance.address) from ex
            discovered = flow.client.appliance_state(
                address=appliance.address,
                cloud=flow.cloud,
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


async def _async_add_entry(flow: MideaConfigFlow | MideaOptionsFlow) -> FlowResult:
    for i, appliance in enumerate(flow.appliances):
        if not supported_appliance(flow.conf, appliance):
            continue
        device_conf = flow.devices_conf[i]
        if device_conf.get(CONF_DISCOVERY) != DISCOVERY_IGNORE:
            device_conf.update(
                {
                    CONF_API_VERSION: appliance.version,
                    CONF_ID: appliance.appliance_id,
                    CONF_IP_ADDRESS: appliance.address,
                    CONF_NAME: appliance.name,
                    CONF_TOKEN_KEY: appliance.key,
                    CONF_TOKEN: appliance.token,
                    CONF_TYPE: appliance.type,
                    CONF_UNIQUE_ID: appliance.unique_id,
                }
            )
    flow.conf[CONF_DEVICES] = flow.devices_conf

    # Remove not used elements
    flow.conf.pop(CONF_ADVANCED_SETTINGS, None)
    flow.conf.pop(CONF_MOBILE_APP, None)

    if flow.config_entry:
        flow.hass.config_entries.async_update_entry(
            entry=flow.config_entry,
            data=flow.conf,
        )
        # Reload the config entry otherwise devices will remain unavailable
        flow.hass.async_create_task(
            flow.hass.config_entries.async_reload(flow.config_entry.entry_id)
        )

    if len(flow.devices_conf) == 0:
        return flow.async_abort(reason="no_configured_devices")
    return flow.async_create_entry(
        title="Midea Dehumidifiers",
        data=flow.conf,
    )


def _connect_to_cloud(
    flow: MideaConfigFlow | MideaOptionsFlow, extra_conf: dict[str, Any] = None
):
    """Validates that cloud credentials are valid"""
    extra_conf = extra_conf or {}
    flow.cloud = flow.client.connect_to_cloud(
        account=flow.conf[CONF_USERNAME],
        password=extra_conf.get(CONF_PASSWORD, flow.conf[CONF_PASSWORD]),
        appkey=extra_conf.get(CONF_APPKEY, flow.conf[CONF_APPKEY]),
        appid=extra_conf.get(CONF_APPID, flow.conf[CONF_APPID]),
    )


def _get_broadcast_addresses(user_input):
    address_entry = str(user_input.get(CONF_BROADCAST_ADDRESS, ""))
    addresses = [addr.strip() for addr in address_entry.split(",") if addr.strip()]
    for addr in addresses:
        try:
            ipaddress.IPv4Address(addr)
        except Exception as ex:
            raise _FlowException("invalid_ip_address", addr) from ex
    return addresses


async def _async_step_appliance(
    flow: MideaConfigFlow | MideaOptionsFlow,
    step_id: str,
    user_input: dict[str, Any] | None = None,
) -> FlowResult:
    """Manage an appliances"""

    errors: dict = {}
    flow.error_cause = ""
    _LOGGER.debug("Processing step %d", flow.appliance_idx)
    appliance = flow.appliances[flow.appliance_idx]
    device_conf = flow.devices_conf[flow.appliance_idx]
    discovery_mode = device_conf.get(CONF_DISCOVERY, DISCOVERY_LAN)
    if user_input is not None:
        discovery_mode = user_input.get(CONF_DISCOVERY, discovery_mode)
        device_conf[CONF_DISCOVERY] = discovery_mode
        appliance.address = (
            user_input.get(
                CONF_IP_ADDRESS, device_conf.get(CONF_IP_ADDRESS, UNKNOWN_IP)
            )
            if discovery_mode == DISCOVERY_LAN
            else UNKNOWN_IP
        )
        appliance.name = user_input.get(CONF_NAME, appliance.name)
        appliance.token = user_input.get(CONF_TOKEN, "")
        appliance.key = user_input.get(CONF_TOKEN_KEY, "")

        try:
            if not flow.cloud:
                await flow.hass.async_add_executor_job(_connect_to_cloud, flow)

            discovered = await flow.hass.async_add_executor_job(
                _validate_appliance,
                flow,
                appliance,
                device_conf,
            )
            flow.discovered_appliances[flow.appliance_idx] = discovered

            if not flow.indexes_to_process:
                for discovered in flow.discovered_appliances:
                    if discovered:
                        flow.appliances[flow.appliance_idx].update(discovered)
                return await _async_add_entry(flow)

            flow.appliance_idx = flow.indexes_to_process.pop(0)
            appliance = flow.appliances[flow.appliance_idx]
            device_conf = flow.devices_conf[flow.appliance_idx]
            user_input = None

        except _FlowException as ex:
            flow.error_cause = str(ex.cause)
            errors["base"] = ex.message

    name = appliance.name
    extra = {
        "index": str(flow.appliance_idx + 1),
        "count": str(len(flow.appliances)),
    }
    placeholders = _placeholders(flow.error_cause, appliance, extra)
    schema = _unreachable_appliance_schema(
        name,
        address=device_conf.get(CONF_IP_ADDRESS, appliance.address or UNKNOWN_IP),
        token=device_conf.get(CONF_TOKEN, appliance.token),
        token_key=device_conf.get(CONF_TOKEN_KEY, appliance.key),
        discovery_mode=device_conf.get(CONF_DISCOVERY, discovery_mode),
    )
    return flow.async_show_form(
        step_id=step_id,
        data_schema=schema,
        description_placeholders=placeholders,
        errors=errors,
        last_step=len(flow.indexes_to_process) == 0,
    )


class _FlowException(Exception):
    def __init__(self, message, cause: str = None) -> None:
        super().__init__()
        self.message = message
        self.cause = cause


# pylint: disable=too-many-instance-attributes
class MideaConfigFlow(ConfigFlow, domain=DOMAIN):
    """
    Configuration flow for Midea dehumidifiers on local network uses discovery based on
    Midea cloud, so it first requires credentials for it.
    If some appliances are registered in the cloud, but not discovered, configuration
    flow will prompt for additional information.
    """

    VERSION = CURRENT_CONFIG_VERSION

    def __init__(self) -> None:
        self.cloud: MideaCloud | None = None  # type: ignore
        self.appliances: list[LanDevice] = []
        self.devices_conf: list[dict] = []
        self.discovered_appliances: list[LanDevice | None] = []
        self.conf = {}
        self.advanced_settings = False
        self.client: Final = MideaClient()
        self.error_cause: str = ""
        self.errors: dict = {}
        self.config_entry: ConfigEntry | None = None
        self.appliance_idx = -1
        self.indexes_to_process = []

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Define the config flow to handle options."""
        return MideaOptionsFlow(config_entry)

    def _connect_and_discover(self: MideaConfigFlow):
        """Validates that cloud credentials are valid and discovers local appliances"""

        _connect_to_cloud(self)
        addresses = self.conf.get(CONF_BROADCAST_ADDRESS, [])
        if isinstance(addresses, str):
            addresses = [addresses]
        self.appliances = self.client.find_appliances(self.cloud, addresses=addresses)
        if self.appliances:
            self.devices_conf = [{} for _ in self.appliances]
        else:
            self.devices_conf = []

    async def _validate_discovery_phase(self, user_input: dict[str, Any] | None):
        assert user_input is not None
        self.conf[CONF_USERNAME] = user_input[CONF_USERNAME]
        self.conf[CONF_PASSWORD] = user_input[CONF_PASSWORD]

        if self.advanced_settings:
            assert self.conf is not None
            self.conf[CONF_APPKEY] = user_input[CONF_APPKEY]
            self.conf[CONF_APPID] = user_input[CONF_APPID]
            addresses = _get_broadcast_addresses(user_input)

            self.conf[CONF_BROADCAST_ADDRESS] = addresses
            self.conf[CONF_SCAN_INTERVAL] = user_input[CONF_SCAN_INTERVAL]
            self.conf[CONF_INCLUDE] = user_input[CONF_INCLUDE]
            _LOGGER.debug("include=%s", self.conf[CONF_INCLUDE])
        else:
            app = user_input.get(CONF_MOBILE_APP, DEFAULT_APP)
            self.conf.update(SUPPORTED_APPS.get(app, SUPPORTED_APPS[DEFAULT_APP]))
            if user_input.get(CONF_ADVANCED_SETTINGS):
                return await self.async_step_advanced_settings()

            self.conf[CONF_BROADCAST_ADDRESS] = []
            self.conf[CONF_SCAN_INTERVAL] = APPLIANCE_SCAN_INTERVAL
            self.conf[CONF_INCLUDE] = [APPLIANCE_TYPE_DEHUMIDIFIER]

        await self.hass.async_add_executor_job(self._connect_and_discover)

        self.indexes_to_process = []

        for i, appliance in enumerate(self.appliances):
            if supported_appliance(self.conf, appliance) and (
                not appliance.address or appliance.address == UNKNOWN_IP
            ):
                self.indexes_to_process.append(i)
        if self.indexes_to_process:
            self.appliance_idx = self.indexes_to_process.pop(0)
            self.discovered_appliances = [None] * len(self.devices_conf)
            return await self.async_step_unreachable_appliance()

        return await self._async_add_entry()

    def _process_exception(self, ex: Exception):
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

    async def _do_validate(self, user_input: dict[str, Any]):
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
            description_placeholders=_placeholders(self.error_cause),
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
        broadcast_address = user_input.get(
            CONF_BROADCAST_ADDRESS, self.conf.get(CONF_BROADCAST_ADDRESS, "")
        )

        return self.async_show_form(
            step_id="advanced_settings",
            data_schema=_advanced_settings_schema(
                username=username,
                password=password,
                appkey=appkey,
                appid=appid,
                broadcast_address=broadcast_address,
            ),
            description_placeholders=_placeholders(self.error_cause),
            errors=self.errors,
        )

    async def async_step_unreachable_appliance(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the appliances that were not discovered automatically on LAN."""

        return await _async_step_appliance(
            step_id="unreachable_appliance",
            flow=self,
            user_input=user_input,
        )

    async def _async_add_entry(self) -> FlowResult:
        assert self.conf is not None
        self.config_entry = await self.async_set_unique_id(self.conf[CONF_USERNAME])
        return await _async_add_entry(self)

    async def async_step_reauth(self, config):
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
                    _connect_to_cloud, self, extra_conf
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
            description_placeholders=_placeholders(self.error_cause),
            errors=self.errors,
        )


class MideaOptionsFlow(OptionsFlow):
    """Handle Midea options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Midea options flow."""
        self.config_entry = config_entry
        self.appliances: list[LanDevice] = []
        self.devices_conf: list[dict[str, Any]] = []
        self.discovered_appliances: list[LanDevice | None] = []
        self.error_cause = ""
        self.conf = {**config_entry.data}
        self.client = MideaClient()
        self.cloud: MideaCloud | None = None
        self.appliance_idx = -1
        self.indexes_to_process = []

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
        return await _async_step_appliance(
            step_id="appliance",
            flow=self,
            user_input=user_input,
        )

    def _build_appliance_list(self):
        hub: Hub = self.hass.data[DOMAIN][self.config_entry.entry_id]
        self.appliances = []
        self.devices_conf: list[dict[str, Any]] = self.conf[CONF_DEVICES]
        for device in self.devices_conf:
            for coord in hub.coordinators:
                if device[CONF_UNIQUE_ID] == coord.appliance.unique_id:
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
