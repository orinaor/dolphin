import logging
from typing import Callable, List
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.helpers.entity import Entity
import homeassistant.core
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .coordinator import UpdateCoordinator
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id
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
    coordinator: UpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    switches = []

    for device in coordinator.data.keys():
        if (
            await coordinator.dolphin.isEnergyMeter(coordinator.dolphin._user, device)
            == "1"
        ):
            switches.append(
                PowerSensor(hass=hass, coordinator=coordinator, device=device)
            )
        switches.append(
            EstimatedTimeSensor(hass=hass, coordinator=coordinator, device=device)
        )

    async_add_entities(switches)


class PowerSensor(CoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    def __init__(self, hass, coordinator, device):
        CoordinatorEntity.__init__(self, coordinator)
        self._hass = hass
        self._device = device
        self._coordinator = coordinator
        self.entity_id = async_generate_entity_id(
            DOMAIN + ".{}", f"{device}_electric_current", hass=hass
        )

    @property
    def unique_id(self):
        return self.entity_id

    @property
    def name(self):
        return "Electric current"

    @property
    def icon(self):
        return "mdi:lightning-bolt"

    @property
    def native_value(self):
        return self._coordinator.data[self._device].energy

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device)},
            name=self.name,
        )


class EstimatedTimeSensor(CoordinatorEntity, SensorEntity):
    """Sensor for estimated target time."""

    def __init__(self, hass, coordinator, device):
        CoordinatorEntity.__init__(self, coordinator)
        self._hass = hass
        self._device = device
        self._coordinator = coordinator
        self.entity_id = async_generate_entity_id(
            DOMAIN + ".{}", f"{device}_estimated_target_time", hass=hass
        )

    @property
    def unique_id(self):
        return self.entity_id

    @property
    def name(self):
        return "Estimated target time"

    @property
    def icon(self):
        return "mdi:timer-sand"

    @property
    def native_value(self):
        return self._coordinator.data[self._device].estimatedTargetTime

    @property
    def available(self):
        """Return availability."""
        return (
            self._coordinator.data[self._device].power
            and self._coordinator.data[self._device].estimatedTargetTime is not None
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device)},
        )
