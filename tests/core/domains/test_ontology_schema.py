"""
Unit tests for OntologySchema.

Tests YAML parsing, required field validation, enum validation, and type validation.
_Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
"""
import os
import tempfile
import pytest

from core.domains.ontology_schema import (
    OntologySchema,
    EntityType,
    FieldSpec,
    Relationship,
    ValidationRule,
)


class TestOntologySchemaYAMLParsing:
    """Test YAML parsing functionality. _Requirements: 3.1_"""

    def test_from_yaml_basic(self):
        """Test loading a basic ontology from YAML."""
        yaml_content = """
domain_id: test_domain
version: "1.0"

entity_types:
  person:
    description: "A person entity"
    fields:
      name:
        type: string
        description: "Person's name"
      age:
        type: integer
        minimum: 0
        maximum: 150
    required:
      - name

relationships:
  - name: knows
    source_type: person
    target_type: person
    cardinality: many

validation_rules:
  - rule: "age >= 0"
    message: "Age must be non-negative"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            try:
                schema = OntologySchema.from_yaml(f.name)
                
                assert schema.domain_id == "test_domain"
                assert schema.version == "1.0"
                assert "person" in schema.entity_types
                assert schema.entity_types["person"].fields["name"].type == "string"
                assert schema.entity_types["person"].fields["age"].minimum == 0
                assert schema.entity_types["person"].fields["age"].maximum == 150
                assert "name" in schema.entity_types["person"].required_fields
                assert len(schema.relationships) == 1
                assert schema.relationships[0].name == "knows"
                assert len(schema.validation_rules) == 1
            finally:
                os.unlink(f.name)

    def test_from_yaml_with_enum(self):
        """Test loading ontology with enum fields."""
        yaml_content = """
domain_id: enum_test
version: "1.0"

