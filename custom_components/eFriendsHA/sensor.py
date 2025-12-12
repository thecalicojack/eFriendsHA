"""
A integration read data from the eFriends Cube
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
import aiohttp
import asyncio

import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.const import UnitOfPower, UnitOfEnergy
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.event import (
    async_track_state_change_event,  # ← listen to another entity's state changes
    async_track_time_interval,  # ← periodic tick (optional UI refresh)
)
from homeassistant.core import Event, EventStateChangedData

from custom_components.eFriendsHA.const import (
    DOMAIN,
    LOCAL_BASE_URL,
    NAME_POWER,
    NAME_P_FROMGRID,
    NAME_P_TOGRID,
    NAME_E_FROMGRID,
    NAME_E_TOGRID,
    CMD_POWER,
)

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

    api = eFriendsAPI(
        async_create_clientsession(hass), hass.loop, ipaddr, apikey, CMD_POWER
    )
    dev.append(eFriendsPowerSensor(api))
    dev.append(eFriendsPowerFromGridSensor(hass, f"sensor.{DOMAIN}_{NAME_POWER}"))
    dev.append(eFriendsPowerToGridSensor(hass, f"sensor.{DOMAIN}_{NAME_POWER}"))
    dev.append(eFriendsEnergyFromGridSensor(hass, f"sensor.{DOMAIN}_{NAME_P_FROMGRID}"))
    dev.append(eFriendsEnergyToGridSensor(hass, f"sensor.{DOMAIN}_{NAME_P_TOGRID}"))
    async_add_entities(dev, True)


class eFriendsPowerSensor(SensorEntity):
    """eFriendsPowerSensor."""

    def __init__(self, api):
        """Initialize."""
        self._attr_unique_id = f"{DOMAIN}_{NAME_POWER}"
        self.api = api
        self._attr_name = f"{DOMAIN}_{NAME_POWER}"
        self._attr_icon = "mdi:flash"
        self._attr_native_value: Optional[float] = None
        self.attributes = {}
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT

    async def async_update(self):
        """Update value."""
        data = await self.api.get_power()

        if isinstance(data["energyBalance"], (int, float)):
            self._attr_native_value = float(data["energyBalance"]) * -1.0
        else:
            self._attr_native_value = None

        self.attributes = {
            "power1Watt": data["power1Watt"] * (-1),
            "power2Watt": data["power2Watt"] * (-1),
            "power3Watt": data["power3Watt"] * (-1),
        }

    @property
    def extra_state_attributes(self):
        """Return attributes."""
        return self.attributes


class eFriendsPowerFromGridSensor(SensorEntity):
    """eFriendsPowerFromGridSensor."""

    def __init__(self, hass, source_entity_id):
        """Initialize."""
        self.hass = hass
        self._source_entity_id = source_entity_id
        self._attr_name = f"{DOMAIN}_{NAME_P_FROMGRID}"
        self._attr_icon = "mdi:flash"
        self._attr_native_value: Optional[float] = None
        self._attr_unique_id = f"{DOMAIN}_{NAME_P_FROMGRID}"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT

    async def async_added_to_hass(self):
        """Called when the entity is added to HA."""
        async_track_state_change_event(
            self.hass,
            self._source_entity_id,
            self._state_changed,
        )

    async def _state_changed(self, event: Event[EventStateChangedData]):
        """Update value."""
        # entity_id = event.data.get("entity_id")
        # old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        _LOGGER.debug(
            "eFriendsPowerFromGridSensor _state_changed called with: %s", new_state
        )
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return

        try:
            power_w = float(new_state.state)  # power in watts
        except ValueError:
            _LOGGER.warning("Invalid power value %s", new_state.state)
            return

        if power_w > 0:
            self._attr_native_value = power_w
        else:
            self._attr_native_value = 0

        self.schedule_update_ha_state()


class eFriendsEnergyFromGridSensor(SensorEntity, RestoreEntity):
    """eFriendsEnergyFromGridSensor."""

    def __init__(self, hass, source_entity_id):
        """Initialize."""
        self.hass = hass
        self._source_entity_id = source_entity_id
        self._attr_name = f"{DOMAIN}_{NAME_E_FROMGRID}"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_unique_id = f"{DOMAIN}_{NAME_E_FROMGRID}"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._last_power = None  # last power reading (W)
        self._last_timestamp = None  # when that reading arrived
        self._energy_kwh = 0.0  # accumulated energy (will be restored)

    async def async_added_to_hass(self):
        """Called when the entity is added to HA."""
        # 1️⃣ Restore previous state (if any)
        restored = await self.async_get_last_state()
        if restored is not None and restored.state not in ("unknown", "unavailable"):
            try:
                self._energy_kwh = float(restored.state)
                _LOGGER.debug(
                    "Restored previous energy total: %.3f kWh", self._energy_kwh
                )
            except ValueError:
                _LOGGER.warning("Could not parse restored state %s", restored.state)

        # 2️⃣ Listen for power‑sensor updates
        async_track_state_change_event(
            self.hass,
            self._source_entity_id,
            self._state_changed,
        )
        # 3️⃣ Periodic tick to keep the UI fresh
        async_track_time_interval(self.hass, self._tick, SCAN_INTERVAL)

    async def _state_changed(self, event: Event[EventStateChangedData]):
        """Update value."""
        # entity_id = event.data.get("entity_id")
        # old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        _LOGGER.debug("_state_changed called with: %s", new_state)
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return

        try:
            power_w = float(new_state.state)  # power in watts
        except ValueError:
            _LOGGER.warning("Invalid power value %s", new_state.state)
            return

        now = datetime.now(timezone.utc)
        if self._last_power is not None and self._last_timestamp is not None:
            # Δt in hours
            dt_hours = (now - self._last_timestamp).total_seconds() / 3600.0
            # Energy = Power × Time
            self._energy_kwh += (self._last_power * dt_hours) / 1000.0
            _LOGGER.debug("Current Energy: %s", self._energy_kwh)

        # Store for next iteration
        self._last_power = power_w
        self._last_timestamp = now

        # Tell HA the state changed (this also writes the new state to the DB)
        self.schedule_update_ha_state()

    async def _tick(self, now):
        """Periodic write – useful for UI refresh."""
        self.schedule_update_ha_state()

    @property
    def native_value(self) -> float:
        """Return latest measurement."""
        return round(self._energy_kwh, 3)


class eFriendsPowerToGridSensor(SensorEntity):
    """eFriendsPowerToGridSensor."""

    def __init__(self, hass, source_entity_id):
        """Initialize."""
        self.hass = hass
        self._source_entity_id = source_entity_id
        self._attr_name = f"{DOMAIN}_{NAME_P_TOGRID}"
        self._attr_icon = "mdi:flash"
        self._attr_native_value: Optional[float] = None
        self.attributes = {}
        self._attr_unique_id = f"{DOMAIN}_{NAME_P_TOGRID}"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT

    async def async_added_to_hass(self):
        """Called when the entity is added to HA."""
        async_track_state_change_event(
            self.hass,
            self._source_entity_id,
            self._state_changed,
        )

    async def _state_changed(self, event: Event[EventStateChangedData]):
        """Update value."""
        # entity_id = event.data.get("entity_id")
        # old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return

        try:
            power_w = float(new_state.state)  # power in watts
        except ValueError:
            _LOGGER.warning("Invalid power value %s", new_state.state)
            return

        if power_w < 0:
            self._attr_native_value = power_w * (-1)
        else:
            self._attr_native_value = 0

        self.schedule_update_ha_state()


class eFriendsEnergyToGridSensor(SensorEntity, RestoreEntity):
    """eFriendsEnergyToGridSensor."""

    def __init__(self, hass, source_entity_id):
        """Initialize."""
        self.hass = hass
        self._source_entity_id = source_entity_id
        self._attr_name = f"{DOMAIN}_{NAME_E_TOGRID}"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_unique_id = f"{DOMAIN}_{NAME_E_TOGRID}"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._last_power = None  # last power reading (W)
        self._last_timestamp = None  # when that reading arrived
        self._energy_kwh = 0.0  # accumulated energy (will be restored)

    async def async_added_to_hass(self):
        """Called when the entity is added to HA."""
        # 1️⃣ Restore previous state (if any)
        restored = await self.async_get_last_state()
        if restored is not None and restored.state not in ("unknown", "unavailable"):
            try:
                self._energy_kwh = float(restored.state)
                _LOGGER.debug(
                    "Restored previous energy total: %.3f kWh", self._energy_kwh
                )
            except ValueError:
                _LOGGER.warning("Could not parse restored state %s", restored.state)

        # 2️⃣ Listen for power‑sensor updates
        async_track_state_change_event(
            self.hass,
            self._source_entity_id,
            self._state_changed,
        )
        # 3️⃣ Periodic tick to keep the UI fresh
        async_track_time_interval(self.hass, self._tick, SCAN_INTERVAL)

    async def _state_changed(self, event: Event[EventStateChangedData]):
        """Update value."""
        # entity_id = event.data.get("entity_id")
        # old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        _LOGGER.debug("_state_changed called with: %s", new_state)
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return

        try:
            power_w = float(new_state.state)  # power in watts
        except ValueError:
            _LOGGER.warning("Invalid power value %s", new_state.state)
            return

        now = datetime.now(timezone.utc)
        if self._last_power is not None and self._last_timestamp is not None:
            # Δt in hours
            dt_hours = (now - self._last_timestamp).total_seconds() / 3600.0
            # Energy = Power × Time
            self._energy_kwh += (self._last_power * dt_hours) / 1000.0
            _LOGGER.debug("Current Energy: %s", self._energy_kwh)

        # Store for next iteration
        self._last_power = power_w
        self._last_timestamp = now

        # Tell HA the state changed (this also writes the new state to the DB)
        self.schedule_update_ha_state()

    async def _tick(self, now):
        """Periodic write – useful for UI refresh."""
        self.schedule_update_ha_state()

    @property
    def native_value(self) -> float:
        """Return latest measurement."""
        return round(self._energy_kwh, 3)


class eFriendsAPI:
    """Call API."""

    def __init__(self, session, loop, ipaddr, apikey, cmd):
        """Initialize."""
        self.session = session
        self.loop = loop
        self.ipaddr = ipaddr
        self.apikey = apikey
        self.cmd = cmd

    async def get_power(self) -> dict:
        """Get json from API endpoint."""
        result: dict[str, float | None] = {
            "energyBalance": None,
            "power1Watt": None,
            "power2Watt": None,
            "power3Watt": None,
        }
        url = LOCAL_BASE_URL.format(self.ipaddr, self.cmd, self.apikey)
        _LOGGER.debug("Requesting URL: %s", url)

        try:
            # Give the request a hard timeout of 10 seconds.
            async with async_timeout.timeout(10):
                async with self.session.get(url) as response:
                    # Raise for non‑2xx status codes – they indicate a real failure.
                    response.raise_for_status()
                    payload = await response.json()
                    _LOGGER.debug("Raw JSON payload: %s", payload)

        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            # Covers connection problems, time‑outs, DNS failures, etc.
            _LOGGER.warning("Unable to reach %s: %s", url, exc)
            return result
        except Exception as exc:  # Catch unexpected JSON decode errors, etc.
            _LOGGER.error("Unexpected error while fetching %s: %s", url, exc)
            return result

        mapping = {
            "energyBalance": ("energyBalance",),
            "power1Watt": ("details", "power1Watt"),
            "power2Watt": ("details", "power2Watt"),
            "power3Watt": ("details", "power3Watt"),
        }

        for out_key, path in mapping.items():
            # Walk the path safely – break if any intermediate level is missing
            node = payload
            for subkey in path:
                if isinstance(node, dict) and subkey in node:
                    node = node[subkey]
                else:
                    node = None
                    break

            # Try to coerce the final value to float; keep None on failure
            try:
                result[out_key] = float(node) if node is not None else None
            except (TypeError, ValueError):
                _LOGGER.debug("%s exists but is not numeric", ".".join(path))

        _LOGGER.debug(
            "Parsed power values – %s",
            ", ".join(f"{k}={v}" for k, v in result.items()),
        )
        return result

    # def my_stopid(self):
    #     return self.stopid
