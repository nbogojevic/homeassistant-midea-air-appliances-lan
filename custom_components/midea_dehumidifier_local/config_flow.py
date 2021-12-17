"""Config flow for Midea Dehumidifier (Local) integration."""
from __future__ import annotations

import ipaddress
import logging
from typing import Tuple

from midea_beautiful_dehumidifier import find_appliances, connect_to_cloud
from midea_beautiful_dehumidifier.cloud import MideaCloud
from midea_beautiful_dehumidifier.lan import LanDevice, get_appliance_state
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import (
    CONF_DEVICES,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TOKEN,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    DEFAULT_ANNOUNCE_PORT,
    CONF_APP_KEY,
    CONF_TOKEN_KEY,
    CONF_IGNORE_APPLIANCE,
    IGNORED_IP_ADDRESS,
)

_LOGGER = logging.getLogger(__name__)


def validate_input(
    hass: HomeAssistant, conf: dict
) -> Tuple[MideaCloud, list[LanDevice]]:
    cloud = connect_to_cloud(
        appkey=conf[CONF_APP_KEY],
        account=conf[CONF_USERNAME],
        password=conf[CONF_PASSWORD],
    )
    if cloud is None:
        raise exceptions.IntegrationError("no_cloud")
    appliances = find_appliances(
        cloud=cloud,
        broadcast_retries=2,
        broadcast_timeout=3,
    )
    for appliance in appliances:
        _LOGGER.info("%s", appliance)
    return cloud, appliances


def validate_appliance(
    hass: HomeAssistant, cloud: MideaCloud, appliance: LanDevice
):
    _LOGGER.debug("Validating id=%s ip=%s", appliance.id, appliance.ip)
    _LOGGER.debug(" token=%s key=%s", appliance.token, appliance.key)
    if appliance.ip == IGNORED_IP_ADDRESS:
        _LOGGER.debug("Ignored appliance with id=%s", appliance.ip)
        return True
    ipaddress.IPv4Network(appliance.ip)
    discovered = get_appliance_state(ip=appliance.ip, cloud=cloud)
    if discovered is not None:
        appliance.update(discovered)
        return True
    raise exceptions.IntegrationError("not_discovered")



class MideaLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    def __init__(self):
        self._cloud_credentials: dict | None = None
        self._cloud = None
        self._appliance_idx = -1
        self._appliances: list[LanDevice] = []

    async def async_step_user(self, user_input: dict):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict = {}

        if user_input is not None:
            (
                self._cloud,
                self._appliances,
            ) = await self.hass.async_add_executor_job(
                validate_input, self.hass, user_input
            )
            self._appliance_idx = -1
            self._conf = user_input
            for i, a in enumerate(self._appliances):
                if not a.ip:
                    self._appliance_idx = i
                    break
            if self._appliance_idx >= 0:
                return await self.async_step_unreachable_appliance()

            return await self._async_add_entry()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=""
                    ): vol.All(cv.string, vol.Length(min=3)),
                    vol.Required(CONF_PASSWORD, default=""): vol.All(
                        cv.string, vol.Length(min=6)
                    ),
                    vol.Required(
                        CONF_APP_KEY,
                        default="3742e9e5842d4ad59c2db887e12449f9",
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_unreachable_appliance(self, user_input=None):
        """Manage the appliances that were not found on LAN."""
        errors: dict = {}
        if user_input is not None:
            _LOGGER.info(
                "async_step_unreachable_appliance(user_input)=%s", user_input
            )
            self._appliances[self._appliance_idx].ip = (
                user_input[CONF_IP_ADDRESS]
                if not user_input[CONF_IGNORE_APPLIANCE]
                else IGNORED_IP_ADDRESS
            )
            self._appliances[self._appliance_idx].port = user_input[CONF_PORT]
            self._appliances[self._appliance_idx].token = (
                user_input[CONF_TOKEN]
                if hasattr(user_input, CONF_TOKEN)
                else ""
            )
            self._appliances[self._appliance_idx].key = (
                user_input[CONF_TOKEN_KEY]
                if hasattr(user_input, CONF_TOKEN_KEY)
                else ""
            )
            try:
                await self.hass.async_add_executor_job(
                    validate_appliance,
                    self.hass,
                    self._cloud,
                    self._appliances[self._appliance_idx],
                )
                # Find next unreachable appliance
                self._appliance_idx = self._appliance_idx + 1
                while self._appliance_idx < len(self._appliances):
                    if self._appliances[self._appliance_idx].ip is None:
                        return await self.async_step_unreachable_appliance()
                    self._appliance_idx = self._appliance_idx + 1

                # If no unreachable appliances, create entry
                if self._appliance_idx >= len(self._appliances):
                    return await self._async_add_entry()
            except Exception:
                logging.error("Exception while validating appliance", exc_info=True)
                errors["base"] = "invalid_ip_address"

        _LOGGER.info(
            "Showing unreachable appliance! %d %s",
            self._appliance_idx,
            self._appliances[self._appliance_idx].id,
        )
        return self.async_show_form(
            step_id="unreachable_appliance",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IGNORE_APPLIANCE, default=False): bool,
                    vol.Optional(
                        CONF_IP_ADDRESS, default=IGNORED_IP_ADDRESS
                    ): str,
                    vol.Required(
                        CONF_PORT, default=DEFAULT_ANNOUNCE_PORT
                    ): cv.port,
                    vol.Optional(CONF_TOKEN): str,
                    vol.Optional(CONF_TOKEN_KEY): str,
                }
            ),
            description_placeholders={
                CONF_ID: self._appliances[self._appliance_idx].id
                if self._appliance_idx < len(self._appliances)
                else "",
                CONF_NAME: self._appliances[self._appliance_idx].state.name
                if self._appliance_idx < len(self._appliances)
                else "",
            },
            errors=errors,
        )

    async def _async_add_entry(self):
        if self._conf is not None:
            self._appliance_conf = []
            for a in self._appliances:
                if a.ip != IGNORED_IP_ADDRESS:
                    self._appliance_conf.append({
                        CONF_IP_ADDRESS: a.ip,
                        CONF_ID: a.id,
                        CONF_NAME: a.state.name,
                        CONF_TYPE: a.type,
                        CONF_TOKEN: a.token,
                        CONF_TOKEN_KEY: a.key,
                    })
            existing_entry = await self.async_set_unique_id(
                self._conf[CONF_USERNAME]
            )
            self._conf[CONF_DEVICES] = self._appliance_conf
            if existing_entry:
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data=self._conf,
                )
                # Reload the config entry otherwise devices will remain unavailable
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(
                        existing_entry.entry_id
                    )
                )

                return self.async_abort(reason="reauth_successful")
            else:
                return self.async_create_entry(
                    title="Midea Dehumidifiers",
                    data=self._conf,
                )
        else:
            raise exceptions.InvalidStateError("unexpected_state")
