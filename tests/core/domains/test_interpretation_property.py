"""
Property-based tests for InterpretationResult Completeness

**Feature: vertical-domain-phase2, Property 2: Interpretation Result Completeness**
**Validates: Requirements 1.3, 2.2, 5.4**

For any document processed by any domain interpreter, the returned InterpretationResult
should contain non-empty domain_id, structured_data dict, narrative string, and
confidence between 0 and 1.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Any

from core.domains.base_interpreter import BaseDomainInterpreter, InterpretationResult
from core.domains.ontology_schema import OntologySchema
from core.domains.registry import DomainRegistry, reset_domain_registry


# Strategies for property tests
domain_ids = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_")
)

confidence_values = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
invalid_confidence_values = st.one_of(
    st.floats(max_value=-0.01, allow_nan=False),
    st.floats(min_value=1.01, allow_nan=False),
)

narrative_texts = st.text(min_size=0, max_size=1000)

structured_data_values = st.dictionaries(
    keys=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz_"),
    values=st.one_of(
        st.text(max_size=100),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.booleans(),
        st.none(),
    ),
    min_size=0,
    max_size=10
)

metadata_values = st.dictionaries(
    keys=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz_"),
    values=st.one_of(st.text(max_size=50), st.integers(), st.floats(allow_nan=False)),
    min_size=0,
    max_size=5
)


class TestInterpretationResultCompleteness:
    """
    **Feature: vertical-domain-phase2, Property 2: Interpretation Result Completeness**
    **Validates: Requirements 1.3, 2.2, 5.4**
    """

    @given(domain_ids, structured_data_values, narrative_texts, confidence_values, metadata_values)
    @settings(max_examples=100)
    def test_valid_result_has_all_required_fields(
        self,
        domain_id: str,
        structured_data: dict,
        narrative: str,
        confidence: float,
        metadata: dict
    ):
        """
        For any valid inputs, InterpretationResult should contain all required fields.
        """
        result = InterpretationResult(
            domain_id=domain_id,
            structured_data=structured_data,
            narrative=narrative,
            confidence=confidence,
            metadata=metadata,
        )
        
        # Verify all required fields are present and correct type
        assert result.domain_id == domain_id
        assert isinstance(result.domain_id, str)
        assert len(result.domain_id) > 0
        
        assert result.structured_data == structured_data
        assert isinstance(result.structured_data, dict)
        
        assert result.narrative == narrative
        assert isinstance(result.narrative, str)
        
        assert result.confidence == confidence
        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0
        
        assert result.metadata == metadata
        assert isinstance(result.metadata, dict)
        
        # raw_elements should default to empty list
        assert isinstance(result.raw_elements, list)

    @given(confidence_values)
    @settings(max_examples=100)
    def test_confidence_always_in_valid_range(self, confidence: float):
        """
        For any valid confidence value, it should be between 0 and 1.
        """
        result = InterpretationResult(
            domain_id="test",
            structured_data={},
            narrative="",
            confidence=confidence,
        )
        
        assert 0.0 <= result.confidence <= 1.0

    @given(invalid_confidence_values)
    @settings(max_examples=50)
    def test_invalid_confidence_raises_error(self, confidence: float):
        """
        For any confidence value outside [0, 1], creation should raise ValueError.
        """
        with pytest.raises(ValueError, match="confidence must be between 0 and 1"):
            InterpretationResult(
                domain_id="test",
                structured_data={},
                narrative="",
                confidence=confidence,
            )

    def test_empty_domain_id_raises_error(self):
        """
        Empty domain_id should raise ValueError.
        """
        with pytest.raises(ValueError, match="domain_id cannot be empty"):
            InterpretationResult(
                domain_id="",
                structured_data={},
                narrative="",
                confidence=0.5,
            )

    @given(domain_ids, structured_data_values, narrative_texts, confidence_values)
    @settings(max_examples=50)
    def test_result_fields_are_immutable_types(
        self,
        domain_id: str,
        structured_data: dict,
        narrative: str,
        confidence: float
    ):
        """
        InterpretationResult fields should maintain their values after creation.
        """
        result = InterpretationResult(
            domain_id=domain_id,
            structured_data=structured_data,
            narrative=narrative,
            confidence=confidence,
        )
        
        # Fields should be accessible and unchanged
        assert result.domain_id == domain_id
        assert result.structured_data == structured_data
        assert result.narrative == narrative
        assert result.confidence == confidence

    @given(st.lists(st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=st.text(max_size=20),
        min_size=0,
        max_size=3
    ), min_size=0, max_size=5))
    @settings(max_examples=50)
    def test_raw_elements_accepts_list_of_dicts(self, raw_elements: list):
        """
        raw_elements should accept any list of dictionaries.
        """
        result = InterpretationResult(
            domain_id="test",
            structured_data={},
            narrative="",
            confidence=0.5,
            raw_elements=raw_elements,
        )
        
        assert result.raw_elements == raw_elements
        assert isinstance(result.raw_elements, list)


class TestMockInterpreterResults:
    """
    Tests that mock interpreters produce valid InterpretationResults.
    """

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset registry before each test"""
        reset_domain_registry()
        yield
        reset_domain_registry()

    @given(domain_ids, structured_data_values, narrative_texts, confidence_values)
    @settings(max_examples=50)
    def test_interpreter_result_is_complete(
        self,
        domain_id: str,
        structured_data: dict,
        narrative: str,
        confidence: float
    ):
        """
        Any interpreter should produce a complete InterpretationResult.
        """
        # Create a mock interpreter that returns the given values
        class TestInterpreter(BaseDomainInterpreter):
            def __init__(self, did, sd, narr, conf):
                super().__init__()
                self._domain_id = did
                self._sd = sd
                self._narr = narr
                self._conf = conf
            
            @property
            def domain_id(self):
                return self._domain_id
            
            async def interpret(self, document, config=None):
                return InterpretationResult(
                    domain_id=self._domain_id,
                    structured_data=self._sd,
                    narrative=self._narr,
                    confidence=self._conf,
                )
            
            def get_ontology(self):
                return OntologySchema(domain_id=self._domain_id)
            
            def validate_output(self, result):
                return True, []
        
        interpreter = TestInterpreter(domain_id, structured_data, narrative, confidence)
        
        # Verify the interpreter can be used
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            interpreter.interpret({})
        )
        
        # Verify completeness
        assert result.domain_id == domain_id
        assert result.structured_data == structured_data
        assert result.narrative == narrative
        assert result.confidence == confidence
        assert 0.0 <= result.confidence <= 1.0


