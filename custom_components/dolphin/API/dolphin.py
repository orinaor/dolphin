import socket
from typing import Any
import aiohttp
from yarl import URL
import asyncio
import json
import logging

from homeassistant.exceptions import HomeAssistantError

from .models import User, Device

_LOGGER = logging.getLogger(__name__)


class DolphinError(HomeAssistantError):
    """Generic Dolphin API error."""


class DolphinConnectionError(DolphinError):
    """Dolphin cloud could not be reached."""


class DolphinAuthError(DolphinError):
    """Dolphin cloud rejected the credentials."""


class Dolphin:
    """Main class for handling connections with Dolphin."""

    host: str = "api.dolphinboiler.com"
    request_timeout: float = 10.0

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self._device: dict[str, Device] = {}
        self._user: User | None = None

    async def request(self, uri: str = "", method: str = "POST", data: dict[str, Any] | None = None,
                      expect_json: bool = True) -> Any:
        url = URL.build(scheme="https", host=self.host, path=uri)

        try:
            async with asyncio.timeout(self.request_timeout):
                response = await self.session.request(method, url, data=data)
                response.raise_for_status()
                text = await response.text("UTF-8")
        except asyncio.TimeoutError as exception:
            raise DolphinConnectionError(f"Timeout while requesting {uri}") from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            raise DolphinConnectionError(f"Error while requesting {uri}: {exception}") from exception

        if "getAPIkey" in url.path or not expect_json:
            return text.strip()
        if not text.strip():
            return None
        try:
            return json.loads(text)
        except ValueError as exception:
            raise DolphinError(f"Invalid response from {uri}: {text[:100]!r}") from exception

    async def login(self, email: str, password: str) -> User:
        """Fetch a fresh API key and the device list."""
        user = User(None)
        user.email = email
        await self.getAPIKey(user, password)
        await self.getDevices(user)
        self._user = user
        return user

    async def update(self, user: User) -> dict[str, Device]:
        for device in user.device:
            data = {
                "deviceName": device['deviceName'],
                "email": user.email,
                "API_Key": user.api,
            }
            response = await self.request("/HA/V1/getMainScreenData.php", "POST", data)

            if not response:
                # The API returns nothing for some states (e.g. Shabbat); keep the last known state.
                _LOGGER.debug("No data received for device %s, keeping last known state", device['deviceName'])
                response = {}
            elif not isinstance(response, dict):
                raise DolphinError(f"Unexpected response for device {device['deviceName']}: {response!r}")

            if device['deviceName'] not in self._device:
                self._device[device['deviceName']] = Device(response)
            else:
                self._device[device['deviceName']].update_from_dict(response)

        return self._device

    async def getAPIKey(self, user: User, password: str) -> User:
        data = {
            "email": user.email,
            "password": password,
        }
        api_key = await self.request("/HA/V1/getAPIkey.php", "POST", data)
        if not api_key:
            raise DolphinError("Empty API key response")
        if api_key == "failed":
            raise DolphinAuthError("Invalid username or password")

        user.update_from_dict(api_key)
        return user

    async def getDevices(self, user: User) -> User:
        data = {
            "email": user.email,
            "API_Key": user.api,
        }
        devices = await self.request("/HA/V1//getDevices.php", "POST", data)
        if not isinstance(devices, list):
            raise DolphinError(f"Unexpected device list response: {devices!r}")

        user.update_from_dict(devices)
        return user

    async def turnOnManually(self, user: User, temperature: str, deviceName: str):
        data = {
            "deviceName": deviceName,
            "temperature": temperature,
            "email": user.email,
            "API_Key": user.api,
        }

        await self.request("/HA/V1/turnOnManually.php", "POST", data, expect_json=False)

    async def turnOffManually(self, user: User, deviceName: str):
        data = {
            "deviceName": deviceName,
            "email": user.email,
            "API_Key": user.api,
        }

        await self.request("/HA/V1/turnOffManually.php", "POST", data, expect_json=False)

    async def enableShabbat(self, user: User, deviceName: str):
        data = {
            "deviceName": deviceName,
            "email": user.email,
            "API_Key": user.api,
        }

        await self.request("/HA/V1/enableShabbat.php", "POST", data, expect_json=False)

    async def disableShabbat(self, user: User, deviceName: str):
        data = {
            "deviceName": deviceName,
            "email": user.email,
            "API_Key": user.api,
        }

        await self.request("/HA/V1/disableShabbat.php", "POST", data, expect_json=False)

    async def isEnergyMeter(self, user: User, deviceName: str):
        data = {
            "deviceName": deviceName,
            "email": user.email,
            "API_Key": user.api,
        }

        # Older devices have no current meter and answer {"isEnergyMeter": "0"}.
        if not isinstance(data := await self.request("/HA/V1/isEnergyMeter.php", "POST", data), dict):
            return 0
        return data.get('isEnergyMeter', 0)

    async def turnOnFixedTemperature(self, user: User, deviceName: str, temperature: str):
        data = {
            "deviceName": deviceName,
            "temperature": temperature,
            "email": user.email,
            "API_Key": user.api,
        }

        await self.request("/HA/V1/setFixedTemperature.php", "POST", data, expect_json=False)

    async def turnOffFixedTemperature(self, user: User, deviceName: str):
        data = {
            "deviceName": deviceName,
            "email": user.email,
            "API_Key": user.api,
        }

        await self.request("/HA/V1/turnOffFixedTemperature.php", "POST", data, expect_json=False)
