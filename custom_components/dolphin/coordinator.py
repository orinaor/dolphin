import logging
from datetime import datetime

from .API.dolphin import Dolphin, DolphinAuthError, DolphinError, User, Device

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util, slugify

from .const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    OFFLINE_NOTIFY_AFTER,
    UPDATE_INTERVAL,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)

# entry_id -> time the Dolphin cloud was first seen unreachable. Kept outside the
# coordinator so it survives ConfigEntryNotReady retries during setup.
_DOWN_SINCE = f"{DOMAIN}_down_since"


def entity_unique_id(device: str, suffix: str) -> str:
    """Unique id matching what earlier versions registered (dolphin.<device>_<suffix>)."""
    return f"{DOMAIN}.{slugify(f'{device}_{suffix}')}"


def _notification_id(entry: ConfigEntry) -> str:
    return f"{DOMAIN}_{entry.entry_id}_offline"


def async_mark_down(hass: HomeAssistant, entry: ConfigEntry, err: Exception) -> None:
    """Record a failed connection and notify once it has lasted long enough."""
    down_since: dict[str, datetime] = hass.data.setdefault(_DOWN_SINCE, {})
    since = down_since.setdefault(entry.entry_id, dt_util.utcnow())
    if dt_util.utcnow() - since >= OFFLINE_NOTIFY_AFTER:
        persistent_notification.async_create(
            hass,
            f"Dolphin cloud has been unreachable since {dt_util.as_local(since):%H:%M:%S}.\n\nLast error: {err}",
            title="Dolphin unavailable",
            notification_id=_notification_id(entry),
        )


def async_mark_up(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clear the outage state and its notification."""
    if hass.data.get(_DOWN_SINCE, {}).pop(entry.entry_id, None) is not None:
        persistent_notification.async_dismiss(hass, _notification_id(entry))


class UpdateCoordinator(DataUpdateCoordinator[dict[str, Device]]):
    """Class to manage fetching Dolphin data from single endpoint."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, dolphin: Dolphin):
        """Initialize global Dolphin data updater."""
        self.dolphin = dolphin
        self.user: User | None = None
        self.energy_meters: dict[str, bool] = {}
        self._entry = entry
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch data from Dolphin, logging in again after any failure."""
        try:
            if self.user is None:
                self.user = await self.dolphin.login(
                    self._entry.data[CONF_USERNAME], self._entry.data[CONF_PASSWORD]
                )
            data = await self.dolphin.update(self.user)
        except DolphinAuthError as err:
            self.user = None
            if self.data is None:
                raise ConfigEntryError(str(err)) from err
            async_mark_down(self.hass, self._entry, err)
            raise UpdateFailed(str(err)) from err
        except DolphinError as err:
            # The API key may have expired or the cloud restarted; re-login on the next poll.
            self.user = None
            async_mark_down(self.hass, self._entry, err)
            raise UpdateFailed(str(err)) from err

        async_mark_up(self.hass, self._entry)
        return data