class TestInterpretationResultEdgeCases:
    """
    Edge case tests for InterpretationResult.
    """

    def test_result_with_empty_structured_data(self):
        """Result should accept empty structured_data."""
        result = InterpretationResult(
            domain_id="test",
            structured_data={},
            narrative="Some narrative",
            confidence=0.8,
        )
        
        assert result.structured_data == {}

    def test_result_with_empty_narrative(self):
        """Result should accept empty narrative."""
        result = InterpretationResult(
            domain_id="test",
            structured_data={"key": "value"},
            narrative="",
            confidence=0.8,
        )
        
        assert result.narrative == ""

    def test_result_with_zero_confidence(self):
        """Result should accept zero confidence."""
        result = InterpretationResult(
            domain_id="test",
            structured_data={},
            narrative="",
            confidence=0.0,
        )
        
        assert result.confidence == 0.0

    def test_result_with_one_confidence(self):
        """Result should accept confidence of 1.0."""
        result = InterpretationResult(
            domain_id="test",
            structured_data={},
            narrative="",
            confidence=1.0,
        )
        
        assert result.confidence == 1.0

    def test_result_with_nested_structured_data(self):
        """Result should accept nested structured_data."""
        nested_data = {
            "level1": {
                "level2": {
                    "level3": "value"
                }
            },
            "array": [1, 2, 3],
            "mixed": [{"a": 1}, {"b": 2}]
        }
        
        result = InterpretationResult(
            domain_id="test",
            structured_data=nested_data,
            narrative="",
            confidence=0.5,
        )
        
        assert result.structured_data == nested_data

    def test_result_with_unicode_content(self):
        """Result should handle unicode content correctly."""
        result = InterpretationResult(
            domain_id="命理",
            structured_data={"八字": "甲子年"},
            narrative="这是一份命理分析报告",
            confidence=0.9,
        )
        
        assert result.domain_id == "命理"
        assert result.structured_data["八字"] == "甲子年"
        assert "命理" in result.narrative

    def test_result_with_special_characters(self):
        """Result should handle special characters."""
        result = InterpretationResult(
            domain_id="test-domain_v2",
            structured_data={"key-with-dash": "value_with_underscore"},
            narrative="Line1\nLine2\tTabbed",
            confidence=0.75,
        )
        
        assert "-" in result.domain_id
        assert "_" in result.domain_id
        assert "\n" in result.narrative
        assert "\t" in result.narrative
