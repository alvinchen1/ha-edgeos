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
        self._starting_version: str | None = None
        self._firmware_url: str | None = None
        self._reboot_required = False

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
        self._pending_version = version or self._attr_latest_version
        self._starting_version = self._attr_installed_version
        self.async_write_ha_state()

        firmware_staged = False
        try:
            await self.coordinator.async_install_firmware(self._firmware_url)
            firmware_staged = True
            self._set_reboot_required(True)
            self.async_write_ha_state()
            _LOGGER.info("Firmware staged successfully; rebooting EdgeOS device")
            await self.coordinator.async_reboot()
        except Exception:
            self._install_pending = False
            if not firmware_staged:
                self._pending_version = None
                self._starting_version = None
                self._set_reboot_required(False)
            _LOGGER.exception("EdgeOS firmware upgrade or automatic reboot failed")
            self.async_write_ha_state()
            raise

    def _set_reboot_required(self, required: bool) -> None:
        self._reboot_required = required
        self._attr_extra_state_attributes = {
            "firmware_download_url": self._firmware_url,
            "reboot_required": required,
        }

    def update_component(self, data):
        data = data or {}
        attributes = data.get(ATTR_ATTRIBUTES, {})
        self._attr_installed_version = attributes.get("installed_version")
        update_available = data.get("is_on", False)
        self._attr_latest_version = (
            attributes.get("latest_version")
            if update_available
            else self._attr_installed_version
        )
        self._attr_release_url = attributes.get("release_url")
        self._firmware_url = (
            attributes.get("firmware_url") if update_available else None
        )

        version_confirmed = (
            self._attr_installed_version == self._pending_version
            if self._pending_version
            else bool(self._starting_version)
            and self._attr_installed_version != self._starting_version
        )
        if (
            self._reboot_required
            and self._attr_installed_version
            and version_confirmed
        ):
            self._install_pending = False
            self._pending_version = None
            self._starting_version = None
            self._set_reboot_required(False)
        else:
            self._set_reboot_required(self._reboot_required)
