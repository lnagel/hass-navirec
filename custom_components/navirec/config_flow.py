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
from .const import (
    CONF_ACCOUNT_ID,
    CONF_API_TOKEN,
    CONF_API_URL,
    DEFAULT_API_URL,
    DOMAIN,
    LOGGER,
)


def _normalize_account_id(user_input: dict[str, Any]) -> str | None:
    """Normalize account_id from user input, returning None for empty strings."""
    return user_input.get(CONF_ACCOUNT_ID, "").strip() or None


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
            user_account_id = _normalize_account_id(user_input)

            try:
                account = await self._validate_and_get_account(
                    api_url, api_token, user_account_id
                )
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
                account_id = account["id"]
                account_name = account.get("name") or account_id

                # Use account_id as unique ID
                await self.async_set_unique_id(account_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=account_name,
                    data={
                        CONF_API_URL: api_url,
                        CONF_API_TOKEN: api_token,
                        CONF_ACCOUNT_ID: account_id,
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
                    vol.Optional(
                        CONF_ACCOUNT_ID,
                        default=(user_input or {}).get(CONF_ACCOUNT_ID, ""),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                },
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            api_url = user_input[CONF_API_URL].rstrip("/")
            api_token = user_input[CONF_API_TOKEN]
            user_account_id = _normalize_account_id(user_input)

            try:
                account = await self._validate_and_get_account(
                    api_url, api_token, user_account_id
                )
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
                account_id = account["id"]
                account_name = account.get("name") or account_id

                # Update unique ID if account changed
                await self.async_set_unique_id(account_id)
                self._abort_if_unique_id_mismatch()

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=account_name,
                    data={
                        CONF_API_URL: api_url,
                        CONF_API_TOKEN: api_token,
                        CONF_ACCOUNT_ID: account_id,
                    },
                )

        # Pre-fill with current values
        current_data = reconfigure_entry.data

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_API_URL,
                        default=(user_input or current_data).get(
                            CONF_API_URL, DEFAULT_API_URL
                        ),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.URL,
                        ),
                    ),
                    vol.Required(
                        CONF_API_TOKEN,
                        default=(user_input or current_data).get(CONF_API_TOKEN, ""),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                    vol.Optional(
                        CONF_ACCOUNT_ID,
                        default=(user_input or current_data).get(CONF_ACCOUNT_ID, ""),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                },
            ),
            errors=errors,
        )

    async def _validate_and_get_account(
        self, api_url: str, api_token: str, account_id: str | None
    ) -> dict[str, Any]:
        """
        Validate credentials and return the account to use.

        If account_id is provided, validates that it exists.
        Otherwise, returns the first available account.
        """
        client = NavirecApiClient(
            api_url=api_url,
            api_token=api_token,
            session=async_create_clientsession(self.hass),
        )

        # Fetch all accounts
        accounts = await client.async_get_accounts()
        if not accounts:
            msg = "No accounts found for this token"
            raise NavirecApiClientAuthenticationError(msg)

        # If account_id is provided, find that specific account
        if account_id:
            for account in accounts:
                if account.get("id") == account_id:
                    return account
            # Account not found
            msg = f"Account {account_id} not found or not accessible"
            raise NavirecApiClientAuthenticationError(msg)

        # No account_id provided, use the first one
        return accounts[0]
