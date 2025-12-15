"""
Property-based tests for DomainRegistry

**Feature: vertical-domain-phase2, Property 1: Domain Registration Round Trip**
**Validates: Requirements 1.1, 1.2**

For any domain interpreter class and ontology configuration, registering it with
the DomainRegistry and then retrieving it should return an equivalent interpreter instance.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Any

from core.domains.registry import DomainRegistry, reset_domain_registry
from core.domains.base_interpreter import BaseDomainInterpreter, InterpretationResult
from core.domains.ontology_schema import OntologySchema, EntityType, FieldSpec


# Test interpreter for property tests
class MockDomainInterpreter(BaseDomainInterpreter):
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


class GPUMockInterpreter(BaseDomainInterpreter):
    """Mock interpreter that requires GPU"""
    domain_id = "gpu_mock"
    requires_gpu = True
    recommended_vram_mb = 4096

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


# Strategies for property tests
domain_ids = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_-")
).filter(lambda x: x and not x.startswith("-") and not x.startswith("_"))

detection_patterns = st.lists(
    st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz.*[]"),
    min_size=0,
    max_size=5
)


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset registry before each test"""
    reset_domain_registry()
    yield
    reset_domain_registry()


class TestDomainRegistrationRoundTrip:
    """
    **Feature: vertical-domain-phase2, Property 1: Domain Registration Round Trip**
    **Validates: Requirements 1.1, 1.2**
    """

    @given(domain_ids)
    @settings(max_examples=100)
    def test_register_then_get_returns_interpreter(self, domain_id: str):
        """
        For any valid domain_id, registering an interpreter and then
        retrieving it should return a valid interpreter instance.
        """
        registry = DomainRegistry()
        
        # Register
        registry.register(domain_id, MockDomainInterpreter)
        
        # Retrieve
        interpreter = registry.get_interpreter(domain_id)
        
        # Verify round trip
        assert interpreter is not None
        assert isinstance(interpreter, BaseDomainInterpreter)
        assert isinstance(interpreter, MockDomainInterpreter)

    @given(domain_ids)
    @settings(max_examples=100)
    def test_register_then_list_contains_domain(self, domain_id: str):
        """
        For any registered domain, list_domains() should contain that domain_id.
        """
        registry = DomainRegistry()
        
        # Register
        registry.register(domain_id, MockDomainInterpreter)
        
        # List
        domains = registry.list_domains()
        
        # Verify
        assert domain_id in domains

    @given(domain_ids)
    @settings(max_examples=100)
    def test_register_then_has_domain_returns_true(self, domain_id: str):
        """
        For any registered domain, has_domain() should return True.
        """
        registry = DomainRegistry()
        
        # Register
        registry.register(domain_id, MockDomainInterpreter)
        
        # Check
        assert registry.has_domain(domain_id) is True

    @given(domain_ids)
    @settings(max_examples=100)
    def test_unregistered_domain_returns_none(self, domain_id: str):
        """
        For any unregistered domain_id, get_interpreter() should return None.
        """
        registry = DomainRegistry()
        
        # Don't register, just try to get
        interpreter = registry.get_interpreter(domain_id)
        
        assert interpreter is None

    @given(domain_ids, detection_patterns)
    @settings(max_examples=50)
    def test_register_with_ontology_preserves_ontology(
        self, domain_id: str, patterns: list[str]
    ):
        """
        For any domain registered with an ontology, get_ontology() should
        return the same ontology.
        """
        registry = DomainRegistry()
        
        # Create ontology
        ontology = OntologySchema(
            domain_id=domain_id,
            version="1.0",
            entity_types={
                "test_entity": EntityType(
                    name="test_entity",
                    fields={"field1": FieldSpec(name="field1", type="string")},
                    required_fields=["field1"]
                )
            }
        )
        
        # Register with ontology
        registry.register(
            domain_id,
            MockDomainInterpreter,
            ontology=ontology,
            detection_patterns=patterns
        )
        
        # Retrieve ontology
        retrieved_ontology = registry.get_ontology(domain_id)
        
        # Verify
        assert retrieved_ontology is not None
        assert retrieved_ontology.domain_id == domain_id
        assert retrieved_ontology.version == "1.0"
        assert "test_entity" in retrieved_ontology.entity_types

    @given(st.lists(domain_ids, min_size=1, max_size=10, unique=True))
    @settings(max_examples=30)
    def test_multiple_registrations_all_retrievable(self, domain_ids_list: list[str]):
        """
        For any set of registered domains, all should be retrievable.
        """
        registry = DomainRegistry()
        
        # Register all
        for did in domain_ids_list:
            registry.register(did, MockDomainInterpreter)
        
        # Verify all retrievable
        for did in domain_ids_list:
            interpreter = registry.get_interpreter(did)
            assert interpreter is not None
        
        # Verify list contains all
        listed = registry.list_domains()
        for did in domain_ids_list:
            assert did in listed

    @given(domain_ids)
    @settings(max_examples=50)
    def test_get_interpreter_returns_same_instance(self, domain_id: str):
        """
        Multiple calls to get_interpreter() should return the same instance.
        """
        registry = DomainRegistry()
        registry.register(domain_id, MockDomainInterpreter)
        
        # Get twice
        interpreter1 = registry.get_interpreter(domain_id)
        interpreter2 = registry.get_interpreter(domain_id)
        
        # Should be same instance (cached)
        assert interpreter1 is interpreter2

    @given(domain_ids)
    @settings(max_examples=50)
    def test_unregister_removes_domain(self, domain_id: str):
        """
        After unregistering, the domain should no longer be retrievable.
        """
        registry = DomainRegistry()
        
        # Register
        registry.register(domain_id, MockDomainInterpreter)
        assert registry.has_domain(domain_id)
        
        # Unregister
        result = registry.unregister(domain_id)
        
        # Verify
        assert result is True
        assert not registry.has_domain(domain_id)
        assert registry.get_interpreter(domain_id) is None

    @given(domain_ids)
    @settings(max_examples=50)
    def test_get_domain_info_returns_correct_info(self, domain_id: str):
        """
        get_domain_info() should return correct metadata about the domain.
        """
        registry = DomainRegistry()
        registry.register(domain_id, GPUMockInterpreter)
        
        info = registry.get_domain_info(domain_id)
        
        assert info is not None
        assert info["domain_id"] == domain_id
        assert info["interpreter_class"] == "GPUMockInterpreter"
        assert info["requires_gpu"] is True
        assert info["recommended_vram_mb"] == 4096


