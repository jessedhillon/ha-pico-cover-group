from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import (
    STATE_OPEN,
    STATE_OPENING,
    STATE_CLOSING,
    STATE_CLOSED,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> bool:
    """Set up cover entities for this config entry."""
    entity = CoverGroupEntity(hass=hass, unique_id=entry.entry_id, **entry.data)
    async_add_entities([entity])
    return True


class CoverGroupEntity(CoverEntity):
    _attr_should_poll = False

    def __init__(
        self,
        hass,
        name: str,
        covers: list[str],
        open_button: str,
        close_button: str,
        stop_button: str,
        unique_id: str,
    ) -> None:
        self.hass = hass
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._covers = covers
        self._open_button = open_button
        self._close_button = close_button
        self._stop_button = stop_button

        self._unsub = None
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    async def async_added_to_hass(self) -> None:
        # subscribe to state changes of member covers
        self._unsub = async_track_state_change_event(
            self.hass, self._covers, self._handle_member_state_change
        )

        # initialize state based on current member states
        await self._async_recalc_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    @callback
    async def _handle_member_state_change(self, event) -> None:
        await self._async_recalc_state()

    async def _async_recalc_state(self) -> None:
        states = [self.hass.states.get(eid) for eid in self._covers]
        states = [s for s in states if s is not None]
        positions = [state.attributes["current_position"]
                     for state in states if isinstance(state.attributes.get("current_position"), (int, float))]

        if positions:
            self._attr_current_cover_position = round(sum(positions) / len(positions))

        if not states:
            self._attr_is_closed = None
            self._attr_is_opening = False
            self._attr_is_closing = False
            self.async_write_ha_state()
            return

        values = {s.state for s in states}

        opening = STATE_OPENING in values
        closing = STATE_CLOSING in values
        open_ = STATE_OPEN in values
        closed = values == {STATE_CLOSED}

        # basic precedence
        self._attr_is_opening = opening
        self._attr_is_closing = closing
        self._attr_is_closed = closed if not (opening or closing) else None
        self._attr_is_open = open_

        self.async_write_ha_state()

    def _calc_group_position(self) -> int | None:
        positions = []
        for eid in self._covers:
            state = self.hass.states.get(eid)
            if not state:
                continue
            pos = state.attributes.get("current_position")
            if isinstance(pos, (int, float)):
                positions.append(int(pos))

        if not positions:
            return None

        return round(sum(positions) / len(positions))

    async def async_open_cover(self, **kwargs):
        await self.hass.services.async_call(
            "button",
            "press",
            {"entity_id": self._open_button},
            blocking=False,
        )

    async def async_close_cover(self, **kwargs) -> None:
        await self.hass.services.async_call(
            "button",
            "press",
            {"entity_id": self._close_button},
            blocking=False,
        )

    async def async_stop_cover(self, **kwargs) -> None:
        await self.hass.services.async_call(
            "button",
            "press",
            {"entity_id": self._stop_button},
            blocking=False,
        )

    async def async_set_cover_position(self, **kwargs) -> None:
        target = kwargs.get(ATTR_POSITION)
        if target is None:
            return

        target = max(0, min(100, int(target)))
        for eid in self._covers:
            await self.hass.services.async_call(
                "cover",
                "set_cover_position",
                {
                    "entity_id": eid,
                    ATTR_POSITION: target,
                },
                blocking=False,
            )