entity_types:
  status:
    description: "Status entity"
    fields:
      state:
        type: string
        enum:
          - active
          - inactive
          - pending
    required:
      - state
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            try:
                schema = OntologySchema.from_yaml(f.name)
                
                assert schema.entity_types["status"].fields["state"].enum == ["active", "inactive", "pending"]
            finally:
                os.unlink(f.name)

    def test_from_yaml_with_pattern(self):
        """Test loading ontology with regex pattern fields."""
        yaml_content = """
domain_id: pattern_test
version: "1.0"

entity_types:
  email_record:
    description: "Email record"
    fields:
      email:
        type: string
        pattern: "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+[.][a-zA-Z0-9-.]+$"
    required:
      - email
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            
            try:
                schema = OntologySchema.from_yaml(f.name)
                
                assert schema.entity_types["email_record"].fields["email"].pattern is not None
            finally:
                os.unlink(f.name)

    def test_from_dict(self):
        """Test creating ontology from dictionary."""
        data = {
            "domain_id": "dict_test",
            "version": "2.0",
            "entity_types": {
                "item": {
                    "description": "An item",
                    "fields": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                    },
                    "required": ["id"],
                }
            },
            "relationships": [],
            "validation_rules": [],
        }
        
        schema = OntologySchema.from_dict(data)
        
        assert schema.domain_id == "dict_test"
        assert schema.version == "2.0"
        assert "item" in schema.entity_types
        assert schema.entity_types["item"].fields["id"].type == "integer"


class TestOntologySchemaRequiredFieldValidation:
    """Test required field validation. _Requirements: 3.4_"""

    @pytest.fixture
    def schema_with_required(self):
        """Create a schema with required fields."""
        return OntologySchema(
            domain_id="test",
            entity_types={
                "user": EntityType(
                    name="user",
                    fields={
                        "username": FieldSpec(name="username", type="string", required=True),
                        "email": FieldSpec(name="email", type="string", required=True),
                        "bio": FieldSpec(name="bio", type="string", required=False),
                    },
                    required_fields=["username", "email"],
                )
            },
        )

    def test_all_required_fields_present(self, schema_with_required):
        """Test validation passes when all required fields are present."""
        data = {
            "user": {
                "username": "john_doe",
                "email": "john@example.com",
            }
        }
        
        is_valid, violations = schema_with_required.validate(data)
        
        assert is_valid
        assert violations == []

    def test_missing_one_required_field(self, schema_with_required):
        """Test validation fails when one required field is missing."""
        data = {
            "user": {
                "username": "john_doe",
                # email is missing
            }
        }
        
        is_valid, violations = schema_with_required.validate(data)
        
        assert not is_valid
        assert any("email" in v for v in violations)

    def test_missing_all_required_fields(self, schema_with_required):
        """Test validation fails when all required fields are missing."""
        data = {
            "user": {
                "bio": "Just a bio",
            }
        }
        
        is_valid, violations = schema_with_required.validate(data)
        
        assert not is_valid
        assert len(violations) >= 2  # Both username and email should be reported

    def test_required_field_is_none(self, schema_with_required):
        """Test validation fails when required field is None."""
        data = {
            "user": {
                "username": None,
                "email": "john@example.com",
            }
        }
        
        is_valid, violations = schema_with_required.validate(data)
        
        assert not is_valid
        assert any("username" in v for v in violations)


class TestOntologySchemaEnumValidation:
    """Test enum value validation. _Requirements: 3.5_"""

    @pytest.fixture
    def schema_with_enum(self):
        """Create a schema with enum fields."""
        return OntologySchema(
            domain_id="test",
            entity_types={
                "task": EntityType(
                    name="task",
                    fields={
                        "status": FieldSpec(
                            name="status",
                            type="string",
                            enum=["todo", "in_progress", "done"],
                        ),
                        "priority": FieldSpec(
                            name="priority",
                            type="string",
                            enum=["low", "medium", "high"],
                        ),
                    },
                    required_fields=[],
                )
            },
        )

    def test_valid_enum_value(self, schema_with_enum):
        """Test validation passes with valid enum values."""
        data = {
            "task": {
                "status": "todo",
                "priority": "high",
            }
        }
        
        is_valid, violations = schema_with_enum.validate(data)
        
        assert is_valid
        assert violations == []

    def test_invalid_enum_value(self, schema_with_enum):
        """Test validation fails with invalid enum value."""
        data = {
            "task": {
                "status": "invalid_status",
                "priority": "high",
            }
        }
        
        is_valid, violations = schema_with_enum.validate(data)
        
        assert not is_valid
        assert any("enum" in v.lower() for v in violations)
        assert any("invalid_status" in v for v in violations)

    def test_multiple_invalid_enum_values(self, schema_with_enum):
        """Test validation reports all invalid enum values."""
        data = {
            "task": {
                "status": "bad_status",
                "priority": "bad_priority",
            }
        }
        
        is_valid, violations = schema_with_enum.validate(data)
        
        assert not is_valid
        assert len(violations) >= 2


class TestOntologySchemaTypeValidation:
    """Test type validation. _Requirements: 3.2_"""

    @pytest.fixture
    def schema_with_types(self):
        """Create a schema with various field types."""
        return OntologySchema(
            domain_id="test",
            entity_types={
                "record": EntityType(
                    name="record",
                    fields={
                        "name": FieldSpec(name="name", type="string"),
                        "count": FieldSpec(name="count", type="integer"),
                        "score": FieldSpec(name="score", type="float"),
                        "active": FieldSpec(name="active", type="boolean"),
                        "tags": FieldSpec(name="tags", type="array"),
                        "metadata": FieldSpec(name="metadata", type="object"),
                    },
                    required_fields=[],
                )
            },
        )

    def test_valid_types(self, schema_with_types):
        """Test validation passes with correct types."""
        data = {
            "record": {
                "name": "test",
                "count": 42,
                "score": 3.14,
                "active": True,
                "tags": ["a", "b"],
                "metadata": {"key": "value"},
            }
        }
        
        is_valid, violations = schema_with_types.validate(data)
        
        assert is_valid
        assert violations == []

    def test_string_type_mismatch(self, schema_with_types):
        """Test validation fails when string field gets non-string."""
        data = {
            "record": {
                "name": 12345,  # Should be string
            }
        }
        
        is_valid, violations = schema_with_types.validate(data)
        
        assert not is_valid
        assert any("type" in v.lower() for v in violations)

    def test_integer_type_mismatch(self, schema_with_types):
        """Test validation fails when integer field gets non-integer."""
        data = {
            "record": {
                "count": "not_an_int",  # Should be integer
            }
        }
        
        is_valid, violations = schema_with_types.validate(data)
        
        assert not is_valid
        assert any("type" in v.lower() for v in violations)

    def test_float_accepts_integer(self, schema_with_types):
        """Test float field accepts integer values."""
        data = {
            "record": {
                "score": 42,  # Integer should be accepted for float
            }
        }
        
        is_valid, violations = schema_with_types.validate(data)
        
        # Float fields should accept integers
        score_violations = [v for v in violations if "score" in v]
        assert len(score_violations) == 0

    def test_boolean_type_mismatch(self, schema_with_types):
        """Test validation fails when boolean field gets non-boolean."""
        data = {
            "record": {
                "active": "yes",  # Should be boolean
            }
        }
        
        is_valid, violations = schema_with_types.validate(data)
        
        assert not is_valid
        assert any("type" in v.lower() for v in violations)

    def test_array_type_mismatch(self, schema_with_types):
        """Test validation fails when array field gets non-array."""
        data = {
            "record": {
                "tags": "not_an_array",  # Should be array
            }
        }
        
        is_valid, violations = schema_with_types.validate(data)
        
        assert not is_valid
        assert any("type" in v.lower() for v in violations)

    def test_object_type_mismatch(self, schema_with_types):
        """Test validation fails when object field gets non-object."""
        data = {
            "record": {
                "metadata": "not_an_object",  # Should be object
            }
        }
        
        is_valid, violations = schema_with_types.validate(data)
        
        assert not is_valid
        assert any("type" in v.lower() for v in violations)


class TestOntologySchemaNumericRangeValidation:
    """Test numeric range validation."""

    @pytest.fixture
    def schema_with_ranges(self):
        """Create a schema with numeric range constraints."""
        return OntologySchema(
            domain_id="test",
            entity_types={
                "measurement": EntityType(
                    name="measurement",
                    fields={
                        "temperature": FieldSpec(
                            name="temperature",
                            type="float",
                            minimum=-273.15,
                            maximum=1000.0,
                        ),
                        "percentage": FieldSpec(
                            name="percentage",
                            type="integer",
                            minimum=0,
                            maximum=100,
                        ),
                    },
                    required_fields=[],
                )
            },
        )

    def test_value_within_range(self, schema_with_ranges):
        """Test validation passes when value is within range."""
        data = {
            "measurement": {
                "temperature": 25.0,
                "percentage": 50,
            }
        }
        
        is_valid, violations = schema_with_ranges.validate(data)
        
        assert is_valid
        assert violations == []

    def test_value_below_minimum(self, schema_with_ranges):
        """Test validation fails when value is below minimum."""
        data = {
            "measurement": {
                "percentage": -10,  # Below minimum of 0
            }
        }
        
        is_valid, violations = schema_with_ranges.validate(data)
        
        assert not is_valid
        assert any("minimum" in v for v in violations)

    def test_value_above_maximum(self, schema_with_ranges):
        """Test validation fails when value is above maximum."""
        data = {
            "measurement": {
                "percentage": 150,  # Above maximum of 100
            }
        }
        
        is_valid, violations = schema_with_ranges.validate(data)
        
        assert not is_valid
        assert any("maximum" in v for v in violations)

    def test_value_at_boundary(self, schema_with_ranges):
        """Test validation passes when value is at boundary."""
        data = {
            "measurement": {
                "percentage": 0,  # At minimum
            }
        }
        
        is_valid, violations = schema_with_ranges.validate(data)
        
        # Value at boundary should be valid
        percentage_violations = [v for v in violations if "percentage" in v]
        assert len(percentage_violations) == 0


class TestOntologySchemaPatternValidation:
    """Test regex pattern validation."""

    @pytest.fixture
    def schema_with_pattern(self):
        """Create a schema with pattern constraints."""
        return OntologySchema(
            domain_id="test",
            entity_types={
                "contact": EntityType(
                    name="contact",
                    fields={
                        "phone": FieldSpec(
                            name="phone",
                            type="string",
                            pattern=r"^\d{3}-\d{3}-\d{4}$",
                        ),
                    },
                    required_fields=[],
                )
            },
        )

    def test_value_matches_pattern(self, schema_with_pattern):
        """Test validation passes when value matches pattern."""
        data = {
            "contact": {
                "phone": "123-456-7890",
            }
        }
        
        is_valid, violations = schema_with_pattern.validate(data)
        
        assert is_valid
        assert violations == []

    def test_value_does_not_match_pattern(self, schema_with_pattern):
        """Test validation fails when value doesn't match pattern."""
        data = {
            "contact": {
                "phone": "invalid-phone",
            }
        }
        
        is_valid, violations = schema_with_pattern.validate(data)
        
        assert not is_valid
        assert any("pattern" in v for v in violations)