class TestDomainDetection:
    """
    Tests for domain detection functionality.
    **Validates: Requirements 1.2**
    """

    @given(domain_ids, detection_patterns)
    @settings(max_examples=50)
    def test_detect_domain_with_explicit_domain(self, domain_id: str, patterns: list[str]):
        """
        When document has explicit domain field, detect_domain() should return it.
        """
        registry = DomainRegistry()
        registry.register(domain_id, MockDomainInterpreter, detection_patterns=patterns)
        
        document = {"domain": domain_id, "content": "test content"}
        
        detected = registry.detect_domain(document)
        
        assert detected == domain_id

    @given(domain_ids)
    @settings(max_examples=50)
    def test_detect_domain_with_metadata_domain(self, domain_id: str):
        """
        When document metadata has domain field, detect_domain() should return it.
        """
        registry = DomainRegistry()
        registry.register(domain_id, MockDomainInterpreter)
        
        document = {
            "content": "test content",
            "metadata": {"domain": domain_id}
        }
        
        detected = registry.detect_domain(document)
        
        assert detected == domain_id

    def test_detect_domain_with_pattern_match(self):
        """
        When content matches detection pattern, detect_domain() should return domain.
        """
        registry = DomainRegistry()
        registry.register(
            "metaphysics",
            MockDomainInterpreter,
            detection_patterns=["八字", "五行", "命理"]
        )
        
        document = {"content": "这是一份八字命理分析报告"}
        
        detected = registry.detect_domain(document)
        
        assert detected == "metaphysics"

    def test_detect_domain_returns_none_for_unknown(self):
        """
        When no domain matches, detect_domain() should return None.
        """
        registry = DomainRegistry()
        registry.register("test", MockDomainInterpreter)
        
        document = {"content": "random content"}
        
        detected = registry.detect_domain(document)
        
        assert detected is None


class TestRegistryEdgeCases:
    """
    Edge case tests for DomainRegistry.
    """

    def test_register_empty_domain_id_raises(self):
        """Registering with empty domain_id should raise ValueError."""
        registry = DomainRegistry()
        
        with pytest.raises(ValueError, match="domain_id cannot be empty"):
            registry.register("", MockDomainInterpreter)

    def test_register_non_interpreter_class_raises(self):
        """Registering non-interpreter class should raise TypeError."""
        registry = DomainRegistry()
        
        class NotAnInterpreter:
            pass
        
        with pytest.raises(TypeError, match="must be a subclass of BaseDomainInterpreter"):
            registry.register("test", NotAnInterpreter)

    def test_clear_removes_all_registrations(self):
        """clear() should remove all registrations."""
        registry = DomainRegistry()
        registry.register("domain1", MockDomainInterpreter)
        registry.register("domain2", GPUMockInterpreter)
        
        assert len(registry.list_domains()) == 2
        
        registry.clear()
        
        assert len(registry.list_domains()) == 0

    def test_unregister_nonexistent_returns_false(self):
        """Unregistering nonexistent domain should return False."""
        registry = DomainRegistry()
        
        result = registry.unregister("nonexistent")
        
        assert result is False

    def test_get_interpreter_class_returns_class(self):
        """get_interpreter_class() should return the class, not instance."""
        registry = DomainRegistry()
        registry.register("test", MockDomainInterpreter)
        
        cls = registry.get_interpreter_class("test")
        
        assert cls is MockDomainInterpreter
        assert cls is not registry.get_interpreter("test")
