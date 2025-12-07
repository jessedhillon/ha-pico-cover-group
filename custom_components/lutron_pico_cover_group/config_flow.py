import typing as t

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers import entity_registry
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN


DOMAIN = "lutron_pico_cover_group"
LUTRON_CASETA_DOMAIN = "lutron_caseta"


CoverGroupSchema = vol.Schema({
    vol.Required("name"): selector.TextSelector(
        selector.TextSelectorConfig(
            type=selector.TextSelectorType.TEXT,
        )
    ),
    vol.Required("open_button"): selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=BUTTON_DOMAIN,
            integration=LUTRON_CASETA_DOMAIN,
        )
    ),
    vol.Required("close_button"): selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=BUTTON_DOMAIN,
            integration=LUTRON_CASETA_DOMAIN,
        )
    ),
    vol.Required("stop_button"): selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=BUTTON_DOMAIN,
            integration=LUTRON_CASETA_DOMAIN,
        )
    ),
    vol.Required("covers"): selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain=COVER_DOMAIN,
            integration=LUTRON_CASETA_DOMAIN,
            multiple=True,
        )
    ),
})


class CoverGroupOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="init",
                data_schema=self.add_suggested_values_to_schema(CoverGroupSchema, self.entry.data),
            )

        if len(user_input["covers"]) == 0:
            return self.async_show_form(
                step_id="init",
                data_schema=self.add_suggested_values_to_schema(CoverGroupSchema, user_input),
                errors={
                    "covers": "no_covers_selected"
                },
            )

        self.hass.config_entries.async_update_entry(
            self.entry,
            title=user_input["name"],
            data=user_input,
        )
        return self.async_create_entry(data={})


class CoverGroupsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cover Group."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.groups = []
        self.current_group = {}
        self.pico_device = None

    async def async_step_user(
        self, user_input: dict[str, t.Any] | None = None
    ) -> FlowResult:
        return await self.async_step_start_group()

    async def async_step_start_group(
        self, user_input: dict[str, t.Any] | None = None
    ) -> FlowResult:
        """Add a cover group."""
        schema = vol.Schema({
            vol.Required("name"): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                )
            ),
        })

        if user_input is None:
            return self.async_show_form(
                step_id="start_group",
                data_schema=schema,
            )

        self.current_group = {
            "name": user_input["name"],
        }
        return await self.async_step_select_remote()

    async def async_step_select_remote(
        self, user_input: dict[str, t.Any] | None = None
    ) -> FlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="select_remote",
                data_schema=vol.Schema({
                    vol.Required("pico_device"): selector.DeviceSelector(
                        selector.DeviceSelectorConfig(
                            entity={
                                "integration": LUTRON_CASETA_DOMAIN,
                                "domain": BUTTON_DOMAIN,
                            },
                            multiple=False,
                        )
                    )
                }),
            )

        self.pico_device = user_input["pico_device"]
        return await self.async_step_select_buttons()

    async def async_step_select_buttons(
        self, user_input: dict[str, t.Any] | None = None
    ) -> FlowResult:
        if self.pico_device is None:
            self.async_abort(reason="no_lutron_buttons")

        ent_reg = entity_registry.async_get(self.hass)
        buttons = [ent for ent in ent_reg.entities.values()
                   if ent.device_id == self.pico_device and ent.domain == BUTTON_DOMAIN]
        selector_config = selector.EntitySelectorConfig(
            multiple=False,
            include_entities=[ent.entity_id for ent in buttons],
        )
        schema = vol.Schema({
            vol.Required("open_button"): selector.EntitySelector(selector_config),
            vol.Required("stop_button"): selector.EntitySelector(selector_config),
            vol.Required("close_button"): selector.EntitySelector(selector_config),
        })

        if user_input is None:
            candidates = {}
            for ent in buttons:
                slug = ent.entity_id.split(".", 1)[1]
                parts = {pt.lower() for pt in slug.split("_")}
                if "on" in parts:
                    candidates["open_button"] = ent.entity_id
                elif "off" in parts:
                    candidates["close_button"] = ent.entity_id
                elif "stop" in parts:
                    candidates["stop_button"] = ent.entity_id

            return self.async_show_form(
                step_id="select_buttons",
                data_schema=self.add_suggested_values_to_schema(schema, candidates),
            )

        if len(set(user_input.values())) != 3:
            return self.async_show_form(
                step_id="select_buttons",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={
                    "base": "duplicate_buttons",
                }
            )
        self.current_group.update(**user_input)
        return await self.async_step_select_covers()

    async def async_step_select_covers(
        self, user_input: dict[str, t.Any] | None = None
    ) -> FlowResult:
        schema = vol.Schema({
            vol.Required("covers"): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=COVER_DOMAIN,
                    integration=LUTRON_CASETA_DOMAIN,
                    multiple=True
                ),
            ),
        })
        if user_input is None:
            return self.async_show_form(
                step_id="select_covers",
                data_schema=schema,
            )
        if len(user_input["covers"]) == 0:
            return self.async_show_form(
                step_id="select_covers",
                data_schema=schema,
                errors={
                    "covers": "no_covers_selected",
                }
            )
        self.current_group.update(**user_input)
        return self.async_create_entry(
            title=self.current_group["name"],
            data=self.current_group,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return CoverGroupOptionsFlow(config_entry)
