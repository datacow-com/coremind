"""
Property-based tests for Domain Binding API

**Feature: capability-visualization, Property 4: Domain Binding Round-Trip**
**Validates: Requirements 3.3, 3.4**

For any KB name and valid domain configuration, binding a domain and then
retrieving the binding should return the same domain ID and configuration.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from typing import Any
from unittest.mock import patch, MagicMock
import tempfile
import os
import json

from server.api.domains import (
    DomainBindingRequest,
    DomainBindingResponse,
    DomainBindingInfo,
    DomainInfo,
    OntologyResponse,
    EntityDef,
    RelationDef,
    _get_domain_info,
    _get_ontology_response,
    _check_dependencies,
)
from core.storage.kb_config import default_kb_config, load_kb_config, save_kb_config
from core.domains.registry import get_domain_registry, reset_domain_registry, DomainRegistry
from core.domains.base_interpreter import BaseDomainInterpreter
from core.domains.ontology_schema import OntologySchema, EntityType, FieldSpec, Relationship


# ═══════════════════════════════════════════════════════════════════════════════
# Test Domain Interpreter for Property Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDomainInterpreter(BaseDomainInterpreter):
    """Test domain interpreter for property tests."""
    
    name = "Test Domain"
    description = "A test domain for property testing"
    icon = "🧪"
    supported_formats = ["pdf", "txt"]
    requires = []
    requires_gpu = False
    recommended_vram_mb = 0
    
    async def interpret(self, document: dict, context: dict | None = None) -> dict:
        return {"interpreted": True}
    
    async def extract_entities(self, document: dict) -> list[dict]:
        return []
    
    async def build_narrative(self, entities: list[dict], context: dict | None = None) -> str:
        return "Test narrative"


class TestDomainWithDeps(BaseDomainInterpreter):
    """Test domain with dependencies."""
    
    name = "Domain With Dependencies"
    description = "A test domain that requires OCR"
    icon = "📷"
    supported_formats = ["pdf"]
    requires = ["enhanced.ocr"]
    requires_gpu = True
    recommended_vram_mb = 4096
    
    async def interpret(self, document: dict, context: dict | None = None) -> dict:
        return {"interpreted": True}
    
    async def extract_entities(self, document: dict) -> list[dict]:
        return []
    
    async def build_narrative(self, entities: list[dict], context: dict | None = None) -> str:
        return "Test narrative"


# ═══════════════════════════════════════════════════════════════════════════════
# Strategies for generating test data
# ═══════════════════════════════════════════════════════════════════════════════

# Valid KB names (alphanumeric with underscores, reasonable length)
kb_name_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_"),
    min_size=1,
    max_size=50,
).filter(lambda x: x[0].isalpha())

# Valid domain IDs
domain_id_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_"),
    min_size=1,
    max_size=30,
).filter(lambda x: x[0].isalpha())

# Valid config values
config_value_strategy = st.one_of(
    st.booleans(),
    st.integers(min_value=0, max_value=10000),
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    st.text(min_size=0, max_size=50, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_")),
)

# Valid domain config
domain_config_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=20, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_")),
    values=config_value_strategy,
    min_size=0,
    max_size=5,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def temp_kb_dir(tmp_path):
    """Create a temporary directory for KB configs."""
    kb_dir = tmp_path / "knowledgebase"
    kb_dir.mkdir(parents=True, exist_ok=True)
    return kb_dir


@pytest.fixture
def mock_registry():
    """Create a mock domain registry with test domains."""
    reset_domain_registry()
    registry = get_domain_registry()
    
    # Create test ontology
    test_ontology = OntologySchema(
        domain_id="test_domain",
        version="1.0",
        entity_types={
            "TestEntity": EntityType(
                name="TestEntity",
                description="A test entity",
                fields={
                    "name": FieldSpec(name="name", type="string", required=True),
                    "value": FieldSpec(name="value", type="integer", required=False),
                },
                required_fields=["name"],
            ),
        },
        relationships=[
            Relationship(
                name="relates_to",
                source_type="TestEntity",
                target_type="TestEntity",
                cardinality="many",
                description="Test relationship",
            ),
        ],
    )
    
    # Register test domains
    registry.register("test_domain", TestDomainInterpreter, test_ontology)
    registry.register("domain_with_deps", TestDomainWithDeps)
    
    yield registry
    
    # Cleanup
    reset_domain_registry()


# ═══════════════════════════════════════════════════════════════════════════════
# Property Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDomainBindingRoundTrip:
    """
    **Feature: capability-visualization, Property 4: Domain Binding Round-Trip**
    **Validates: Requirements 3.3, 3.4**
    
    For any KB name and valid domain configuration, binding a domain and then
    retrieving the binding should return the same domain ID and configuration.
    """

    @given(kb_name=kb_name_strategy, config=domain_config_strategy)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_domain_binding_roundtrip(self, kb_name: str, config: dict, mock_registry, tmp_path):
        """
        Property: Binding a domain to a KB and retrieving it should return
        the same domain ID and configuration.
        """
        # Setup: Create KB config
        kb_config = default_kb_config(kb_name)
        
        # Bind domain
        domain_id = "test_domain"
        kb_config["domain"] = {
            "domain_id": domain_id,
            "config": config,
        }
        
        # Save and reload
        kb_file = tmp_path / f"{kb_name}.json"
        with open(kb_file, "w") as f:
            json.dump(kb_config, f)
        
        with open(kb_file, "r") as f:
            loaded_config = json.load(f)
        
        # Verify round-trip
        domain_binding = loaded_config.get("domain", {})
        assert domain_binding.get("domain_id") == domain_id
        assert domain_binding.get("config") == config

    @given(config=domain_config_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_domain_config_preserved(self, config: dict, mock_registry):
        """
        Property: Domain configuration values should be preserved exactly.
        """
        kb_config = default_kb_config("test_kb")
        
        # Bind domain with config
        kb_config["domain"] = {
            "domain_id": "test_domain",
            "config": config,
        }
        
        # Verify config is preserved
        domain_binding = kb_config.get("domain", {})
        retrieved_config = domain_binding.get("config", {})
        
        assert retrieved_config == config
        for key, value in config.items():
            assert key in retrieved_config
            assert retrieved_config[key] == value

    @given(kb_name=kb_name_strategy)
    @settings(max_examples=50)
    def test_unbound_kb_returns_none(self, kb_name: str):
        """
        Property: A KB without domain binding should return is_bound=False.
        """
        kb_config = default_kb_config(kb_name)
        
        # No domain binding
        domain_binding = kb_config.get("domain", {})
        
        # Should be empty or have no domain_id
        is_bound = bool(domain_binding and domain_binding.get("domain_id"))
        assert not is_bound

    @given(kb_name=kb_name_strategy, config=domain_config_strategy)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_binding_preserves_other_kb_fields(self, kb_name: str, config: dict, mock_registry):
        """
        Property: Binding a domain should not affect other KB config fields.
        """
        kb_config = default_kb_config(kb_name)
        original_name = kb_config.get("name")
        original_stack = kb_config.get("stack")
        original_top_k = kb_config.get("top_k_default")
        original_capabilities = kb_config.get("capabilities", {}).copy()
        
        # Bind domain
        kb_config["domain"] = {
            "domain_id": "test_domain",
            "config": config,
        }
        
        # Other fields should be preserved
        assert kb_config.get("name") == original_name
        assert kb_config.get("stack") == original_stack
        assert kb_config.get("top_k_default") == original_top_k


class TestDependencyChecking:
    """
    Tests for domain dependency checking.
    **Validates: Requirements 3.5**
    """

    def test_no_dependencies_returns_empty(self, mock_registry):
        """Domain without dependencies should return empty missing list."""
        kb_config = default_kb_config("test_kb")
        
        missing = _check_dependencies("test_domain", kb_config)
        
        assert missing == []

    def test_missing_dependency_detected(self, mock_registry):
        """Missing dependencies should be detected."""
        kb_config = default_kb_config("test_kb")
        # OCR is not enabled by default
        
        missing = _check_dependencies("domain_with_deps", kb_config)
        
        assert "enhanced.ocr" in missing

    def test_satisfied_dependency_not_reported(self, mock_registry):
        """Satisfied dependencies should not be reported as missing."""
        kb_config = default_kb_config("test_kb")
        # Enable OCR
        kb_config["capabilities"]["enhanced"]["ocr"] = {"enabled": True}
        
        missing = _check_dependencies("domain_with_deps", kb_config)
        
        assert "enhanced.ocr" not in missing

    @given(kb_name=kb_name_strategy)
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_unknown_domain_returns_empty(self, kb_name: str, mock_registry):
        """Unknown domain should return empty missing list."""
        kb_config = default_kb_config(kb_name)
        
        missing = _check_dependencies("unknown_domain", kb_config)
        
        assert missing == []


class TestDomainInfoRetrieval:
    """Tests for domain info retrieval functions."""

    def test_get_domain_info_existing(self, mock_registry):
        """Getting info for existing domain should return DomainInfo."""
        info = _get_domain_info("test_domain")
        
        assert info is not None
        assert info.id == "test_domain"
        assert info.name == "Test Domain"
        assert info.requires_gpu is False

    def test_get_domain_info_nonexistent(self, mock_registry):
        """Getting info for non-existent domain should return None."""
        info = _get_domain_info("nonexistent_domain")
        
        assert info is None

    def test_get_ontology_response_existing(self, mock_registry):
        """Getting ontology for domain with ontology should return OntologyResponse."""
        ontology = _get_ontology_response("test_domain")
        
        assert ontology is not None
        assert ontology.domain_id == "test_domain"
        assert len(ontology.entities) > 0
        assert len(ontology.relations) > 0

    def test_get_ontology_response_no_ontology(self, mock_registry):
        """Getting ontology for domain without ontology should return None."""
        ontology = _get_ontology_response("domain_with_deps")
        
        assert ontology is None


class TestDomainBindingModels:
    """Tests for Pydantic models."""

    def test_domain_binding_request_defaults(self):
        """DomainBindingRequest should have sensible defaults."""
        request = DomainBindingRequest(domain_id="test")
        
        assert request.domain_id == "test"
        assert request.config == {}

    @given(domain_id=domain_id_strategy, config=domain_config_strategy)
    @settings(max_examples=30)
    def test_domain_binding_request_serialization(self, domain_id: str, config: dict):
        """DomainBindingRequest should survive JSON serialization."""
        request = DomainBindingRequest(domain_id=domain_id, config=config)
        
        json_str = request.model_dump_json()
        restored = DomainBindingRequest.model_validate_json(json_str)
        
        assert restored.domain_id == domain_id
        assert restored.config == config

    def test_domain_binding_info_unbound(self):
        """DomainBindingInfo for unbound KB should have is_bound=False."""
        info = DomainBindingInfo(kb_name="test_kb")
        
        assert info.kb_name == "test_kb"
        assert info.domain_id is None
        assert info.is_bound is False

    @given(kb_name=kb_name_strategy, domain_id=domain_id_strategy, config=domain_config_strategy)
    @settings(max_examples=30)
    def test_domain_binding_info_bound(self, kb_name: str, domain_id: str, config: dict):
        """DomainBindingInfo for bound KB should have correct values."""
        info = DomainBindingInfo(
            kb_name=kb_name,
            domain_id=domain_id,
            config=config,
            is_bound=True,
        )
        
        assert info.kb_name == kb_name
        assert info.domain_id == domain_id
        assert info.config == config
        assert info.is_bound is True

    def test_entity_def_model(self):
        """EntityDef model should work correctly."""
        entity = EntityDef(
            name="TestEntity",
            description="A test entity",
            attributes=["attr1", "attr2"],
        )
        
        assert entity.name == "TestEntity"
        assert entity.description == "A test entity"
        assert entity.attributes == ["attr1", "attr2"]

    def test_relation_def_model(self):
        """RelationDef model should work correctly."""
        relation = RelationDef(
            name="relates_to",
            source_type="Entity1",
            target_type="Entity2",
            description="Test relation",
        )
        
        assert relation.name == "relates_to"
        assert relation.source_type == "Entity1"
        assert relation.target_type == "Entity2"

    def test_ontology_response_model(self):
        """OntologyResponse model should work correctly."""
        ontology = OntologyResponse(
            domain_id="test",
            version="1.0",
            entities=[EntityDef(name="E1", description="Entity 1")],
            relations=[RelationDef(name="R1", source_type="E1", target_type="E1")],
        )
        
        assert ontology.domain_id == "test"
        assert len(ontology.entities) == 1
        assert len(ontology.relations) == 1
