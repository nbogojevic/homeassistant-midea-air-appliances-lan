"""Config flow for Midea Dehumidifier (Local) integration."""
from __future__ import annotations

import ipaddress
import logging
from typing import Any, Final

from homeassistant.config_entries import (
    ConfigFlow,
    OptionsFlow,
    ConfigEntry,
    ConfigType,
)
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_DEVICES,
    CONF_EXCLUDE,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
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
from midea_beautiful.midea import DEFAULT_APP_ID, DEFAULT_APPKEY, SUPPORTED_APPS
from custom_components.midea_dehumidifier_lan import Hub

from custom_components.midea_dehumidifier_lan.api import (
    MideaClient,
    supported_appliance,
)

from custom_components.midea_dehumidifier_lan.const import (
    CONF_ADVANCED_SETTINGS,
    CONF_APPID,
    CONF_APPKEY,
    CONF_DETECT_AC_APPLIANCES,
    CONF_MOBILE_APP,
    CONF_BROADCAST_ADDRESS,
    CONF_TOKEN_KEY,
    CONF_USE_CLOUD,
    CONF_WHAT_TO_DO,
    CURRENT_CONFIG_VERSION,
    DEFAULT_APP,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    DOMAIN,
    UNKNOWN_IP,
    TAG_CAUSE,
    TAG_ID,
    TAG_NAME,
)

_LOGGER = logging.getLogger(__name__)


# What to do with configured appliance
IGNORE = "IGNORE"
LAN = "LAN"
USE_CLOUD = "CLOUD"
WAIT = "WAIT"


def _unreachable_appliance_schema(
    name: str,
    address: str = UNKNOWN_IP,
    token: str = "",
    token_key: str = "",
    what_to_do=WAIT,
):
    return vol.Schema(
        {
            vol.Optional(CONF_WHAT_TO_DO, default=str(what_to_do)): vol.In(
                {
                    str(IGNORE): "Exclude appliance",
                    str(LAN): "Provide appliance's IPv4 address",
                    str(WAIT): "Wait for appliance to come online",
                    str(USE_CLOUD): "Use cloud API to poll devices",
                }
            ),
            vol.Optional(
                CONF_IP_ADDRESS,
                default=address,
                description={"suggested_value": UNKNOWN_IP},
            ): cv.string,
            vol.Optional(CONF_NAME, default=name): cv.string,
            vol.Optional(CONF_TOKEN, default=token): cv.string,
            vol.Optional(CONF_TOKEN_KEY, default=token_key): cv.string,
        }
    )


# pylint: disable=too-many-arguments
def _advanced_settings_schema(
    username: str,
    password: str,
    appkey: str,
    appid: int,
    broadcast_address: str,
    use_cloud: bool,
):
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=username): cv.string,
            vol.Required(CONF_PASSWORD, default=password): cv.string,
            vol.Required(CONF_APPKEY, default=appkey): cv.string,
            vol.Required(CONF_APPID, default=appid): int,
            vol.Optional(CONF_BROADCAST_ADDRESS, default=broadcast_address): cv.string,
            vol.Required(CONF_USE_CLOUD, default=use_cloud): bool,
            vol.Required(CONF_DETECT_AC_APPLIANCES, default=False): bool,
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
            vol.Required(CONF_APPID, default=appid): int,
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
        TAG_CAUSE: error_cause or "",
    }
    if extra:
        placeholders.update(extra)
    if appliance:
        placeholders[TAG_ID] = appliance.unique_id
        placeholders[TAG_NAME] = appliance.name

    return placeholders


def _validate_appliance(
    cloud: MideaCloud, client: MideaClient, appliance: LanDevice, conf: dict
):
    """
    Validates that appliance configuration is correct and matches physical
    device
    """
    use_cloud = conf.get(CONF_USE_CLOUD, False)
    if appliance.address == UNKNOWN_IP or (appliance.address is None and not use_cloud):
        _LOGGER.debug("Ignored appliance with id=%s", appliance.appliance_id)
        return
    try:
        if use_cloud:
            discovered = client.appliance_state(
                cloud=cloud,
                use_cloud=use_cloud,
                appliance_id=appliance.appliance_id,
            )
        else:
            try:
                ipaddress.IPv4Address(appliance.address)
            except Exception as ex:
                raise _FlowException("invalid_ip_address", appliance.address) from ex
            discovered = client.appliance_state(
                address=appliance.address,
                cloud=cloud,
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
    appliance.update(discovered)


async def _async_add_entry(flow: MideaConfigFlow | MideaOptionsFlow) -> FlowResult:
    for i, appliance in enumerate(flow.appliances):
        if not supported_appliance(flow.conf, appliance):
            continue
        device_conf = flow.devices_conf[i]
        if not device_conf[CONF_EXCLUDE]:
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
    flow: MideaConfigFlow | MideaOptionsFlow, user_input: dict[str, Any] = None
):
    """Validates that cloud credentials are valid"""
    user_input = user_input or {}
    flow.cloud = flow.client.connect_to_cloud(
        account=flow.conf[CONF_USERNAME],
        password=user_input.get(CONF_PASSWORD, flow.conf[CONF_PASSWORD]),
        appkey=user_input.get(CONF_APPKEY, flow.conf[CONF_APPKEY]),
        appid=user_input.get(CONF_APPID, flow.conf[CONF_APPID]),
    )


