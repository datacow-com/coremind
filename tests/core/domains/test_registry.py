"""
Unit tests for DomainRegistry

**Validates: Requirements 1.1, 1.2, 2.1**
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from core.domains.registry import DomainRegistry, get_domain_registry, reset_domain_registry
from core.domains.base_interpreter import BaseDomainInterpreter, InterpretationResult
from core.domains.ontology_schema import OntologySchema, EntityType, FieldSpec


class MockInterpreter(BaseDomainInterpreter):
    """Mock interpreter for testing"""
    domain_id = "mock"
    requires_gpu = False
    recommended_vram_mb = 0

    async def interpret(self, document: dict, config: dict | None = None) -> InterpretationResult:
        return InterpretationResult(
            domain_id=self.domain_id,
            structured_data={"test": "data"},
            narrative="Test narrative",
            confidence=0.9,
        )

    def get_ontology(self) -> OntologySchema:
        return OntologySchema(domain_id=self.domain_id)

    def validate_output(self, result: InterpretationResult) -> tuple[bool, list[str]]:
        return True, []


class GPUInterpreter(BaseDomainInterpreter):
    """Mock interpreter that requires GPU"""
    domain_id = "gpu_test"
    requires_gpu = True
    recommended_vram_mb = 8192

    async def interpret(self, document: dict, config: dict | None = None) -> InterpretationResult:
        return InterpretationResult(
            domain_id=self.domain_id,
            structured_data={},
            narrative="",
            confidence=0.5,
        )

    def get_ontology(self) -> OntologySchema:
        return OntologySchema(domain_id=self.domain_id)

    def validate_output(self, result: InterpretationResult) -> tuple[bool, list[str]]:
        return True, []


@pytest.fixture(autouse=True)
def reset_registry_fixture():
    """Reset registry before and after each test"""
    reset_domain_registry()
    yield
    reset_domain_registry()


class TestDomainRegistryBasics:
    """Basic registration and retrieval tests"""

    def test_register_interpreter(self):
        """Test registering an interpreter"""
        registry = DomainRegistry()
        registry.register("test", MockInterpreter)
        
        assert registry.has_domain("test")
        assert "test" in registry.list_domains()

    def test_get_interpreter_returns_instance(self):
        """Test getting an interpreter returns an instance"""
        registry = DomainRegistry()
        registry.register("test", MockInterpreter)
        
        interpreter = registry.get_interpreter("test")
        
        assert interpreter is not None
        assert isinstance(interpreter, MockInterpreter)

    def test_get_interpreter_caches_instance(self):
        """Test that get_interpreter returns the same instance"""
        registry = DomainRegistry()
        registry.register("test", MockInterpreter)
        
        interpreter1 = registry.get_interpreter("test")
        interpreter2 = registry.get_interpreter("test")
        
        assert interpreter1 is interpreter2

    def test_get_interpreter_class(self):
        """Test getting the interpreter class"""
        registry = DomainRegistry()
        registry.register("test", MockInterpreter)
        
        cls = registry.get_interpreter_class("test")
        
        assert cls is MockInterpreter

    def test_list_domains(self):
        """Test listing all registered domains"""
        registry = DomainRegistry()
        registry.register("domain1", MockInterpreter)
        registry.register("domain2", GPUInterpreter)
        
        domains = registry.list_domains()
        
        assert len(domains) == 2
        assert "domain1" in domains
        assert "domain2" in domains

    def test_has_domain(self):
        """Test checking if domain exists"""
        registry = DomainRegistry()
        registry.register("exists", MockInterpreter)
        
        assert registry.has_domain("exists")
        assert not registry.has_domain("not_exists")

    def test_unregister_domain(self):
        """Test unregistering a domain"""
        registry = DomainRegistry()
        registry.register("test", MockInterpreter)
        
        assert registry.has_domain("test")
        
        result = registry.unregister("test")
        
        assert result is True
        assert not registry.has_domain("test")

    def test_unregister_nonexistent_returns_false(self):
        """Test unregistering nonexistent domain returns False"""
        registry = DomainRegistry()
        
        result = registry.unregister("nonexistent")
        
        assert result is False

    def test_clear_removes_all(self):
        """Test clearing all registrations"""
        registry = DomainRegistry()
        registry.register("domain1", MockInterpreter)
        registry.register("domain2", GPUInterpreter)
        
        registry.clear()
        
        assert len(registry.list_domains()) == 0


class TestDomainRegistryWithOntology:
    """Tests for ontology handling"""

    def test_register_with_ontology(self):
        """Test registering with ontology"""
        registry = DomainRegistry()
        ontology = OntologySchema(
            domain_id="test",
            version="1.0",
            entity_types={
                "entity1": EntityType(
                    name="entity1",
                    fields={"field1": FieldSpec(name="field1", type="string")},
                )
            }
        )
        
        registry.register("test", MockInterpreter, ontology=ontology)
        
        retrieved = registry.get_ontology("test")
        
        assert retrieved is not None
        assert retrieved.domain_id == "test"
        assert "entity1" in retrieved.entity_types

    def test_get_ontology_returns_none_if_not_set(self):
        """Test get_ontology returns None if not set"""
        registry = DomainRegistry()
        registry.register("test", MockInterpreter)
        
        ontology = registry.get_ontology("test")
        
        assert ontology is None


class TestDomainDetection:
    """Tests for domain detection"""

    def test_detect_domain_explicit(self):
        """Test detecting domain from explicit field"""
        registry = DomainRegistry()
        registry.register("metaphysics", MockInterpreter)
        
        document = {"domain": "metaphysics", "content": "test"}
        
        detected = registry.detect_domain(document)
        
        assert detected == "metaphysics"

    def test_detect_domain_from_metadata(self):
        """Test detecting domain from metadata"""
        registry = DomainRegistry()
        registry.register("comic", MockInterpreter)
        
        document = {
            "content": "test",
            "metadata": {"domain": "comic"}
        }
        
        detected = registry.detect_domain(document)
        
        assert detected == "comic"

    def test_detect_domain_from_pattern(self):
        """Test detecting domain from content pattern"""
        registry = DomainRegistry()
        registry.register(
            "metaphysics",
            MockInterpreter,
            detection_patterns=["八字", "五行", "命理"]
        )
        
        document = {"content": "这是一份八字分析"}
        
        detected = registry.detect_domain(document)
        
        assert detected == "metaphysics"

    def test_detect_domain_file_pattern(self):
        """Test detecting domain from file type pattern"""
        registry = DomainRegistry()
        registry.register(
            "comic",
            MockInterpreter,
            detection_patterns=["file:.*\\.cbz$", "file:.*\\.cbr$"]
        )
        
        document = {"content": "", "file_type": "test.cbz"}
        
        detected = registry.detect_domain(document)
        
        assert detected == "comic"

    def test_detect_domain_returns_none_for_unknown(self):
        """Test detect_domain returns None for unknown content"""
        registry = DomainRegistry()
        registry.register("test", MockInterpreter)
        
        document = {"content": "random content"}
        
        detected = registry.detect_domain(document)
        
        assert detected is None


class TestDomainInfo:
    """Tests for domain info retrieval"""

    def test_get_domain_info(self):
        """Test getting domain info"""
        registry = DomainRegistry()
        registry.register("gpu_test", GPUInterpreter)
        
        info = registry.get_domain_info("gpu_test")
        
        assert info is not None
        assert info["domain_id"] == "gpu_test"
        assert info["interpreter_class"] == "GPUInterpreter"
        assert info["requires_gpu"] is True
        assert info["recommended_vram_mb"] == 8192

    def test_get_domain_info_nonexistent(self):
        """Test getting info for nonexistent domain"""
        registry = DomainRegistry()
        
        info = registry.get_domain_info("nonexistent")
        
        assert info is None


class TestGlobalRegistry:
    """Tests for global registry functions"""

    def test_get_domain_registry_returns_singleton(self):
        """Test get_domain_registry returns singleton"""
        registry1 = get_domain_registry()
        registry2 = get_domain_registry()
        
        assert registry1 is registry2

    def test_reset_domain_registry(self):
        """Test reset_domain_registry clears and resets"""
        registry = get_domain_registry()
        registry.register("test", MockInterpreter)
        
        reset_domain_registry()
        
        new_registry = get_domain_registry()
        assert len(new_registry.list_domains()) == 0


class TestRegistryValidation:
    """Tests for registration validation"""

    def test_register_empty_domain_id_raises(self):
        """Test registering with empty domain_id raises"""
        registry = DomainRegistry()
        
        with pytest.raises(ValueError, match="domain_id cannot be empty"):
            registry.register("", MockInterpreter)

    def test_register_non_interpreter_raises(self):
        """Test registering non-interpreter class raises"""
        registry = DomainRegistry()
        
        class NotInterpreter:
            pass
        
        with pytest.raises(TypeError, match="must be a subclass"):
            registry.register("test", NotInterpreter)
