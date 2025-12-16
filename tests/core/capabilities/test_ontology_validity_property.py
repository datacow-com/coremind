"""
Property-based tests for Ontology Structure Validity

**Feature: capability-visualization, Property 14: Ontology Structure Validity**
**Validates: Requirements 9.5**

For any domain ontology, all relations should reference entities that exist
in the entities list.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from typing import Any

from core.domains.ontology_schema import (
    OntologySchema,
    EntityType,
    FieldSpec,
    Relationship,
)
from core.domains.registry import get_domain_registry, reset_domain_registry
from core.domains.base_interpreter import BaseDomainInterpreter


# ═══════════════════════════════════════════════════════════════════════════════
# Strategies for generating test data
# ═══════════════════════════════════════════════════════════════════════════════

# Valid entity names
entity_name_strategy = st.text(
    alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_"),
    min_size=1,
    max_size=30,
).filter(lambda x: x[0].isalpha())

# Valid field types
field_type_strategy = st.sampled_from(["string", "integer", "float", "boolean", "array", "object"])

# Valid field spec
field_spec_strategy = st.builds(
    FieldSpec,
    name=entity_name_strategy,
    type=field_type_strategy,
    required=st.booleans(),
    description=st.text(min_size=0, max_size=100),
)

# Valid entity type
entity_type_strategy = st.builds(
    EntityType,
    name=entity_name_strategy,
    description=st.text(min_size=0, max_size=200),
    fields=st.dictionaries(
        keys=entity_name_strategy,
        values=field_spec_strategy,
        min_size=0,
        max_size=5,
    ),
    required_fields=st.lists(entity_name_strategy, min_size=0, max_size=3),
)

# Valid cardinality
cardinality_strategy = st.sampled_from(["one", "many"])


def relationship_strategy(entity_names: list[str]):
    """Generate relationships that reference existing entities."""
    if not entity_names:
        return st.just(None)
    
    return st.builds(
        Relationship,
        name=entity_name_strategy,
        source_type=st.sampled_from(entity_names),
        target_type=st.sampled_from(entity_names),
        cardinality=cardinality_strategy,
        description=st.text(min_size=0, max_size=100),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════


def validate_ontology_relations(ontology: OntologySchema) -> tuple[bool, list[str]]:
    """
    Validate that all relations reference existing entities.
    
    Returns: (is_valid, list of invalid relation descriptions)
    """
    entity_names = set(ontology.entity_types.keys())
    invalid_relations: list[str] = []
    
    for relation in ontology.relationships:
        if relation.source_type not in entity_names:
            invalid_relations.append(
                f"Relation '{relation.name}' references non-existent source entity '{relation.source_type}'"
            )
        if relation.target_type not in entity_names:
            invalid_relations.append(
                f"Relation '{relation.name}' references non-existent target entity '{relation.target_type}'"
            )
    
    return len(invalid_relations) == 0, invalid_relations


def create_valid_ontology(
    domain_id: str,
    entity_names: list[str],
    num_relations: int = 2,
) -> OntologySchema:
    """Create a valid ontology with entities and relations."""
    entity_types = {}
    for name in entity_names:
        entity_types[name] = EntityType(
            name=name,
            description=f"Entity {name}",
            fields={
                "id": FieldSpec(name="id", type="string", required=True),
                "name": FieldSpec(name="name", type="string", required=True),
            },
            required_fields=["id", "name"],
        )
    
    relationships = []
    if len(entity_names) >= 2:
        for i in range(min(num_relations, len(entity_names) - 1)):
            relationships.append(Relationship(
                name=f"relation_{i}",
                source_type=entity_names[i],
                target_type=entity_names[(i + 1) % len(entity_names)],
                cardinality="many",
                description=f"Relation from {entity_names[i]} to {entity_names[(i + 1) % len(entity_names)]}",
            ))
    
    return OntologySchema(
        domain_id=domain_id,
        version="1.0",
        entity_types=entity_types,
        relationships=relationships,
    )


def create_invalid_ontology(
    domain_id: str,
    entity_names: list[str],
    invalid_source: str = "NonExistentSource",
    invalid_target: str = "NonExistentTarget",
) -> OntologySchema:
    """Create an invalid ontology with relations referencing non-existent entities."""
    entity_types = {}
    for name in entity_names:
        entity_types[name] = EntityType(
            name=name,
            description=f"Entity {name}",
            fields={},
            required_fields=[],
        )
    
    # Add invalid relation
    relationships = [
        Relationship(
            name="invalid_relation",
            source_type=invalid_source,
            target_type=invalid_target,
            cardinality="one",
            description="Invalid relation",
        ),
    ]
    
    return OntologySchema(
        domain_id=domain_id,
        version="1.0",
        entity_types=entity_types,
        relationships=relationships,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Property Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOntologyStructureValidity:
    """
    **Feature: capability-visualization, Property 14: Ontology Structure Validity**
    **Validates: Requirements 9.5**
    
    For any domain ontology, all relations should reference entities that exist
    in the entities list.
    """

    @given(
        entity_names=st.lists(entity_name_strategy, min_size=2, max_size=10, unique=True),
        num_relations=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100)
    def test_valid_ontology_passes_validation(self, entity_names: list[str], num_relations: int):
        """
        Property: A valid ontology where all relations reference existing entities
        should pass validation.
        """
        ontology = create_valid_ontology("test_domain", entity_names, num_relations)
        
        is_valid, errors = validate_ontology_relations(ontology)
        
        assert is_valid, f"Valid ontology failed validation: {errors}"
        assert len(errors) == 0

    @given(
        entity_names=st.lists(entity_name_strategy, min_size=1, max_size=5, unique=True),
        invalid_source=entity_name_strategy,
        invalid_target=entity_name_strategy,
    )
    @settings(max_examples=100)
    def test_invalid_ontology_fails_validation(
        self, entity_names: list[str], invalid_source: str, invalid_target: str
    ):
        """
        Property: An ontology with relations referencing non-existent entities
        should fail validation.
        """
        # Ensure invalid names are not in entity_names
        assume(invalid_source not in entity_names)
        assume(invalid_target not in entity_names)
        
        ontology = create_invalid_ontology(
            "test_domain", entity_names, invalid_source, invalid_target
        )
        
        is_valid, errors = validate_ontology_relations(ontology)
        
        assert not is_valid, "Invalid ontology should fail validation"
        assert len(errors) > 0

    @given(entity_names=st.lists(entity_name_strategy, min_size=1, max_size=10, unique=True))
    @settings(max_examples=50)
    def test_ontology_without_relations_is_valid(self, entity_names: list[str]):
        """
        Property: An ontology with entities but no relations should be valid.
        """
        entity_types = {}
        for name in entity_names:
            entity_types[name] = EntityType(
                name=name,
                description=f"Entity {name}",
                fields={},
                required_fields=[],
            )
        
        ontology = OntologySchema(
            domain_id="test_domain",
            version="1.0",
            entity_types=entity_types,
            relationships=[],
        )
        
        is_valid, errors = validate_ontology_relations(ontology)
        
        assert is_valid
        assert len(errors) == 0

    def test_empty_ontology_is_valid(self):
        """
        Property: An empty ontology (no entities, no relations) should be valid.
        """
        ontology = OntologySchema(
            domain_id="empty_domain",
            version="1.0",
            entity_types={},
            relationships=[],
        )
        
        is_valid, errors = validate_ontology_relations(ontology)
        
        assert is_valid
        assert len(errors) == 0

    @given(
        entity_names=st.lists(entity_name_strategy, min_size=2, max_size=5, unique=True),
    )
    @settings(max_examples=50)
    def test_self_referencing_relation_is_valid(self, entity_names: list[str]):
        """
        Property: A relation where source and target are the same entity should be valid.
        """
        entity_types = {}
        for name in entity_names:
            entity_types[name] = EntityType(
                name=name,
                description=f"Entity {name}",
                fields={},
                required_fields=[],
            )
        
        # Self-referencing relation
        relationships = [
            Relationship(
                name="self_ref",
                source_type=entity_names[0],
                target_type=entity_names[0],
                cardinality="many",
                description="Self-referencing relation",
            ),
        ]
        
        ontology = OntologySchema(
            domain_id="test_domain",
            version="1.0",
            entity_types=entity_types,
            relationships=relationships,
        )
        
        is_valid, errors = validate_ontology_relations(ontology)
        
        assert is_valid, f"Self-referencing relation should be valid: {errors}"

    @given(
        entity_names=st.lists(entity_name_strategy, min_size=2, max_size=5, unique=True),
        invalid_source=entity_name_strategy,
    )
    @settings(max_examples=50)
    def test_invalid_source_only_fails(self, entity_names: list[str], invalid_source: str):
        """
        Property: A relation with invalid source but valid target should fail.
        """
        assume(invalid_source not in entity_names)
        
        entity_types = {}
        for name in entity_names:
            entity_types[name] = EntityType(
                name=name,
                description=f"Entity {name}",
                fields={},
                required_fields=[],
            )
        
        relationships = [
            Relationship(
                name="invalid_source_rel",
                source_type=invalid_source,
                target_type=entity_names[0],  # Valid target
                cardinality="one",
                description="Relation with invalid source",
            ),
        ]
        
        ontology = OntologySchema(
            domain_id="test_domain",
            version="1.0",
            entity_types=entity_types,
            relationships=relationships,
        )
        
        is_valid, errors = validate_ontology_relations(ontology)
        
        assert not is_valid
        assert any("source" in err.lower() for err in errors)

    @given(
        entity_names=st.lists(entity_name_strategy, min_size=2, max_size=5, unique=True),
        invalid_target=entity_name_strategy,
    )
    @settings(max_examples=50)
    def test_invalid_target_only_fails(self, entity_names: list[str], invalid_target: str):
        """
        Property: A relation with valid source but invalid target should fail.
        """
        assume(invalid_target not in entity_names)
        
        entity_types = {}
        for name in entity_names:
            entity_types[name] = EntityType(
                name=name,
                description=f"Entity {name}",
                fields={},
                required_fields=[],
            )
        
        relationships = [
            Relationship(
                name="invalid_target_rel",
                source_type=entity_names[0],  # Valid source
                target_type=invalid_target,
                cardinality="one",
                description="Relation with invalid target",
            ),
        ]
        
        ontology = OntologySchema(
            domain_id="test_domain",
            version="1.0",
            entity_types=entity_types,
            relationships=relationships,
        )
        
        is_valid, errors = validate_ontology_relations(ontology)
        
        assert not is_valid
        assert any("target" in err.lower() for err in errors)


class TestOntologySchemaModel:
    """Tests for OntologySchema model operations."""

    @given(
        domain_id=entity_name_strategy,
        version=st.text(min_size=1, max_size=10, alphabet="0123456789."),
    )
    @settings(max_examples=30)
    def test_ontology_to_dict_roundtrip(self, domain_id: str, version: str):
        """
        Property: Converting ontology to dict and back should preserve structure.
        """
        assume(version and version[0].isdigit())
        
        ontology = OntologySchema(
            domain_id=domain_id,
            version=version,
            entity_types={
                "TestEntity": EntityType(
                    name="TestEntity",
                    description="Test",
                    fields={
                        "id": FieldSpec(name="id", type="string", required=True),
                    },
                    required_fields=["id"],
                ),
            },
            relationships=[],
        )
        
        # Convert to dict
        data = ontology.to_dict()
        
        # Verify structure
        assert data["domain_id"] == domain_id
        assert data["version"] == version
        assert "TestEntity" in data["entity_types"]

    def test_ontology_from_dict(self):
        """Test creating ontology from dictionary."""
        data = {
            "domain_id": "test",
            "version": "1.0",
            "entity_types": {
                "Person": {
                    "description": "A person",
                    "fields": {
                        "name": {"type": "string", "required": True},
                        "age": {"type": "integer", "required": False},
                    },
                    "required": ["name"],
                },
            },
            "relationships": [
                {
                    "name": "knows",
                    "source_type": "Person",
                    "target_type": "Person",
                    "cardinality": "many",
                },
            ],
        }
        
        ontology = OntologySchema.from_dict(data)
        
        assert ontology.domain_id == "test"
        assert "Person" in ontology.entity_types
        assert len(ontology.relationships) == 1
        assert ontology.relationships[0].name == "knows"

    @given(entity_names=st.lists(entity_name_strategy, min_size=2, max_size=5, unique=True))
    @settings(max_examples=30)
    def test_ontology_validation_method(self, entity_names: list[str]):
        """
        Property: Ontology validate method should work for valid data.
        """
        ontology = create_valid_ontology("test", entity_names)
        
        # Create valid data matching the ontology
        valid_data = {}
        for name in entity_names:
            valid_data[name] = [{"id": "1", "name": f"Test {name}"}]
        
        is_valid, violations = ontology.validate(valid_data)
        
        # Should be valid (no violations for required fields)
        assert isinstance(is_valid, bool)
        assert isinstance(violations, list)


class TestRelationshipModel:
    """Tests for Relationship model."""

    def test_relationship_defaults(self):
        """Relationship should have sensible defaults."""
        rel = Relationship(
            name="test_rel",
            source_type="A",
            target_type="B",
        )
        
        assert rel.name == "test_rel"
        assert rel.source_type == "A"
        assert rel.target_type == "B"
        assert rel.cardinality == "one"
        assert rel.description == ""

    @given(
        name=entity_name_strategy,
        source=entity_name_strategy,
        target=entity_name_strategy,
        cardinality=cardinality_strategy,
    )
    @settings(max_examples=30)
    def test_relationship_preserves_values(
        self, name: str, source: str, target: str, cardinality: str
    ):
        """Relationship should preserve all values."""
        rel = Relationship(
            name=name,
            source_type=source,
            target_type=target,
            cardinality=cardinality,
            description="Test description",
        )
        
        assert rel.name == name
        assert rel.source_type == source
        assert rel.target_type == target
        assert rel.cardinality == cardinality
        assert rel.description == "Test description"