async def _async_step_appliance(
    step_id: str,
    args: MideaConfigFlow | MideaOptionsFlow,
    user_input: dict[str, Any] | None = None,
) -> FlowResult:
    """Manage an appliances"""

    errors: dict = {}
    args.error_cause = ""
    appliance = args.appliances[args.appliance_idx]
    device_conf = args.devices_conf[args.appliance_idx]
    what_to_do = _deduce_what_to_do(device_conf)
    if user_input is not None:
        what_to_do = user_input.get(CONF_WHAT_TO_DO, str(what_to_do))
        appliance.address = (
            user_input.get(CONF_IP_ADDRESS, UNKNOWN_IP)
            if what_to_do == LAN
            else UNKNOWN_IP
        )
        appliance.name = user_input.get(CONF_NAME, appliance.name)
        appliance.token = user_input.get(CONF_TOKEN, "")
        appliance.key = user_input.get(CONF_TOKEN_KEY, "")

        device_conf[CONF_EXCLUDE] = what_to_do == IGNORE
        device_conf[CONF_USE_CLOUD] = what_to_do == USE_CLOUD

        try:
            if not args.cloud:
                await args.hass.async_add_executor_job(_connect_to_cloud, args)
            await args.hass.async_add_executor_job(
                _validate_appliance,
                args.cloud,
                args.client,
                appliance,
                device_conf,
            )
            # Find next unreachable appliance
            args.appliance_idx = args.appliance_idx + 1
            while args.appliance_idx < len(args.appliances):
                if supported_appliance(args.conf, appliance):
                    if not args.appliances[args.appliance_idx].address:
                        return await _async_step_appliance(step_id, args)
                args.appliance_idx = args.appliance_idx + 1

            # If no unreachable appliances, create entry
            if args.appliance_idx >= len(args.appliances):
                return await _async_add_entry(args)
            appliance = args.appliances[args.appliance_idx]

        except _FlowException as ex:
            args.error_cause = str(ex.cause)
            errors["base"] = ex.message

    name = appliance.name
    extra = {
        "current_index": str(args.appliance_idx + 1),
        "appliance_count": str(len(args.appliances)),
    }
    placeholders = _placeholders(args.error_cause, appliance, extra)
    schema = _unreachable_appliance_schema(
        name,
        address=device_conf.get(CONF_IP_ADDRESS, UNKNOWN_IP),
        token=device_conf.get(CONF_TOKEN, ""),
        token_key=device_conf.get(CONF_TOKEN_KEY, ""),
        what_to_do=what_to_do,
    )
    return args.async_show_form(
        step_id=step_id,
        data_schema=schema,
        description_placeholders=placeholders,
        errors=errors,
    )


