"""
Ontology Schema - 本体定义系统

Phase 2: 垂直领域增强
支持从 YAML、字典、数据库加载本体定义，验证结构化数据。
支持通过 UI 管理配置业务能力。
"""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal
import re
import logging

import yaml

from core.domains.exceptions import OntologyValidationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class FieldSpec:
    """字段规格定义"""
    name: str
    type: Literal["string", "integer", "float", "boolean", "array", "object"]
    required: bool = False
    pattern: str | None = None  # 正则表达式模式
    enum: list[str] | None = None  # 枚举值
    minimum: float | None = None
    maximum: float | None = None
    items_type: str | None = None  # array 元素类型
    description: str = ""


@dataclass
class EntityType:
    """实体类型定义"""
    name: str
    description: str = ""
    fields: dict[str, FieldSpec] = field(default_factory=dict)
    required_fields: list[str] = field(default_factory=list)


@dataclass
class Relationship:
    """关系定义"""
    name: str
    source_type: str
    target_type: str
    cardinality: Literal["one", "many"] = "one"
    description: str = ""


@dataclass
class ValidationRule:
    """验证规则"""
    rule: str  # 规则表达式
    message: str  # 错误消息


class OntologySchema:
    """本体定义"""

    def __init__(
        self,
        domain_id: str,
        version: str = "1.0",
        entity_types: dict[str, EntityType] | None = None,
        relationships: list[Relationship] | None = None,
        validation_rules: list[ValidationRule] | None = None,
    ):
        self.domain_id = domain_id
        self.version = version
        self.entity_types = entity_types or {}
        self.relationships = relationships or []
        self.validation_rules = validation_rules or []

    @classmethod
    def from_yaml(cls, path: str) -> "OntologySchema":
        """从 YAML 文件加载本体定义"""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        domain_id = data.get("domain_id", "unknown")
        version = data.get("version", "1.0")

        # 解析实体类型
        entity_types: dict[str, EntityType] = {}
        for name, spec in data.get("entity_types", {}).items():
            fields: dict[str, FieldSpec] = {}
            for field_name, field_spec in spec.get("fields", {}).items():
                fields[field_name] = FieldSpec(
                    name=field_name,
                    type=field_spec.get("type", "string"),
                    required=field_name in spec.get("required", []),
                    pattern=field_spec.get("pattern"),
                    enum=field_spec.get("enum"),
                    minimum=field_spec.get("minimum"),
                    maximum=field_spec.get("maximum"),
                    items_type=field_spec.get("items_type"),
                    description=field_spec.get("description", ""),
                )
            entity_types[name] = EntityType(
                name=name,
                description=spec.get("description", ""),
                fields=fields,
                required_fields=spec.get("required", []),
            )

        # 解析关系
        relationships: list[Relationship] = []
        for rel_spec in data.get("relationships", []):
            relationships.append(Relationship(
                name=rel_spec.get("name", ""),
                source_type=rel_spec.get("source_type", ""),
                target_type=rel_spec.get("target_type", ""),
                cardinality=rel_spec.get("cardinality", "one"),
                description=rel_spec.get("description", ""),
            ))

        # 解析验证规则
        validation_rules: list[ValidationRule] = []
        for rule_spec in data.get("validation_rules", []):
            validation_rules.append(ValidationRule(
                rule=rule_spec.get("rule", ""),
                message=rule_spec.get("message", "Validation failed"),
            ))

        return cls(
            domain_id=domain_id,
            version=version,
            entity_types=entity_types,
            relationships=relationships,
            validation_rules=validation_rules,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "OntologySchema":
        """从字典创建本体定义"""
        domain_id = data.get("domain_id", "unknown")
        version = data.get("version", "1.0")

        # 解析实体类型
        entity_types: dict[str, EntityType] = {}
        for name, spec in data.get("entity_types", {}).items():
            fields: dict[str, FieldSpec] = {}
            for field_name, field_spec in spec.get("fields", {}).items():
                fields[field_name] = FieldSpec(
                    name=field_name,
                    type=field_spec.get("type", "string"),
                    required=field_name in spec.get("required", []),
                    pattern=field_spec.get("pattern"),
                    enum=field_spec.get("enum"),
                    minimum=field_spec.get("minimum"),
                    maximum=field_spec.get("maximum"),
                    items_type=field_spec.get("items_type"),
                    description=field_spec.get("description", ""),
                )
            entity_types[name] = EntityType(
                name=name,
                description=spec.get("description", ""),
                fields=fields,
                required_fields=spec.get("required", []),
            )

        # 解析关系
        relationships: list[Relationship] = []
        for rel_spec in data.get("relationships", []):
            relationships.append(Relationship(
                name=rel_spec.get("name", ""),
                source_type=rel_spec.get("source_type", ""),
                target_type=rel_spec.get("target_type", ""),
                cardinality=rel_spec.get("cardinality", "one"),
                description=rel_spec.get("description", ""),
            ))

        # 解析验证规则
        validation_rules: list[ValidationRule] = []
        for rule_spec in data.get("validation_rules", []):
            validation_rules.append(ValidationRule(
                rule=rule_spec.get("rule", ""),
                message=rule_spec.get("message", "Validation failed"),
            ))

        return cls(
            domain_id=domain_id,
            version=version,
            entity_types=entity_types,
            relationships=relationships,
            validation_rules=validation_rules,
        )

    def validate(self, data: dict) -> tuple[bool, list[str]]:
        """
        验证结构化数据是否符合本体定义
        
        Args:
            data: 待验证的结构化数据
            
        Returns:
            tuple[bool, list[str]]: (是否有效, 违规列表)
        """
        violations: list[str] = []

        # 验证每个实体类型
        for entity_name, entity_data in data.items():
            if entity_name not in self.entity_types:
                # 允许额外字段，不报错
                continue

            entity_type = self.entity_types[entity_name]
            
            # 处理单个实体或实体列表
            entities = entity_data if isinstance(entity_data, list) else [entity_data]
            
            for idx, entity in enumerate(entities):
                if not isinstance(entity, dict):
                    violations.append(
                        f"{entity_name}[{idx}]: expected dict, got {type(entity).__name__}"
                    )
                    continue
                    
                # 检查必填字段
                for req_field in entity_type.required_fields:
                    if req_field not in entity or entity[req_field] is None:
                        violations.append(
                            f"{entity_name}[{idx}]: missing required field '{req_field}'"
                        )

                # 验证字段值
                for field_name, field_value in entity.items():
                    if field_name not in entity_type.fields:
                        continue
                        
                    field_spec = entity_type.fields[field_name]
                    field_violations = self._validate_field(
                        f"{entity_name}[{idx}].{field_name}",
                        field_value,
                        field_spec
                    )
                    violations.extend(field_violations)

        return len(violations) == 0, violations

    def _validate_field(
        self,
        path: str,
        value: Any,
        spec: FieldSpec
    ) -> list[str]:
        """验证单个字段"""
        violations: list[str] = []

        if value is None:
            if spec.required:
                violations.append(f"{path}: required field is None")
            return violations

        # 类型验证
        type_valid = self._check_type(value, spec.type)
        if not type_valid:
            violations.append(
                f"{path}: expected type '{spec.type}', got '{type(value).__name__}'"
            )
            return violations  # 类型错误时跳过其他验证

        # 枚举验证
        if spec.enum is not None and value not in spec.enum:
            violations.append(
                f"{path}: value '{value}' not in allowed enum {spec.enum}"
            )

        # 正则模式验证
        if spec.pattern is not None and isinstance(value, str):
            if not re.match(spec.pattern, value):
                violations.append(
                    f"{path}: value '{value}' does not match pattern '{spec.pattern}'"
                )

        # 数值范围验证
        if spec.minimum is not None and isinstance(value, (int, float)):
            if value < spec.minimum:
                violations.append(
                    f"{path}: value {value} is less than minimum {spec.minimum}"
                )
        if spec.maximum is not None and isinstance(value, (int, float)):
            if value > spec.maximum:
                violations.append(
                    f"{path}: value {value} is greater than maximum {spec.maximum}"
                )

        return violations

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查值类型"""
        type_map = {
            "string": str,
            "integer": int,
            "float": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        expected = type_map.get(expected_type)
        if expected is None:
            return True  # 未知类型，跳过验证
        return isinstance(value, expected)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "domain_id": self.domain_id,
            "version": self.version,
            "entity_types": {
                name: {
                    "description": et.description,
                    "fields": {
                        fn: {
                            "type": fs.type,
                            "required": fs.required,
                            "pattern": fs.pattern,
                            "enum": fs.enum,
                            "minimum": fs.minimum,
                            "maximum": fs.maximum,
                            "description": fs.description,
                        }
                        for fn, fs in et.fields.items()
                    },
                    "required": et.required_fields,
                }
                for name, et in self.entity_types.items()
            },
            "relationships": [
                {
                    "name": r.name,
                    "source_type": r.source_type,
                    "target_type": r.target_type,
                    "cardinality": r.cardinality,
                }
                for r in self.relationships
            ],
            "validation_rules": [
                {"rule": vr.rule, "message": vr.message}
                for vr in self.validation_rules
            ],
        }

    # =========================================================================
    # 数据库集成方法 - 支持从 DB 加载和保存，用于 UI 管理
    # =========================================================================

    @classmethod
    async def from_db(
        cls,
        domain_id: str,
        session: "AsyncSession",
    ) -> "OntologySchema | None":
        """
        从数据库加载本体定义
        
        Args:
            domain_id: 领域 ID
            session: 数据库会话
            
        Returns:
            OntologySchema 实例，如果不存在则返回 None
        """
        from sqlalchemy import select
        from server.models import DomainConfig
        
        stmt = select(DomainConfig).where(DomainConfig.id == domain_id)
        result = await session.execute(stmt)
        config = result.scalar_one_or_none()
        
        if config is None:
            logger.warning(f"Domain config not found in DB: {domain_id}")
            return None
        
        if not config.ontology:
            logger.warning(f"Domain {domain_id} has no ontology defined")
            return None
        
        # 从 JSON 字段构建 OntologySchema
        ontology_data = config.ontology
        ontology_data["domain_id"] = domain_id
        
        return cls.from_dict(ontology_data)

    async def save_to_db(
        self,
        session: "AsyncSession",
        name: str | None = None,
        name_en: str | None = None,
        visual_schema: dict | None = None,
        narrative_schema: dict | None = None,
        interpretation_rules: dict | None = None,
        gpu_requirements: dict | None = None,
        enabled: bool = True,
    ) -> None:
        """
        保存本体定义到数据库
        
        Args:
            session: 数据库会话
            name: 领域显示名称（中文）
            name_en: 领域显示名称（英文）
            visual_schema: 视觉模式定义
            narrative_schema: 叙事模式定义
            interpretation_rules: 解读规则
            gpu_requirements: GPU 需求配置
            enabled: 是否启用
        """
        from sqlalchemy import select
        from server.models import DomainConfig
        
        # 检查是否已存在
        stmt = select(DomainConfig).where(DomainConfig.id == self.domain_id)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        ontology_dict = self.to_dict()
        # 移除 domain_id，因为它是主键
        ontology_dict.pop("domain_id", None)
        
        if existing:
            # 更新现有记录
            existing.ontology = ontology_dict
            if name is not None:
                existing.name = name
            if name_en is not None:
                existing.name_en = name_en
            if visual_schema is not None:
                existing.visual_schema = visual_schema
            if narrative_schema is not None:
                existing.narrative_schema = narrative_schema
            if interpretation_rules is not None:
                existing.interpretation_rules = interpretation_rules
            if gpu_requirements is not None:
                existing.gpu_requirements = gpu_requirements
            existing.enabled = enabled
            logger.info(f"Updated domain config in DB: {self.domain_id}")
        else:
            # 创建新记录
            new_config = DomainConfig(
                id=self.domain_id,
                name=name or self.domain_id,
                name_en=name_en,
                ontology=ontology_dict,
                visual_schema=visual_schema,
                narrative_schema=narrative_schema,
                interpretation_rules=interpretation_rules,
                gpu_requirements=gpu_requirements,
                enabled=enabled,
            )
            session.add(new_config)
            logger.info(f"Created domain config in DB: {self.domain_id}")
        
        await session.commit()

    @classmethod
    async def list_from_db(
        cls,
        session: "AsyncSession",
        enabled_only: bool = True,
    ) -> list["OntologySchema"]:
        """
        从数据库列出所有本体定义
        
        Args:
            session: 数据库会话
            enabled_only: 是否只返回启用的领域
            
        Returns:
            OntologySchema 实例列表
        """
        from sqlalchemy import select
        from server.models import DomainConfig
        
        stmt = select(DomainConfig)
        if enabled_only:
            stmt = stmt.where(DomainConfig.enabled == True)  # noqa: E712
        
        result = await session.execute(stmt)
        configs = result.scalars().all()
        
        schemas = []
        for config in configs:
            if config.ontology:
                ontology_data = config.ontology.copy()
                ontology_data["domain_id"] = config.id
                try:
                    schema = cls.from_dict(ontology_data)
                    schemas.append(schema)
                except Exception as e:
                    logger.error(f"Failed to parse ontology for {config.id}: {e}")
        
        return schemas

    @classmethod
    async def delete_from_db(
        cls,
        domain_id: str,
        session: "AsyncSession",
    ) -> bool:
        """
        从数据库删除本体定义
        
        Args:
            domain_id: 领域 ID
            session: 数据库会话
            
        Returns:
            是否成功删除
        """
        from sqlalchemy import delete
        from server.models import DomainConfig
        
        stmt = delete(DomainConfig).where(DomainConfig.id == domain_id)
        result = await session.execute(stmt)
        await session.commit()
        
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Deleted domain config from DB: {domain_id}")
        else:
            logger.warning(f"Domain config not found for deletion: {domain_id}")
        
        return deleted


# =============================================================================
# 辅助函数 - 用于 API 路由
# =============================================================================


async def get_domain_config_for_ui(
    domain_id: str,
    session: "AsyncSession",
) -> dict | None:
    """
    获取领域配置用于 UI 展示
    
    Args:
        domain_id: 领域 ID
        session: 数据库会话
        
    Returns:
        包含完整配置的字典，用于 UI 展示
    """
    from sqlalchemy import select
    from server.models import DomainConfig
    
    stmt = select(DomainConfig).where(DomainConfig.id == domain_id)
    result = await session.execute(stmt)
    config = result.scalar_one_or_none()
    
    if config is None:
        return None
    
    return {
        "id": config.id,
        "name": config.name,
        "name_en": config.name_en,
        "ontology": config.ontology,
        "visual_schema": config.visual_schema,
        "narrative_schema": config.narrative_schema,
        "interpretation_rules": config.interpretation_rules,
        "gpu_requirements": config.gpu_requirements,
        "enabled": config.enabled,
        "created_at": config.created_at.isoformat() if config.created_at else None,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


async def list_domain_configs_for_ui(
    session: "AsyncSession",
    enabled_only: bool = False,
) -> list[dict]:
    """
    列出所有领域配置用于 UI 展示
    
    Args:
        session: 数据库会话
        enabled_only: 是否只返回启用的领域
        
    Returns:
        领域配置列表
    """
    from sqlalchemy import select
    from server.models import DomainConfig
    
    stmt = select(DomainConfig)
    if enabled_only:
        stmt = stmt.where(DomainConfig.enabled == True)  # noqa: E712
    stmt = stmt.order_by(DomainConfig.name)
    
    result = await session.execute(stmt)
    configs = result.scalars().all()
    
    return [
        {
            "id": config.id,
            "name": config.name,
            "name_en": config.name_en,
            "enabled": config.enabled,
            "has_ontology": config.ontology is not None,
            "has_visual_schema": config.visual_schema is not None,
            "gpu_requirements": config.gpu_requirements,
            "created_at": config.created_at.isoformat() if config.created_at else None,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        }
        for config in configs
    ]
