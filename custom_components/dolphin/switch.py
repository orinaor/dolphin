import logging
from typing import Callable, List
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ServiceValidationError
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
    """Set up Dolphin switch based on a config entry."""
    coordinator: UpdateCoordinator = entry.runtime_data
    switches = []

    for device in coordinator.data.keys():
        switches.append(ShabbatSwitch(hass=hass, coordinator=coordinator, device=device))
        switches.append(FixedTemperature(hass=hass, coordinator=coordinator, device=device))
        for switch in range(1, 7):
            switches.append(DropSwitch(hass=hass, coordinator=coordinator, index=switch, device=device))

    async_add_entities(switches)


class DropSwitch(CoordinatorEntity, SwitchEntity):

    def __init__(self, hass, coordinator, index, device):
        CoordinatorEntity.__init__(self, coordinator)
        self._hass = hass
        self._id = index
        self._coordinator = coordinator
        self._device = device
        self._is_on = False
        self._attr_unique_id = entity_unique_id(device, f"drop{index}")
        self.entity_id = f"switch.{self._attr_unique_id.split('.', 1)[1]}"

    @property
    def name(self):
        if self._coordinator.data[self._device].showerTemperature != None:
            showerTemperature = self._coordinator.data[self._device].showerTemperature[self._id - 1]['temp'] if len(
                self._coordinator.data[self._device].showerTemperature) > self._id - 1 else None
        else:
            showerTemperature = None
        return f"{self._id} Shower - {showerTemperature}°C" if self._id == 1 else f"{self._id} Showers - {showerTemperature}°C"

    @property
    def icon(self):
        return "mdi:shower"

    @property
    def _drop_temperature(self):
        """Temperature of this drop, or None if the device has fewer drops."""
        showers = self._coordinator.data[self._device].showerTemperature
        if showers is not None and len(showers) > self._id - 1:
            return showers[self._id - 1]['temp']
        return None

    @property
    def available(self):
        """Return availability.

        A drop stays available while the boiler heats for another drop; it then
        just reports off, so the UI does not look like the device is offline.
        """
        if not super().available or self._device not in self._coordinator.data:
            return False
        if self._coordinator.data[self._device].shabbat:
            return False
        if self._coordinator.data[self._device].fixedTemperature:
            return False
        return self._drop_temperature is not None

    @property
    def is_on(self):
        device = self._coordinator.data[self._device]
        if not device.power:
            self._is_on = False
            return False
        if device.targetTemperature is not None and self._drop_temperature is not None:
            # Heating was started for this drop's temperature, whoever started it.
            return device.targetTemperature == self._drop_temperature
        return self._is_on

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._device)
            },
        )

    async def async_turn_on(self):
        device = self._coordinator.data[self._device]
        current_temp = device.temperature
        drop_temperature = self._drop_temperature

        if device.power:
            raise ServiceValidationError(
                f"The boiler is already heating to {device.targetTemperature}°C; turn it off first"
            )
        if current_temp is not None and current_temp > drop_temperature:
            raise ServiceValidationError(
                f"The water is already {current_temp}°C, hotter than {drop_temperature}°C"
            )

        await self._coordinator.dolphin.turnOnManually(self._coordinator.dolphin._user, drop_temperature,
                                                       self._device)
        self._is_on = True
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_turn_off(self):

        await self._coordinator.dolphin.turnOffManually(self._coordinator.dolphin._user, self._device)
        self._is_on = False
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()


class ShabbatSwitch(CoordinatorEntity, SwitchEntity):

    def __init__(self, hass, coordinator, device):
        CoordinatorEntity.__init__(self, coordinator)
        self._hass = hass
        self._coordinator = coordinator
        self._device = device
        self._attr_unique_id = entity_unique_id(device, "sabbath_mode")
        self.entity_id = f"switch.{self._attr_unique_id.split('.', 1)[1]}"

    @property
    def name(self):
        return "Sabbath mode"

    @property
    def icon(self):
        return "mdi:star-david"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._device)
            },
            name=self.name,
        )

    @property
    def is_on(self):
        return self._coordinator.data[self._device].shabbat

    async def async_turn_on(self):
        await self._coordinator.dolphin.enableShabbat(self._coordinator.dolphin._user, self._device)
        self._coordinator.data[self._device].shabbat = True
        self.async_write_ha_state()

    async def async_turn_off(self):
        await self._coordinator.dolphin.disableShabbat(self._coordinator.dolphin._user, self._device)
        self._coordinator.data[self._device].shabbat = False
        self.async_write_ha_state()


class FixedTemperature(CoordinatorEntity, SwitchEntity):

    def __init__(self, hass, coordinator, device):
        CoordinatorEntity.__init__(self, coordinator)
        self._hass = hass
        self._coordinator = coordinator
        self._device = device
        self._attr_unique_id = entity_unique_id(device, "fixed_temperature")
        self.entity_id = f"switch.{self._attr_unique_id.split('.', 1)[1]}"

    @property
    def name(self):
        return "Fixed temperature"

    @property
    def icon(self):
        return "mdi:home-thermometer-outline"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._device)
            },
            name=self.name,
        )

    @property
    def is_on(self):
        return self._coordinator.data[self._device].fixedTemperature

    async def async_turn_on(self):
        await self._coordinator.dolphin.turnOnFixedTemperature(self._coordinator.dolphin._user, self._device,
                                                               self._coordinator.data[self._device].targetTemperature)
        self._coordinator.data[self._device].fixedTemperature = True
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_turn_off(self):
        await self._coordinator.dolphin.turnOffFixedTemperature(self._coordinator.dolphin._user, self._device)
        self._coordinator.data[self._device].fixedTemperature = False
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()
