"""Config flow for Navirec."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import (
    NavirecApiClient,
    NavirecApiClientAuthenticationError,
    NavirecApiClientCommunicationError,
    NavirecApiClientError,
)
from .const import CONF_API_TOKEN, CONF_API_URL, DEFAULT_API_URL, DOMAIN, LOGGER


class NavirecFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Navirec."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_url = user_input[CONF_API_URL].rstrip("/")
            api_token = user_input[CONF_API_TOKEN]

            try:
                accounts = await self._test_credentials(api_url, api_token)
            except NavirecApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                errors["base"] = "auth"
            except NavirecApiClientCommunicationError as exception:
                LOGGER.error(exception)
                errors["base"] = "connection"
            except NavirecApiClientError as exception:
                LOGGER.exception(exception)
                errors["base"] = "unknown"
            else:
                # Create unique ID from URL (without token for privacy)
                # Using URL ensures one entry per Navirec instance
                await self.async_set_unique_id(api_url)
                self._abort_if_unique_id_configured()

                # Use first account name as title, or "Navirec" as fallback
                title = "Navirec"
                if accounts:
                    title = accounts[0].get("name", "Navirec")

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_API_URL: api_url,
                        CONF_API_TOKEN: api_token,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_URL,
                        default=(user_input or {}).get(CONF_API_URL, DEFAULT_API_URL),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.URL,
                        ),
                    ),
                    vol.Required(CONF_API_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                },
            ),
            errors=errors,
        )

    async def _test_credentials(
        self, api_url: str, api_token: str
    ) -> list[dict[str, Any]]:
        """Validate credentials and return accounts."""
        client = NavirecApiClient(
            api_url=api_url,
            api_token=api_token,
            session=async_create_clientsession(self.hass),
        )
        # This will raise an exception if credentials are invalid
        accounts = await client.async_get_accounts()
        if not accounts:
            msg = "No accounts found for this token"
            raise NavirecApiClientAuthenticationError(msg)
        return accounts
