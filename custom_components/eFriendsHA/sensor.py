"""
A integration read data from the eFriends Cube
"""
import logging
from datetime import timedelta

import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from custom_components.eFriendsHA.const import DOMAIN, LOCAL_BASE_URL, REMOTE_BASE_URL, NAME_POWER, CMD_POWER

CONF_IPADDR = "ip"
CONF_BALENAID = "balenaid"
CONF_APIKEY = "apikey"

SCAN_INTERVAL = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_APIKEY): cv.string,
        vol.Required(CONF_IPADDR): cv.string,
        vol.Optional(CONF_BALENAID): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)

UNIQUE_MONITORS = set()

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setup."""
    ipaddr = config.get(CONF_IPADDR)
    apikey = config.get(CONF_APIKEY)
    dev = []

    api = eFriendsAPI(async_create_clientsession(hass), hass.loop, ipaddr, apikey, CMD_POWER)
    dev.append(eFriendsPowerSensor(api))
    async_add_entities(dev, True)


class eFriendsPowerSensor(SensorEntity):
    """eFriendsPowerSensor."""
    def __init__(self, api):
        """Initialize."""
        self.api = api
        self._name = f"{DOMAIN}_{NAME_POWER}"
        self._state = None
        self.attributes = {}
        self._attr_unique_id = f"{DOMAIN}_{NAME_POWER}"
        self._attr_native_value = float
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_unit_of_measurement = UnitOfPower.WATT

    async def async_update(self):
        """Update data."""
        try:
            data = await self.api.get_json()
            _LOGGER.debug(data)
            if data is None:
                return
        except:
            _LOGGER.debug("Could not get new state")
            return

        if data is None:
            return
        try:
            self._state = data["energyBalance"] * (-1)

            self.attributes = {
                "power1Watt": data["details"]["power1Watt"] * (-1),
                "power2Watt": data["details"]["power2Watt"] * (-1),
                "power3Watt": data["details"]["power3Watt"] * (-1),
                # "current1Ampere": data["details"]["current1Ampere"],
                # "current2Ampere": data["details"]["current2Ampere"],
                # "current3Ampere": data["details"]["current3Ampere"],
                # "voltage1Volt": data["details"]["voltage1Volt"],
                # "voltage2Volt": data["details"]["voltage2Volt"],
                # "voltage3Volt": data["details"]["voltage3Volt"],
            }
        except Exception:
            pass

    @property
    def name(self):
        """Return name."""
        return self._name

    @property
    def state(self):
        """Return state."""
        return self._state

    @property
    def icon(self):
        """Return icon"""
        return "mdi:flash"

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        return self.attributes


class eFriendsAPI:
    """Call API."""

    def __init__(self, session, loop, ipaddr, apikey, cmd):
        """Initialize."""
        self.session = session
        self.loop = loop
        self.ipaddr = ipaddr
        self.apikey = apikey
        self.cmd = cmd

    async def get_json(self):
        """Get json from API endpoint."""
        value = None
        url = LOCAL_BASE_URL.format(self.ipaddr,self.cmd,self.apikey)
        # _LOGGER.debug(url)
        try:
            async with async_timeout.timeout(10):
                response = await self.session.get(url)
                # _LOGGER.debug(response)
                value = await response.json()
        except Exception:
            pass

        return value
    
    def my_stopid(self):
        return self.stopid