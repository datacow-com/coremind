"""
Domain Registry - 领域注册表

Phase 2: 垂直领域增强
管理所有已注册的领域解读器。
"""
from typing import Type
import logging
import re

from core.domains.base_interpreter import BaseDomainInterpreter
from core.domains.ontology_schema import OntologySchema
from core.domains.exceptions import DomainNotFoundError

logger = logging.getLogger(__name__)


class DomainRegistry:
    """领域解读器注册表"""

    def __init__(self):
        self._interpreters: dict[str, Type[BaseDomainInterpreter]] = {}
        self._ontologies: dict[str, OntologySchema] = {}
        self._instances: dict[str, BaseDomainInterpreter] = {}
        self._detection_rules: dict[str, list[str]] = {}  # domain_id -> [patterns]

    def register(
        self,
        domain_id: str,
        interpreter_class: Type[BaseDomainInterpreter],
        ontology: OntologySchema | None = None,
        detection_patterns: list[str] | None = None
    ) -> None:
        """
        注册领域解读器
        
        Args:
            domain_id: 领域 ID
            interpreter_class: 解读器类
            ontology: 本体定义（可选）
            detection_patterns: 领域检测模式（正则表达式列表）
        """
        if not domain_id:
            raise ValueError("domain_id cannot be empty")
        if not issubclass(interpreter_class, BaseDomainInterpreter):
            raise TypeError(
                f"interpreter_class must be a subclass of BaseDomainInterpreter, "
                f"got {interpreter_class}"
            )

        self._interpreters[domain_id] = interpreter_class
        
        if ontology:
            self._ontologies[domain_id] = ontology
        
        if detection_patterns:
            self._detection_rules[domain_id] = detection_patterns

        logger.info(f"Registered domain interpreter: {domain_id}")

    def unregister(self, domain_id: str) -> bool:
        """
        注销领域解读器
        
        Args:
            domain_id: 领域 ID
            
        Returns:
            bool: 是否成功注销
        """
        if domain_id not in self._interpreters:
            return False

        del self._interpreters[domain_id]
        self._ontologies.pop(domain_id, None)
        self._instances.pop(domain_id, None)
        self._detection_rules.pop(domain_id, None)
        
        logger.info(f"Unregistered domain interpreter: {domain_id}")
        return True

    def get_interpreter(self, domain_id: str) -> BaseDomainInterpreter | None:
        """
        获取领域解读器实例
        
        Args:
            domain_id: 领域 ID
            
        Returns:
            BaseDomainInterpreter | None: 解读器实例，未找到返回 None
        """
        if domain_id not in self._interpreters:
            return None

        # 使用缓存的实例
        if domain_id not in self._instances:
            interpreter_class = self._interpreters[domain_id]
            self._instances[domain_id] = interpreter_class()

        return self._instances[domain_id]

    def get_interpreter_class(self, domain_id: str) -> Type[BaseDomainInterpreter] | None:
        """
        获取领域解读器类
        
        Args:
            domain_id: 领域 ID
            
        Returns:
            Type[BaseDomainInterpreter] | None: 解读器类，未找到返回 None
        """
        return self._interpreters.get(domain_id)

    def get_ontology(self, domain_id: str) -> OntologySchema | None:
        """
        获取领域本体定义
        
        Args:
            domain_id: 领域 ID
            
        Returns:
            OntologySchema | None: 本体定义，未找到返回 None
        """
        return self._ontologies.get(domain_id)

    def detect_domain(self, document: dict) -> str | None:
        """
        检测文档所属领域
        
        Args:
            document: 文档数据，包含 content, metadata, file_type 等
            
        Returns:
            str | None: 检测到的领域 ID，未检测到返回 None
        """
        # 1. 检查显式指定的领域
        if "domain" in document:
            domain = document["domain"]
            if domain in self._interpreters:
                return domain

        # 2. 检查 metadata 中的领域标记
        metadata = document.get("metadata", {})
        if "domain" in metadata:
            domain = metadata["domain"]
            if domain in self._interpreters:
                return domain

        # 3. 基于文件类型检测
        file_type = document.get("file_type", "").lower()
        content = document.get("content", "")
        
        # 4. 使用注册的检测规则
        for domain_id, patterns in self._detection_rules.items():
            for pattern in patterns:
                # 检查文件类型
                if pattern.startswith("file:"):
                    file_pattern = pattern[5:]
                    if re.search(file_pattern, file_type, re.IGNORECASE):
                        return domain_id
                # 检查内容
                elif re.search(pattern, content, re.IGNORECASE):
                    return domain_id

        return None

    def list_domains(self) -> list[str]:
        """
        列出所有已注册的领域
        
        Returns:
            list[str]: 领域 ID 列表
        """
        return list(self._interpreters.keys())

    def has_domain(self, domain_id: str) -> bool:
        """
        检查领域是否已注册
        
        Args:
            domain_id: 领域 ID
            
        Returns:
            bool: 是否已注册
        """
        return domain_id in self._interpreters

    def get_domain_info(self, domain_id: str) -> dict | None:
        """
        获取领域信息
        
        Args:
            domain_id: 领域 ID
            
        Returns:
            dict | None: 领域信息
        """
        if domain_id not in self._interpreters:
            return None

        interpreter_class = self._interpreters[domain_id]
        ontology = self._ontologies.get(domain_id)

        return {
            "domain_id": domain_id,
            "interpreter_class": interpreter_class.__name__,
            "requires_gpu": interpreter_class.requires_gpu,
            "recommended_vram_mb": interpreter_class.recommended_vram_mb,
            "has_ontology": ontology is not None,
            "ontology_version": ontology.version if ontology else None,
            "detection_patterns": self._detection_rules.get(domain_id, []),
        }

    def clear(self) -> None:
        """清空所有注册"""
        self._interpreters.clear()
        self._ontologies.clear()
        self._instances.clear()
        self._detection_rules.clear()
        logger.info("Cleared all domain registrations")


# 全局注册表实例
_registry: DomainRegistry | None = None


def get_domain_registry() -> DomainRegistry:
    """获取全局 DomainRegistry 实例"""
    global _registry
    if _registry is None:
        _registry = DomainRegistry()
    return _registry


def reset_domain_registry() -> None:
    """重置全局 DomainRegistry（主要用于测试）"""
    global _registry
    if _registry:
        _registry.clear()
    _registry = None