class TestOntologySchemaEntityList:
    """Test validation of entity lists."""

    @pytest.fixture
    def schema(self):
        """Create a basic schema."""
        return OntologySchema(
            domain_id="test",
            entity_types={
                "item": EntityType(
                    name="item",
                    fields={
                        "name": FieldSpec(name="name", type="string", required=True),
                    },
                    required_fields=["name"],
                )
            },
        )

    def test_validate_entity_list(self, schema):
        """Test validation of a list of entities."""
        data = {
            "item": [
                {"name": "item1"},
                {"name": "item2"},
                {"name": "item3"},
            ]
        }
        
        is_valid, violations = schema.validate(data)
        
        assert is_valid
        assert violations == []

    def test_validate_entity_list_with_invalid_item(self, schema):
        """Test validation fails when list contains invalid item."""
        data = {
            "item": [
                {"name": "item1"},
                {},  # Missing required field
                {"name": "item3"},
            ]
        }
        
        is_valid, violations = schema.validate(data)
        
        assert not is_valid
        assert any("[1]" in v for v in violations)  # Should reference index 1


class TestOntologySchemaToDict:
    """Test serialization to dictionary."""

    def test_to_dict_preserves_structure(self):
        """Test that to_dict preserves schema structure."""
        schema = OntologySchema(
            domain_id="test",
            version="2.0",
            entity_types={
                "entity": EntityType(
                    name="entity",
                    description="Test entity",
                    fields={
                        "field1": FieldSpec(
                            name="field1",
                            type="string",
                            enum=["a", "b"],
                        ),
                    },
                    required_fields=["field1"],
                )
            },
            relationships=[
                Relationship(
                    name="rel",
                    source_type="entity",
                    target_type="entity",
                    cardinality="many",
                )
            ],
            validation_rules=[
                ValidationRule(rule="test", message="Test message")
            ],
        )
        
        result = schema.to_dict()
        
        assert result["domain_id"] == "test"
        assert result["version"] == "2.0"
        assert "entity" in result["entity_types"]
        assert result["entity_types"]["entity"]["fields"]["field1"]["enum"] == ["a", "b"]
        assert len(result["relationships"]) == 1
        assert len(result["validation_rules"]) == 1