def _deduce_what_to_do(device_conf: dict[str, Any]) -> str:
    what_to_do = WAIT
    if device_conf.get(CONF_USE_CLOUD):
        what_to_do = USE_CLOUD
    elif device_conf.get(CONF_EXCLUDE):
        what_to_do = IGNORE
    elif device_conf.get(CONF_IP_ADDRESS) != UNKNOWN_IP:
        what_to_do = LAN
    return what_to_do


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
        self.appliance_idx = -1
        self.appliances: list[LanDevice] = []
        self.devices_conf: list[dict] = []
        self.conf = {}
        self.advanced_settings = False
        self.client: Final = MideaClient()
        self.error_cause: str = ""
        self.errors: dict = {}
        self.config_entry: ConfigEntry | None = None

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
        if self.advanced_settings:
            assert self.conf is not None
            self.conf[CONF_APPKEY] = user_input[CONF_APPKEY]
            self.conf[CONF_APPID] = user_input[CONF_APPID]
            if address := user_input.get(CONF_BROADCAST_ADDRESS):
                try:
                    ipaddress.IPv4Address(address)
                except Exception as ex:
                    raise _FlowException("invalid_ip_address", address) from ex
                self.conf[CONF_BROADCAST_ADDRESS] = address
            self.conf[CONF_USE_CLOUD] = user_input[CONF_USE_CLOUD]
            self.conf[CONF_DETECT_AC_APPLIANCES] = user_input[CONF_DETECT_AC_APPLIANCES]
        else:
            self.conf = user_input
            self.conf[CONF_USE_CLOUD] = False
            self.conf[CONF_DETECT_AC_APPLIANCES] = False
            app = user_input.get(CONF_MOBILE_APP, DEFAULT_APP)
            self.conf.update(SUPPORTED_APPS.get(app, SUPPORTED_APPS[DEFAULT_APP]))
            if user_input.get(CONF_ADVANCED_SETTINGS):
                return await self.async_step_advanced_settings()

        self.appliance_idx = -1

        await self.hass.async_add_executor_job(self._connect_and_discover)

        if self.conf[CONF_USE_CLOUD]:
            for i, appliance in enumerate(self.appliances):
                self.devices_conf[i][CONF_USE_CLOUD] = True
        else:
            for i, appliance in enumerate(self.appliances):
                if supported_appliance(self.conf, appliance) and not appliance.address:
                    self.appliance_idx = i
                    break
            if self.appliance_idx >= 0:
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
        use_cloud = user_input.get(CONF_USE_CLOUD, self.conf.get(CONF_USE_CLOUD, False))

        return self.async_show_form(
            step_id="advanced_settings",
            data_schema=_advanced_settings_schema(
                username=username,
                password=password,
                appkey=appkey,
                appid=appid,
                broadcast_address=broadcast_address,
                use_cloud=use_cloud,
            ),
            description_placeholders=_placeholders(self.error_cause),
            errors=self.errors,
        )

    async def async_step_unreachable_appliance(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the appliances that were not discovered automatically on LAN."""
        errors: dict = {}
        self.error_cause = ""
        appliance = self.appliances[self.appliance_idx]
        device_conf = self.devices_conf[self.appliance_idx]

        if user_input is not None:
            what_to_do = user_input.get(CONF_WHAT_TO_DO, str(LAN))
            appliance.address = (
                user_input.get(CONF_IP_ADDRESS, UNKNOWN_IP)
                if what_to_do == LAN
                else UNKNOWN_IP
            )
            appliance.name = user_input.get(CONF_NAME, appliance.name)
            appliance.token = user_input.get(CONF_TOKEN, "")
            appliance.key = user_input.get(CONF_TOKEN_KEY, "")

            device_conf[CONF_EXCLUDE] = what_to_do == IGNORE
            device_conf[CONF_USE_CLOUD] = what_to_do == USE_CLOUD

            try:
                await self.hass.async_add_executor_job(
                    _validate_appliance,
                    self.cloud,
                    self.client,
                    appliance,
                    device_conf,
                )
                # Find next unreachable appliance
                self.appliance_idx = self.appliance_idx + 1
                while self.appliance_idx < len(self.appliances):
                    if supported_appliance(self.conf, appliance):
                        if not self.appliances[self.appliance_idx].address:
                            return await self.async_step_unreachable_appliance()
                    self.appliance_idx = self.appliance_idx + 1

                # If no unreachable appliances, create entry
                if self.appliance_idx >= len(self.appliances):
                    return await self._async_add_entry()
                appliance = self.appliances[self.appliance_idx]

            except _FlowException as ex:
                self.error_cause = str(ex.cause)
                errors["base"] = ex.message

        name = appliance.name
        return self.async_show_form(
            step_id="unreachable_appliance",
            data_schema=_unreachable_appliance_schema(name),
            description_placeholders=_placeholders(self.error_cause, appliance),
            errors=errors,
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
        username = self.conf.get(CONF_USERNAME, DEFAULT_USERNAME)
        password = ""
        appkey = self.conf.get(CONF_APPKEY, DEFAULT_APPKEY)
        appid = self.conf.get(CONF_APPID, DEFAULT_APP_ID)
        if user_input is not None:
            password = user_input.get(CONF_PASSWORD, "")
            appkey = user_input.get(CONF_APPKEY, DEFAULT_APPKEY)
            appid = user_input.get(CONF_APPID, DEFAULT_APP_ID)
            try:
                await self.hass.async_add_executor_job(
                    _connect_to_cloud, self, user_input
                )
            except Exception as ex:  # pylint: disable=broad-except
                self._process_exception(ex)
            else:
                self.conf[CONF_USERNAME] = username
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
        self.error_cause = ""
        self.devices_conf: list[dict[str, Any]] = []
        self.conf = {**config_entry.data}
        self.client = MideaClient()
        self.cloud: MideaCloud | None = None
        self.appliance_idx = -1

    async def async_step_init(self, user_input: ConfigType | None = None) -> FlowResult:
        """Starts options flow"""
        self._build_appliance_list()
        return await self.async_step_appliance(user_input)

    async def async_step_appliance(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Options for an appliance"""
        return await _async_step_appliance("appliance", self, user_input)

    def _build_appliance_list(self):
        hub: Hub = self.hass.data[DOMAIN][self.config_entry.entry_id]
        self.appliances = []
        self.devices_conf = self.conf[CONF_DEVICES]
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
                self.appliances.append(appliance)
        self.appliance_idx = 0
