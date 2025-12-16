"""
Configuration Storage Layer - 配置持久化实现

提供 KB 能力配置的持久化存储接口：
- 配置存储接口定义
- 数据库持久化实现
- 配置加载逻辑
- 版本历史管理
- 配置导出功能

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 13.1, 13.2
"""

import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.sql import func, text

from server.base import Base


# ═══════════════════════════════════════════════════════════════════════════════
# SQLAlchemy Models
# ═══════════════════════════════════════════════════════════════════════════════


class KBCapabilityConfigModel(Base):
    """KB Capability Configuration database model."""
    __tablename__ = "kb_capability_configs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kb_name = Column(String(200), nullable=False, unique=True, index=True)
    config = Column(JSONB, nullable=False, default={})
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class KBCapabilityConfigHistory(Base):
    """KB Capability Configuration version history model."""
    __tablename__ = "kb_capability_config_history"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kb_name = Column(String(200), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    config = Column(JSONB, nullable=False)
    changed_by = Column(String(200))  # User or system identifier
    change_reason = Column(Text)  # Optional reason for change
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════════════════════════


class CapabilityConfig(BaseModel):
    """Single capability configuration."""
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class StoredKBConfig(BaseModel):
    """Stored KB configuration with metadata."""
    kb_name: str
    capabilities: dict[str, CapabilityConfig] = Field(default_factory=dict)
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConfigVersionEntry(BaseModel):
    """Configuration version history entry."""
    version: int
    config: dict[str, Any]
    changed_by: str | None = None
    change_reason: str | None = None
    created_at: datetime


class ConfigExport(BaseModel):
    """Exported configuration format."""
    kb_name: str
    version: int
    capabilities: dict[str, CapabilityConfig]
    exported_at: str
    schema_version: str = "1.0"


# ═══════════════════════════════════════════════════════════════════════════════
# Storage Interface (Abstract)
# ═══════════════════════════════════════════════════════════════════════════════


class ConfigStorageInterface(ABC):
    """Abstract interface for configuration storage."""

    @abstractmethod
    def load_config(self, kb_name: str) -> StoredKBConfig | None:
        """Load configuration for a KB."""
        pass

    @abstractmethod
    def save_config(
        self,
        kb_name: str,
        capabilities: dict[str, CapabilityConfig],
        changed_by: str | None = None,
        change_reason: str | None = None,
    ) -> StoredKBConfig:
        """Save configuration for a KB with version history."""
        pass

    @abstractmethod
    def get_version_history(
        self, kb_name: str, limit: int = 10
    ) -> list[ConfigVersionEntry]:
        """Get version history for a KB configuration."""
        pass

    @abstractmethod
    def get_config_at_version(
        self, kb_name: str, version: int
    ) -> StoredKBConfig | None:
        """Get configuration at a specific version."""
        pass

    @abstractmethod
    def export_config(self, kb_name: str) -> ConfigExport | None:
        """Export configuration in serializable format."""
        pass

    @abstractmethod
    def import_config(
        self,
        kb_name: str,
        config_export: ConfigExport,
        merge_strategy: str = "replace",
    ) -> StoredKBConfig:
        """Import configuration from export format."""
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# Database Implementation
# ═══════════════════════════════════════════════════════════════════════════════


class DatabaseConfigStorage(ConfigStorageInterface):
    """Database-backed configuration storage implementation."""

    def __init__(self, engine=None):
        """Initialize with optional SQLAlchemy engine."""
        self._engine = engine

    def _get_engine(self):
        """Get or create database engine."""
        if self._engine is None:
            from core.storage.kb_config_db import _engine
            self._engine = _engine()
        return self._engine

    def load_config(self, kb_name: str) -> StoredKBConfig | None:
        """
        Load configuration for a KB from database.
        
        Requirements: 12.2
        """
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                row = conn.execute(
                    text("""
                        SELECT kb_name, config, version, created_at, updated_at
                        FROM kb_capability_configs
                        WHERE kb_name = :kb_name
                    """),
                    {"kb_name": kb_name}
                ).fetchone()

                if row is None:
                    return None

                config_data = row[1] if isinstance(row[1], dict) else {}
                capabilities = {
                    k: CapabilityConfig(**v) if isinstance(v, dict) else CapabilityConfig(enabled=bool(v))
                    for k, v in config_data.get("capabilities", {}).items()
                }

                return StoredKBConfig(
                    kb_name=row[0],
                    capabilities=capabilities,
                    version=row[2],
                    created_at=row[3],
                    updated_at=row[4],
                )
        except Exception:
            return None

    def save_config(
        self,
        kb_name: str,
        capabilities: dict[str, CapabilityConfig],
        changed_by: str | None = None,
        change_reason: str | None = None,
    ) -> StoredKBConfig:
        """
        Save configuration for a KB with version history.
        
        Requirements: 12.1, 12.3
        """
        engine = self._get_engine()
        
        # Serialize capabilities
        config_data = {
            "capabilities": {
                k: v.model_dump() for k, v in capabilities.items()
            }
        }

        with engine.begin() as conn:
            # Get current version
            current = conn.execute(
                text("SELECT version FROM kb_capability_configs WHERE kb_name = :kb_name"),
                {"kb_name": kb_name}
            ).scalar_one_or_none()

            new_version = (current or 0) + 1

            # Save to history before updating (Requirements 12.3)
            if current is not None:
                # Get current config for history
                old_config = conn.execute(
                    text("SELECT config FROM kb_capability_configs WHERE kb_name = :kb_name"),
                    {"kb_name": kb_name}
                ).scalar_one_or_none()

                conn.execute(
                    text("""
                        INSERT INTO kb_capability_config_history 
                        (id, kb_name, version, config, changed_by, change_reason)
                        VALUES (:id, :kb_name, :version, :config, :changed_by, :change_reason)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "kb_name": kb_name,
                        "version": current,
                        "config": json.dumps(old_config) if old_config else "{}",
                        "changed_by": changed_by,
                        "change_reason": change_reason,
                    }
                )

            # Upsert current config
            conn.execute(
                text("""
                    INSERT INTO kb_capability_configs (id, kb_name, config, version)
                    VALUES (:id, :kb_name, :config, :version)
                    ON CONFLICT (kb_name) DO UPDATE SET
                        config = EXCLUDED.config,
                        version = EXCLUDED.version,
                        updated_at = NOW()
                """),
                {
                    "id": str(uuid.uuid4()),
                    "kb_name": kb_name,
                    "config": json.dumps(config_data),
                    "version": new_version,
                }
            )

        return StoredKBConfig(
            kb_name=kb_name,
            capabilities=capabilities,
            version=new_version,
            updated_at=datetime.utcnow(),
        )

    def get_version_history(
        self, kb_name: str, limit: int = 10
    ) -> list[ConfigVersionEntry]:
        """
        Get version history for a KB configuration.
        
        Requirements: 12.3
        """
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT version, config, changed_by, change_reason, created_at
                        FROM kb_capability_config_history
                        WHERE kb_name = :kb_name
                        ORDER BY version DESC
                        LIMIT :limit
                    """),
                    {"kb_name": kb_name, "limit": limit}
                ).fetchall()

                return [
                    ConfigVersionEntry(
                        version=row[0],
                        config=row[1] if isinstance(row[1], dict) else json.loads(row[1] or "{}"),
                        changed_by=row[2],
                        change_reason=row[3],
                        created_at=row[4],
                    )
                    for row in rows
                ]
        except Exception:
            return []

    def get_config_at_version(
        self, kb_name: str, version: int
    ) -> StoredKBConfig | None:
        """
        Get configuration at a specific version.
        
        Requirements: 12.3, 12.4
        """
        try:
            engine = self._get_engine()
            with engine.connect() as conn:
                # First check if it's the current version
                current = conn.execute(
                    text("""
                        SELECT kb_name, config, version, created_at, updated_at
                        FROM kb_capability_configs
                        WHERE kb_name = :kb_name AND version = :version
                    """),
                    {"kb_name": kb_name, "version": version}
                ).fetchone()

                if current:
                    config_data = current[1] if isinstance(current[1], dict) else {}
                    capabilities = {
                        k: CapabilityConfig(**v) if isinstance(v, dict) else CapabilityConfig(enabled=bool(v))
                        for k, v in config_data.get("capabilities", {}).items()
                    }
                    return StoredKBConfig(
                        kb_name=current[0],
                        capabilities=capabilities,
                        version=current[2],
                        created_at=current[3],
                        updated_at=current[4],
                    )

                # Check history
                history = conn.execute(
                    text("""
                        SELECT kb_name, config, version, created_at
                        FROM kb_capability_config_history
                        WHERE kb_name = :kb_name AND version = :version
                    """),
                    {"kb_name": kb_name, "version": version}
                ).fetchone()

                if history:
                    config_data = history[1] if isinstance(history[1], dict) else json.loads(history[1] or "{}")
                    capabilities = {
                        k: CapabilityConfig(**v) if isinstance(v, dict) else CapabilityConfig(enabled=bool(v))
                        for k, v in config_data.get("capabilities", {}).items()
                    }
                    return StoredKBConfig(
                        kb_name=history[0],
                        capabilities=capabilities,
                        version=history[2],
                        created_at=history[3],
                    )

                return None
        except Exception:
            return None

    def export_config(self, kb_name: str) -> ConfigExport | None:
        """
        Export configuration in serializable format.
        
        Requirements: 12.4, 12.5, 13.1
        """
        config = self.load_config(kb_name)
        if config is None:
            return None

        return ConfigExport(
            kb_name=kb_name,
            version=config.version,
            capabilities=config.capabilities,
            exported_at=datetime.utcnow().isoformat() + "Z",
            schema_version="1.0",
        )

    def import_config(
        self,
        kb_name: str,
        config_export: ConfigExport,
        merge_strategy: str = "replace",
    ) -> StoredKBConfig:
        """
        Import configuration from export format.
        
        Requirements: 13.2, 13.3
        
        merge_strategy:
        - "replace": Replace all capabilities with imported ones
        - "merge": Merge imported capabilities with existing (imported takes precedence)
        - "merge_keep": Merge but keep existing values where they exist
        """
        existing = self.load_config(kb_name)
        
        if merge_strategy == "replace" or existing is None:
            capabilities = config_export.capabilities
        elif merge_strategy == "merge":
            capabilities = {**(existing.capabilities or {}), **config_export.capabilities}
        elif merge_strategy == "merge_keep":
            capabilities = {**config_export.capabilities, **(existing.capabilities or {})}
        else:
            capabilities = config_export.capabilities

        return self.save_config(
            kb_name=kb_name,
            capabilities=capabilities,
            changed_by="import",
            change_reason=f"Imported from version {config_export.version}",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# In-Memory Implementation (for testing)
# ═══════════════════════════════════════════════════════════════════════════════


class InMemoryConfigStorage(ConfigStorageInterface):
    """In-memory configuration storage for testing."""

    def __init__(self):
        self._configs: dict[str, StoredKBConfig] = {}
        self._history: dict[str, list[ConfigVersionEntry]] = {}

    def load_config(self, kb_name: str) -> StoredKBConfig | None:
        return self._configs.get(kb_name)

    def save_config(
        self,
        kb_name: str,
        capabilities: dict[str, CapabilityConfig],
        changed_by: str | None = None,
        change_reason: str | None = None,
    ) -> StoredKBConfig:
        # Save to history
        existing = self._configs.get(kb_name)
        if existing:
            if kb_name not in self._history:
                self._history[kb_name] = []
            self._history[kb_name].append(
                ConfigVersionEntry(
                    version=existing.version,
                    config={k: v.model_dump() for k, v in existing.capabilities.items()},
                    changed_by=changed_by,
                    change_reason=change_reason,
                    created_at=existing.updated_at or datetime.utcnow(),
                )
            )

        new_version = (existing.version if existing else 0) + 1
        now = datetime.utcnow()

        config = StoredKBConfig(
            kb_name=kb_name,
            capabilities=capabilities,
            version=new_version,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self._configs[kb_name] = config
        return config

    def get_version_history(
        self, kb_name: str, limit: int = 10
    ) -> list[ConfigVersionEntry]:
        history = self._history.get(kb_name, [])
        return sorted(history, key=lambda x: x.version, reverse=True)[:limit]

    def get_config_at_version(
        self, kb_name: str, version: int
    ) -> StoredKBConfig | None:
        current = self._configs.get(kb_name)
        if current and current.version == version:
            return current

        history = self._history.get(kb_name, [])
        for entry in history:
            if entry.version == version:
                capabilities = {
                    k: CapabilityConfig(**v) if isinstance(v, dict) else CapabilityConfig(enabled=bool(v))
                    for k, v in entry.config.items()
                }
                return StoredKBConfig(
                    kb_name=kb_name,
                    capabilities=capabilities,
                    version=entry.version,
                    created_at=entry.created_at,
                )
        return None

    def export_config(self, kb_name: str) -> ConfigExport | None:
        config = self.load_config(kb_name)
        if config is None:
            return None

        return ConfigExport(
            kb_name=kb_name,
            version=config.version,
            capabilities=config.capabilities,
            exported_at=datetime.utcnow().isoformat() + "Z",
            schema_version="1.0",
        )

    def import_config(
        self,
        kb_name: str,
        config_export: ConfigExport,
        merge_strategy: str = "replace",
    ) -> StoredKBConfig:
        existing = self.load_config(kb_name)

        if merge_strategy == "replace" or existing is None:
            capabilities = config_export.capabilities
        elif merge_strategy == "merge":
            capabilities = {**(existing.capabilities or {}), **config_export.capabilities}
        elif merge_strategy == "merge_keep":
            capabilities = {**config_export.capabilities, **(existing.capabilities or {})}
        else:
            capabilities = config_export.capabilities

        return self.save_config(
            kb_name=kb_name,
            capabilities=capabilities,
            changed_by="import",
            change_reason=f"Imported from version {config_export.version}",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton Storage Instance
# ═══════════════════════════════════════════════════════════════════════════════

_storage_instance: ConfigStorageInterface | None = None


def get_config_storage() -> ConfigStorageInterface:
    """Get the singleton configuration storage instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = DatabaseConfigStorage()
    return _storage_instance


def set_config_storage(storage: ConfigStorageInterface) -> None:
    """Set the configuration storage instance (for testing)."""
    global _storage_instance
    _storage_instance = storage


# ═══════════════════════════════════════════════════════════════════════════════
# Serialization Utilities (Requirements 13.1, 13.2, 13.5)
# ═══════════════════════════════════════════════════════════════════════════════


def serialize_config(config: StoredKBConfig) -> str:
    """
    Serialize configuration to JSON string.
    
    Requirements: 13.1
    """
    export = ConfigExport(
        kb_name=config.kb_name,
        version=config.version,
        capabilities=config.capabilities,
        exported_at=datetime.utcnow().isoformat() + "Z",
        schema_version="1.0",
    )
    return export.model_dump_json(indent=2)


def deserialize_config(json_str: str) -> ConfigExport:
    """
    Deserialize configuration from JSON string.
    
    Requirements: 13.2
    """
    data = json.loads(json_str)
    return ConfigExport(**data)


def pretty_print_config(config: StoredKBConfig) -> str:
    """
    Pretty print configuration with comments.
    
    Requirements: 13.5
    """
    lines = [
        f"# KB Configuration: {config.kb_name}",
        f"# Version: {config.version}",
        f"# Last Updated: {config.updated_at.isoformat() if config.updated_at else 'N/A'}",
        "",
        "{",
        f'  "kb_name": "{config.kb_name}",',
        f'  "version": {config.version},',
        '  "capabilities": {',
    ]

    cap_items = list(config.capabilities.items())
    for i, (cap_id, cap_config) in enumerate(cap_items):
        comma = "," if i < len(cap_items) - 1 else ""
        lines.append(f'    # Capability: {cap_id}')
        lines.append(f'    "{cap_id}": {{')
        lines.append(f'      "enabled": {str(cap_config.enabled).lower()},')
        lines.append(f'      "config": {json.dumps(cap_config.config)}')
        lines.append(f'    }}{comma}')

    lines.extend([
        '  }',
        '}',
    ])

    return "\n".join(lines)
