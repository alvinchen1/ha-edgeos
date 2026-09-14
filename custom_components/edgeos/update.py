from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .common.base_entity import IntegrationBaseEntity, async_setup_base_entry
from .common.consts import ATTR_ATTRIBUTES
from .common.entity_descriptions import IntegrationUpdateEntityDescription
from .common.enums import DeviceTypes
from .managers.coordinator import Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    await async_setup_base_entry(
        hass,
        entry,
        Platform.UPDATE,
        IntegrationUpdateEntity,
        async_add_entities,
    )


class IntegrationUpdateEntity(IntegrationBaseEntity, UpdateEntity):
    """Representation of the EdgeOS firmware update."""

    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(
        self,
        hass: HomeAssistant,
        entity_description: IntegrationUpdateEntityDescription,
        coordinator: Coordinator,
        device_type: DeviceTypes,
        item_id: str | None,
    ):
        super().__init__(hass, entity_description, coordinator, device_type, item_id)
        self._install_pending = False
        self._pending_version: str | None = None
        self._firmware_url: str | None = None

    @property
    def in_progress(self) -> bool:
        return self._install_pending

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        del backup
        del kwargs
        if not self._firmware_url:
            raise ValueError("EdgeOS did not provide a firmware download URL")

        self._install_pending = True
        self._pending_version = version
        self.async_write_ha_state()

        try:
            await self.coordinator.async_install_firmware(self._firmware_url)
        except Exception:
            _LOGGER.exception("EdgeOS firmware upgrade request failed")
            self.async_write_ha_state()
            raise

    def update_component(self, data):
        data = data or {}
        attributes = data.get(ATTR_ATTRIBUTES, {})
        self._attr_installed_version = attributes.get("installed_version")
        self._attr_latest_version = attributes.get("latest_version")
        self._attr_release_url = attributes.get("release_url")
        self._firmware_url = attributes.get("firmware_url")

        if (
            self._install_pending
            and self._pending_version
            and self._attr_installed_version == self._pending_version
        ):
            self._install_pending = False
            self._pending_version = None
