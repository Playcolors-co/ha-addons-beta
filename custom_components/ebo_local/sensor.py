"""Sensors for the EBO Local integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .bridge_client import EboBridgeCoordinator
from .const import CONF_NAME, CONF_ROBOT_ID, DOMAIN
from .coordinator import EboLocalCoordinator, EboLocalData


@dataclass(frozen=True, kw_only=True)
class EboLocalSensorDescription(SensorEntityDescription):
    """Description for an EBO Local sensor."""

    value_fn: Callable[[EboLocalData], Any]


SENSORS: tuple[EboLocalSensorDescription, ...] = (
    EboLocalSensorDescription(
        key="recording_days",
        translation_key="recording_days",
        icon="mdi:calendar-multiselect",
        value_fn=lambda data: len(data.days),
    ),
    EboLocalSensorDescription(
        key="recording_videos",
        translation_key="recording_videos",
        icon="mdi:video-box",
        value_fn=lambda data: data.storage.video,
    ),
    EboLocalSensorDescription(
        key="storage_used",
        translation_key="storage_used",
        icon="mdi:micro-sd",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        value_fn=lambda data: data.storage.used,
    ),
    EboLocalSensorDescription(
        key="storage_total",
        translation_key="storage_total",
        icon="mdi:micro-sd",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        value_fn=lambda data: data.storage.total,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EBO Local sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    sd: EboLocalCoordinator = data["sd"]
    entities: list[SensorEntity] = [
        EboLocalSensor(sd, entry, description) for description in SENSORS
    ]
    bridge: EboBridgeCoordinator | None = data.get("bridge_coord")
    if bridge is not None:
        entities.append(EboBatterySensor(bridge, entry))
    async_add_entities(entities)


class EboLocalSensor(CoordinatorEntity[EboLocalCoordinator], SensorEntity):
    """Sensor backed by Stage 0 SD-recording metadata."""

    entity_description: EboLocalSensorDescription

    def __init__(
        self,
        coordinator: EboLocalCoordinator,
        entry: ConfigEntry,
        description: EboLocalSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(entry.data[CONF_ROBOT_ID]))},
            "name": entry.data.get(CONF_NAME, entry.title),
            "manufacturer": "Enabot",
            "model": "EBO Air 2",
        }

    @property
    def native_value(self) -> Any:
        """Return the current sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)


class EboBatterySensor(CoordinatorEntity[EboBridgeCoordinator], SensorEntity):
    """Battery percentage from the local bridge telemetry (MAVLink BATTERY_STATUS)."""

    _attr_has_entity_name = True
    _attr_name = "Battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: EboBridgeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_battery"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(entry.data.get(CONF_ROBOT_ID, entry.entry_id)))},
            "name": entry.data.get(CONF_NAME, entry.title),
            "manufacturer": "Enabot",
            "model": "EBO Air 2",
        }

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        battery = data.get("battery") or {}
        return battery.get("percent")
