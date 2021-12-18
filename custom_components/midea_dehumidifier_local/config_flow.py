"""Config flow for Midea Dehumidifier (Local) integration."""
from __future__ import annotations

import ipaddress
import logging
from typing import Tuple

from midea_beautiful_dehumidifier import connect_to_cloud, find_appliances
from midea_beautiful_dehumidifier.cloud import MideaCloud
from midea_beautiful_dehumidifier.exceptions import CloudAuthenticationError
from midea_beautiful_dehumidifier.lan import LanDevice, get_appliance_state
from midea_beautiful_dehumidifier.midea import DEFAULT_APPKEY, DISCOVERY_PORT
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import (
    CONF_DEVICES,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_IGNORE_APPLIANCE,
    CONF_TOKEN_KEY,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    DOMAIN,
    IGNORED_IP_ADDRESS,
)

_LOGGER = logging.getLogger(__name__)


def validate_input(conf: dict) -> Tuple[MideaCloud, list[LanDevice]]:
    cloud = connect_to_cloud(
        appkey=DEFAULT_APPKEY,
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

    return cloud, appliances


def validate_appliance(cloud: MideaCloud, appliance: LanDevice):
    if appliance.ip == IGNORED_IP_ADDRESS or appliance.ip is None:
        _LOGGER.debug("Ignored appliance with id=%s", appliance.id)
        return True
    try:
        ipaddress.IPv4Network(appliance.ip)
    except Exception:
        raise exceptions.IntegrationError("invalid_ip_address")
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

    async def async_step_user(self, input: dict):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict = {}

        if input is not None:
            try:
                (
                    self._cloud,
                    self._appliances,
                ) = await self.hass.async_add_executor_job(
                    validate_input, input
                )
                self._appliance_idx = -1
                self._conf = input
                self._conf[""]
                for i, a in enumerate(self._appliances):
                    if not a.ip:
                        self._appliance_idx = i
                        break
                if self._appliance_idx >= 0:
                    return await self.async_step_unreachable_appliance()

                return await self._async_add_entry()
            except CloudAuthenticationError as ex:
                _LOGGER.error("Unable to log in to Midea cloud %s", ex)
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=DEFAULT_USERNAME
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=DEFAULT_PASSWORD
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_unreachable_appliance(self, input=None):
        """Manage the appliances that were not found on LAN."""
        errors: dict = {}
        appliance = self._appliances[self._appliance_idx]

        if input is not None:
            appliance.ip = (
                input[CONF_IP_ADDRESS]
                if not input[CONF_IGNORE_APPLIANCE]
                else IGNORED_IP_ADDRESS
            )
            appliance.port = DISCOVERY_PORT
            appliance.name = input[CONF_NAME]
            appliance.token = input[CONF_TOKEN] if CONF_TOKEN in input else ""
            appliance.key = (
                input[CONF_TOKEN_KEY] if CONF_TOKEN_KEY in input else ""
            )
            try:
                await self.hass.async_add_executor_job(
                    validate_appliance,
                    self._cloud,
                    appliance,
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
                appliance = self._appliances[self._appliance_idx]

            except exceptions.IntegrationError as ex:
                errors["base"] = str(ex)
            except Exception:
                logging.error(
                    "Exception while validating appliance", exc_info=True
                )
                errors["base"] = "invalid_ip_address"

        name = appliance.name
        return self.async_show_form(
            step_id="unreachable_appliance",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IGNORE_APPLIANCE, default=False): bool,
                    vol.Optional(
                        CONF_IP_ADDRESS, default=IGNORED_IP_ADDRESS
                    ): str,
                    vol.Optional(CONF_NAME, default=name): str,
                    vol.Optional(CONF_TOKEN): str,
                    vol.Optional(CONF_TOKEN_KEY): str,
                }
            ),
            description_placeholders={
                CONF_ID: appliance.id,
                CONF_NAME: name,
            },
            errors=errors,
        )

    async def _async_add_entry(self):
        if self._conf is not None:
            self._appliance_conf = []
            for a in self._appliances:
                if a.ip != IGNORED_IP_ADDRESS:
                    self._appliance_conf.append(
                        {
                            CONF_IP_ADDRESS: a.ip,
                            CONF_ID: a.id,
                            CONF_NAME: a.name,
                            CONF_TYPE: a.type,
                            CONF_TOKEN: a.token,
                            CONF_TOKEN_KEY: a.key,
                        }
                    )
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
