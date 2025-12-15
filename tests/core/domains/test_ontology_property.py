"""
Property-based tests for OntologySchema validation correctness.

**Feature: vertical-domain-phase2, Property 3: Ontology Validation Correctness**
**Validates: Requirements 3.2, 3.3, 3.4, 3.5**

Property: For any structured data and ontology schema, validation should correctly
identify all schema violations including missing required fields, invalid enum values,
and type mismatches.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume

from core.domains.ontology_schema import (
    OntologySchema,
    EntityType,
    FieldSpec,
    Relationship,
    ValidationRule,
)


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Strategy for valid field types
field_types = st.sampled_from(["string", "integer", "float", "boolean", "array", "object"])

# Strategy for generating valid field names (alphanumeric, starting with letter)
field_names = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_"),
    min_size=1,
    max_size=20,
).filter(lambda x: x[0].isalpha())

# Strategy for entity names
entity_names = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_"),
    min_size=1,
    max_size=15,
).filter(lambda x: x[0].isalpha())


@st.composite
def field_spec_strategy(draw):
    """Generate a FieldSpec with valid configuration."""
    name = draw(field_names)
    field_type = draw(field_types)
    required = draw(st.booleans())
    
    # Generate type-appropriate constraints
    enum_values = None
    minimum = None
    maximum = None
    pattern = None
    
    if field_type == "string":
        # Optionally add enum or pattern
        if draw(st.booleans()):
            enum_values = draw(st.lists(
                st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
                min_size=1,
                max_size=5,
                unique=True,
            ))
    elif field_type in ("integer", "float"):
        # Optionally add min/max
        if draw(st.booleans()):
            minimum = draw(st.integers(min_value=-100, max_value=0))
            maximum = draw(st.integers(min_value=1, max_value=100))
    
    return FieldSpec(
        name=name,
        type=field_type,
        required=required,
        pattern=pattern,
        enum=enum_values,
        minimum=minimum,
        maximum=maximum,
    )


@st.composite
def entity_type_strategy(draw):
    """Generate an EntityType with valid configuration."""
    name = draw(entity_names)
    fields_list = draw(st.lists(field_spec_strategy(), min_size=1, max_size=5))
    
    # Ensure unique field names
    fields = {}
    for fs in fields_list:
        if fs.name not in fields:
            fields[fs.name] = fs
    
    # Required fields must be a subset of actual fields
    required_fields = [fn for fn, fs in fields.items() if fs.required]
    
    return EntityType(
        name=name,
        description=f"Test entity {name}",
        fields=fields,
        required_fields=required_fields,
    )


@st.composite
def ontology_schema_strategy(draw):
    """Generate a valid OntologySchema."""
    domain_id = draw(st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz_"))
    assume(domain_id[0].isalpha())
    
    entity_types_list = draw(st.lists(entity_type_strategy(), min_size=1, max_size=3))
    
    # Ensure unique entity names
    entity_types = {}
    for et in entity_types_list:
        if et.name not in entity_types:
            entity_types[et.name] = et
    
    return OntologySchema(
        domain_id=domain_id,
        version="1.0",
        entity_types=entity_types,
        relationships=[],
        validation_rules=[],
    )


def generate_valid_value_for_type(field_type: str, spec: FieldSpec):
    """Generate a valid value for a given field type and spec."""
    if field_type == "string":
        if spec.enum:
            return spec.enum[0]
        return "valid_string"
    elif field_type == "integer":
        if spec.minimum is not None and spec.maximum is not None:
            return (spec.minimum + spec.maximum) // 2
        return 42
    elif field_type == "float":
        if spec.minimum is not None and spec.maximum is not None:
            return (spec.minimum + spec.maximum) / 2
        return 3.14
    elif field_type == "boolean":
        return True
    elif field_type == "array":
        return []
    elif field_type == "object":
        return {}
    return None


def generate_invalid_value_for_type(field_type: str):
    """Generate an invalid value for a given field type."""
    # Return a value that doesn't match the expected type
    type_to_invalid = {
        "string": 12345,  # int instead of string
        "integer": "not_an_int",  # string instead of int
        "float": "not_a_float",  # string instead of float
        "boolean": "not_a_bool",  # string instead of bool
        "array": "not_an_array",  # string instead of array
        "object": "not_an_object",  # string instead of object
    }
    return type_to_invalid.get(field_type, None)


# =============================================================================
# Property Tests
# =============================================================================

class TestOntologyValidationProperty:
    """
    **Feature: vertical-domain-phase2, Property 3: Ontology Validation Correctness**
    
    Property: For any structured data and ontology schema, validation should correctly
    identify all schema violations including missing required fields, invalid enum values,
    and type mismatches.
    """

    @given(ontology_schema_strategy())
    @settings(max_examples=100, deadline=None)
    def test_valid_data_passes_validation(self, schema: OntologySchema):
        """
        **Feature: vertical-domain-phase2, Property 3: Ontology Validation Correctness**
        
        For any ontology schema, data that conforms to all requirements should pass validation.
        """
        # Generate valid data for the schema
        valid_data = {}
        for entity_name, entity_type in schema.entity_types.items():
            entity_instance = {}
            for field_name, field_spec in entity_type.fields.items():
                entity_instance[field_name] = generate_valid_value_for_type(
                    field_spec.type, field_spec
                )
            valid_data[entity_name] = entity_instance
        
        is_valid, violations = schema.validate(valid_data)
        
        assert is_valid, f"Valid data should pass validation, but got violations: {violations}"
        assert violations == [], f"No violations expected for valid data"

    @given(ontology_schema_strategy())
    @settings(max_examples=100, deadline=None)
    def test_missing_required_field_detected(self, schema: OntologySchema):
        """
        **Feature: vertical-domain-phase2, Property 3: Ontology Validation Correctness**
        
        For any ontology schema with required fields, missing required fields should be detected.
        **Validates: Requirements 3.4**
        """
        # Find an entity with required fields
        entity_with_required = None
        required_field = None
        
        for entity_name, entity_type in schema.entity_types.items():
            if entity_type.required_fields:
                entity_with_required = entity_name
                required_field = entity_type.required_fields[0]
                break
        
        # Skip if no required fields exist
        assume(entity_with_required is not None)
        
        # Generate data missing the required field
        entity_type = schema.entity_types[entity_with_required]
        entity_instance = {}
        for field_name, field_spec in entity_type.fields.items():
            if field_name != required_field:
                entity_instance[field_name] = generate_valid_value_for_type(
                    field_spec.type, field_spec
                )
        
        data = {entity_with_required: entity_instance}
        
        is_valid, violations = schema.validate(data)
        
        assert not is_valid, "Missing required field should fail validation"
        assert any(required_field in v for v in violations), \
            f"Violation should mention missing field '{required_field}'"

    @given(ontology_schema_strategy())
    @settings(max_examples=100, deadline=None)
    def test_type_mismatch_detected(self, schema: OntologySchema):
        """
        **Feature: vertical-domain-phase2, Property 3: Ontology Validation Correctness**
        
        For any ontology schema, type mismatches should be detected.
        **Validates: Requirements 3.2**
        """
        # Find an entity with at least one field
        assume(len(schema.entity_types) > 0)
        
        entity_name = list(schema.entity_types.keys())[0]
        entity_type = schema.entity_types[entity_name]
        assume(len(entity_type.fields) > 0)
        
        # Pick a field to give wrong type
        field_name = list(entity_type.fields.keys())[0]
        field_spec = entity_type.fields[field_name]
        
        # Generate data with wrong type for this field
        entity_instance = {}
        for fn, fs in entity_type.fields.items():
            if fn == field_name:
                entity_instance[fn] = generate_invalid_value_for_type(fs.type)
            else:
                entity_instance[fn] = generate_valid_value_for_type(fs.type, fs)
        
        data = {entity_name: entity_instance}
        
        is_valid, violations = schema.validate(data)
        
        assert not is_valid, "Type mismatch should fail validation"
        assert any("type" in v.lower() for v in violations), \
            f"Violation should mention type error: {violations}"

    @given(ontology_schema_strategy())
    @settings(max_examples=100, deadline=None)
    def test_invalid_enum_value_detected(self, schema: OntologySchema):
        """
        **Feature: vertical-domain-phase2, Property 3: Ontology Validation Correctness**
        
        For any ontology schema with enum fields, invalid enum values should be detected.
        **Validates: Requirements 3.5**
        """
        # Find an entity with an enum field
        entity_with_enum = None
        enum_field_name = None
        
        for entity_name, entity_type in schema.entity_types.items():
            for field_name, field_spec in entity_type.fields.items():
                if field_spec.enum is not None and len(field_spec.enum) > 0:
                    entity_with_enum = entity_name
                    enum_field_name = field_name
                    break
            if entity_with_enum:
                break
        
        # Skip if no enum fields exist
        assume(entity_with_enum is not None)
        
        # Generate data with invalid enum value
        entity_type = schema.entity_types[entity_with_enum]
        entity_instance = {}
        for field_name, field_spec in entity_type.fields.items():
            if field_name == enum_field_name:
                # Use a value not in the enum
                entity_instance[field_name] = "INVALID_ENUM_VALUE_XYZ"
            else:
                entity_instance[field_name] = generate_valid_value_for_type(
                    field_spec.type, field_spec
                )
        
        data = {entity_with_enum: entity_instance}
        
        is_valid, violations = schema.validate(data)
        
        assert not is_valid, "Invalid enum value should fail validation"
        assert any("enum" in v.lower() for v in violations), \
            f"Violation should mention enum error: {violations}"

    @given(ontology_schema_strategy())
    @settings(max_examples=100, deadline=None)
    def test_validation_returns_all_violations(self, schema: OntologySchema):
        """
        **Feature: vertical-domain-phase2, Property 3: Ontology Validation Correctness**
        
        For any ontology schema, validation should return all violations, not just the first one.
        **Validates: Requirements 3.3**
        """
        # Find entities with multiple required fields
        entities_with_multiple_required = [
            (name, et) for name, et in schema.entity_types.items()
            if len(et.required_fields) >= 2
        ]
        
        assume(len(entities_with_multiple_required) > 0)
        
        entity_name, entity_type = entities_with_multiple_required[0]
        
        # Create data missing all required fields
        data = {entity_name: {}}
        
        is_valid, violations = schema.validate(data)
        
        assert not is_valid, "Missing all required fields should fail validation"
        # Should have at least as many violations as required fields
        assert len(violations) >= len(entity_type.required_fields), \
            f"Expected at least {len(entity_type.required_fields)} violations, got {len(violations)}"

    @given(ontology_schema_strategy(), st.integers(min_value=-200, max_value=200))
    @settings(max_examples=100, deadline=None)
    def test_numeric_range_validation(self, schema: OntologySchema, test_value: int):
        """
        **Feature: vertical-domain-phase2, Property 3: Ontology Validation Correctness**
        
        For any ontology schema with numeric range constraints, values outside the range
        should be detected.
        """
        # Find an entity with a numeric field that has min/max constraints
        entity_with_range = None
        range_field_name = None
        field_spec_with_range = None
        
        for entity_name, entity_type in schema.entity_types.items():
            for field_name, field_spec in entity_type.fields.items():
                if (field_spec.type in ("integer", "float") and 
                    field_spec.minimum is not None and 
                    field_spec.maximum is not None):
                    entity_with_range = entity_name
                    range_field_name = field_name
                    field_spec_with_range = field_spec
                    break
            if entity_with_range:
                break
        
        # Skip if no range-constrained fields exist
        assume(entity_with_range is not None)
        
        # Generate data with the test value
        entity_type = schema.entity_types[entity_with_range]
        entity_instance = {}
        for field_name, field_spec in entity_type.fields.items():
            if field_name == range_field_name:
                entity_instance[field_name] = test_value
            else:
                entity_instance[field_name] = generate_valid_value_for_type(
                    field_spec.type, field_spec
                )
        
        data = {entity_with_range: entity_instance}
        
        is_valid, violations = schema.validate(data)
        
        # Check if value is within range
        in_range = (field_spec_with_range.minimum <= test_value <= field_spec_with_range.maximum)
        
        if in_range:
            # Value in range should not cause range violation
            range_violations = [v for v in violations if "minimum" in v or "maximum" in v]
            assert len(range_violations) == 0, \
                f"Value {test_value} in range [{field_spec_with_range.minimum}, {field_spec_with_range.maximum}] should not cause range violation"
        else:
            # Value out of range should cause violation
            assert not is_valid or any("minimum" in v or "maximum" in v for v in violations), \
                f"Value {test_value} outside range should be detected"


class TestOntologySchemaRoundTrip:
    """Test that ontology schemas can be serialized and deserialized correctly."""

    @given(ontology_schema_strategy())
    @settings(max_examples=50, deadline=None)
    def test_to_dict_from_dict_round_trip(self, schema: OntologySchema):
        """
        **Feature: vertical-domain-phase2, Property 3: Ontology Validation Correctness**
        
        For any ontology schema, converting to dict and back should preserve validation behavior.
        """
        # Convert to dict and back
        schema_dict = schema.to_dict()
        restored_schema = OntologySchema.from_dict(schema_dict)
        
        # Generate valid test data
        valid_data = {}
        for entity_name, entity_type in schema.entity_types.items():
            entity_instance = {}
            for field_name, field_spec in entity_type.fields.items():
                entity_instance[field_name] = generate_valid_value_for_type(
                    field_spec.type, field_spec
                )
            valid_data[entity_name] = entity_instance
        
        # Both schemas should validate the same data the same way
        original_result = schema.validate(valid_data)
        restored_result = restored_schema.validate(valid_data)
        
        assert original_result[0] == restored_result[0], \
            "Round-tripped schema should validate data the same way"
