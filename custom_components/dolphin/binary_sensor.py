import logging
from typing import Callable, List
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import Entity
import homeassistant.core
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .coordinator import UpdateCoordinator, entity_unique_id
from homeassistant.helpers.entity import DeviceInfo
from .const import (
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
        hass: homeassistant.core.HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    coordinator: UpdateCoordinator = entry.runtime_data

    async_add_entities(CloudConnectivity(coordinator=coordinator, device=device) for device in coordinator.data)


class CloudConnectivity(CoordinatorEntity, BinarySensorEntity):
    """Whether the Dolphin cloud answered the last poll."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Cloud connection"

    def __init__(self, coordinator, device):
        CoordinatorEntity.__init__(self, coordinator)
        self._device = device
        self._attr_unique_id = entity_unique_id(device, "connectivity")
        self.entity_id = f"binary_sensor.{self._attr_unique_id.split('.', 1)[1]}"

    @property
    def available(self):
        """Always available: this entity reports the outage itself."""
        return True

    @property
    def is_on(self):
        return self.coordinator.last_update_success

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._device)
            },
        )
