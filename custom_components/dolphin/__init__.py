"""Dolphin integration."""

from .API.dolphin import Dolphin, DolphinError

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_PASSWORD,
    CONF_USERNAME,
)

from .coordinator import UpdateCoordinator, async_mark_down, async_mark_up
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not entry.data.get(CONF_USERNAME) or not entry.data.get(CONF_PASSWORD):
        raise ConfigEntryError(
            "Config entry has no credentials; delete it and add the Dolphin integration again"
        )

    dolphin = Dolphin(async_get_clientsession(hass))
    coordinator = UpdateCoordinator(hass, entry, dolphin)

    # Raises ConfigEntryNotReady while the cloud is unreachable, so HA retries setup.
    await coordinator.async_config_entry_first_refresh()

    try:
        for device in coordinator.data:
            coordinator.energy_meters[device] = (
                await dolphin.isEnergyMeter(coordinator.user, device) == '1'
            )
    except DolphinError as err:
        async_mark_down(hass, entry, err)
        raise ConfigEntryNotReady(str(err)) from err
    async_mark_up(hass, entry)

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Dolphin config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clear any outage notification for a removed entry."""
    async_mark_up(hass, entry)
