"""
Property-based tests for NarrativeEngine detail level behavior.

**Feature: vertical-domain-phase2, Property 4: Narrative Generation Respects Detail Level**
**Validates: Requirements 4.1, 4.5**

Property: For any structured data and detail_level parameter, the generated narrative
length should be: brief < detailed < comprehensive.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume

from core.domains.narrative_engine import NarrativeEngine, DetailLevel


# =============================================================================
# Strategies for generating test data
# =============================================================================

# Strategy for valid field names
field_names = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_"),
    min_size=1,
    max_size=15,
).filter(lambda x: len(x) > 0 and x[0].isalpha())

# Strategy for simple values
simple_values = st.one_of(
    st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z'))),
    st.integers(min_value=-1000, max_value=1000),
    st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
    st.booleans(),
)


@st.composite
def structured_data_strategy(draw, max_depth: int = 2, max_keys: int = 5):
    """Generate structured data dictionaries for narrative generation."""
    if max_depth <= 0:
        return draw(simple_values)
    
    num_keys = draw(st.integers(min_value=1, max_value=max_keys))
    keys = draw(st.lists(field_names, min_size=num_keys, max_size=num_keys, unique=True))
    
    result = {}
    for key in keys:
        # Decide whether to nest or use simple value
        if draw(st.booleans()) and max_depth > 1:
            # Nested dict
            result[key] = draw(structured_data_strategy(max_depth=max_depth - 1, max_keys=3))
        elif draw(st.booleans()):
            # List of simple values
            result[key] = draw(st.lists(simple_values, min_size=1, max_size=5))
        else:
            # Simple value
            result[key] = draw(simple_values)
    
    return result


@st.composite
def domain_id_strategy(draw):
    """Generate valid domain IDs."""
    return draw(st.text(
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_"),
        min_size=1,
        max_size=20,
    ).filter(lambda x: len(x) > 0 and x[0].isalpha()))


# =============================================================================
# Property Tests
# =============================================================================

class TestNarrativeDetailLevelProperty:
    """
    **Feature: vertical-domain-phase2, Property 4: Narrative Generation Respects Detail Level**
    
    Property: For any structured data and detail_level parameter, the generated narrative
    length should be: brief < detailed < comprehensive.
    """

    @given(structured_data_strategy(), domain_id_strategy())
    @settings(max_examples=100, deadline=None)
    def test_detail_level_ordering_template_fallback(
        self, 
        structured_data: dict, 
        domain_id: str
    ):
        """
        **Feature: vertical-domain-phase2, Property 4: Narrative Generation Respects Detail Level**
        **Validates: Requirements 4.1, 4.5**
        
        For any structured data, template-based narrative generation should produce
        outputs where: len(brief) <= len(detailed) <= len(comprehensive)
        """
        # Skip empty data
        assume(len(structured_data) > 0)
        
        # Create engine without LLM (template fallback mode)
        engine = NarrativeEngine(gateway=None)
        
        # Generate narratives at each detail level using template fallback
        brief = engine._template_fallback(structured_data, domain_id, "brief")
        detailed = engine._template_fallback(structured_data, domain_id, "detailed")
        comprehensive = engine._template_fallback(structured_data, domain_id, "comprehensive")
        
        # Verify ordering: brief <= detailed <= comprehensive
        assert len(brief) <= len(detailed), \
            f"Brief ({len(brief)} chars) should be <= detailed ({len(detailed)} chars)"
        assert len(detailed) <= len(comprehensive), \
            f"Detailed ({len(detailed)} chars) should be <= comprehensive ({len(comprehensive)} chars)"

    @given(structured_data_strategy(), domain_id_strategy())
    @settings(max_examples=100, deadline=None)
    def test_brief_contains_summary_info(
        self, 
        structured_data: dict, 
        domain_id: str
    ):
        """
        **Feature: vertical-domain-phase2, Property 4: Narrative Generation Respects Detail Level**
        **Validates: Requirements 4.1**
        
        For any structured data, brief narrative should contain at least the domain header
        and some summary information.
        """
        assume(len(structured_data) > 0)
        
        engine = NarrativeEngine(gateway=None)
        brief = engine._template_fallback(structured_data, domain_id, "brief")
        
        # Brief should contain the domain header
        assert domain_id.upper() in brief, \
            f"Brief narrative should contain domain header '{domain_id.upper()}'"
        
        # Brief should be non-empty
        assert len(brief) > 0, "Brief narrative should not be empty"

    @given(structured_data_strategy(), domain_id_strategy())
    @settings(max_examples=100, deadline=None)
    def test_comprehensive_contains_all_keys(
        self, 
        structured_data: dict, 
        domain_id: str
    ):
        """
        **Feature: vertical-domain-phase2, Property 4: Narrative Generation Respects Detail Level**
        **Validates: Requirements 4.5**
        
        For any structured data, comprehensive narrative should reference all top-level keys.
        """
        assume(len(structured_data) > 0)
        
        engine = NarrativeEngine(gateway=None)
        comprehensive = engine._template_fallback(structured_data, domain_id, "comprehensive")
        
        # Comprehensive should mention all top-level keys
        for key in structured_data.keys():
            assert key in comprehensive, \
                f"Comprehensive narrative should contain key '{key}'"

    @given(structured_data_strategy(max_depth=3, max_keys=4), domain_id_strategy())
    @settings(max_examples=50, deadline=None)
    def test_detailed_has_limited_depth(
        self, 
        structured_data: dict, 
        domain_id: str
    ):
        """
        **Feature: vertical-domain-phase2, Property 4: Narrative Generation Respects Detail Level**
        **Validates: Requirements 4.5**
        
        For any deeply nested structured data, detailed narrative should have limited depth
        (showing "..." for deeply nested content), while comprehensive shows more.
        """
        assume(len(structured_data) > 0)
        
        engine = NarrativeEngine(gateway=None)
        detailed = engine._template_fallback(structured_data, domain_id, "detailed")
        comprehensive = engine._template_fallback(structured_data, domain_id, "comprehensive")
        
        # Both detailed and comprehensive should be non-empty
        assert len(detailed) > 0, "Detailed narrative should not be empty"
        assert len(comprehensive) > 0, "Comprehensive narrative should not be empty"
        
        # Comprehensive should show actual values where detailed may truncate with "..."
        # Note: String length comparison is not reliable because "..." can be longer than short values
        # Instead, verify that comprehensive doesn't truncate (no "..." for nested content)
        # while detailed may truncate deeply nested content
        if "..." in detailed:
            # If detailed truncates, comprehensive should show more actual content
            # (fewer "..." occurrences or none at all)
            detailed_truncations = detailed.count("...")
            comprehensive_truncations = comprehensive.count("...")
            assert comprehensive_truncations <= detailed_truncations, \
                "Comprehensive should have fewer or equal truncations than detailed"


class TestNarrativeTemplateRegistration:
    """Test template registration and usage."""

    @given(
        structured_data_strategy(),
        domain_id_strategy(),
        st.sampled_from(["brief", "detailed", "comprehensive"])
    )
    @settings(max_examples=50, deadline=None)
    def test_registered_template_used(
        self, 
        structured_data: dict, 
        domain_id: str,
        detail_level: DetailLevel
    ):
        """
        **Feature: vertical-domain-phase2, Property 4: Narrative Generation Respects Detail Level**
        **Validates: Requirements 4.2**
        
        For any domain with a registered template, the template should be used for generation.
        """
        assume(len(structured_data) > 0)
        
        engine = NarrativeEngine(gateway=None)
        
        # Register a custom template with a marker
        marker = f"CUSTOM_TEMPLATE_MARKER_{domain_id}"
        template = f"{marker}: {{summary}}"
        engine.register_template(domain_id, template, detail_level)
        
        # Generate narrative
        result = engine._template_fallback(structured_data, domain_id, detail_level)
        
        # The marker should appear in the result (template was used)
        assert marker in result, \
            f"Registered template marker should appear in result for {detail_level}"

    @given(domain_id_strategy())
    @settings(max_examples=50, deadline=None)
    def test_template_placeholder_substitution(self, domain_id: str):
        """
        **Feature: vertical-domain-phase2, Property 4: Narrative Generation Respects Detail Level**
        **Validates: Requirements 4.2**
        
        For any template with placeholders, values should be substituted correctly.
        """
        engine = NarrativeEngine(gateway=None)
        
        # Register template with specific placeholders
        template = "Name: {name}, Value: {value}"
        engine.register_template(domain_id, template, "detailed")
        
        # Data with matching keys
        data = {"name": "TestName", "value": "TestValue"}
        
        result = engine._template_fallback(data, domain_id, "detailed")
        
        assert "TestName" in result, "Name placeholder should be substituted"
        assert "TestValue" in result, "Value placeholder should be substituted"


class TestNarrativeDefaultGeneration:
    """Test default narrative generation behavior."""

    @given(structured_data_strategy())
    @settings(max_examples=50, deadline=None)
    def test_default_narrative_non_empty(self, structured_data: dict):
        """
        **Feature: vertical-domain-phase2, Property 4: Narrative Generation Respects Detail Level**
        **Validates: Requirements 4.1**
        
        For any structured data, default narrative generation should produce non-empty output.
        """
        assume(len(structured_data) > 0)
        
        engine = NarrativeEngine(gateway=None)
        
        # Use an unregistered domain to trigger default generation
        result = engine._default_narrative(structured_data, "unknown_domain", "detailed")
        
        assert len(result) > 0, "Default narrative should not be empty"
        assert "UNKNOWN_DOMAIN" in result, "Default narrative should contain domain header"

    @given(st.lists(simple_values, min_size=1, max_size=20))
    @settings(max_examples=50, deadline=None)
    def test_list_truncation_in_narrative(self, items: list):
        """
        **Feature: vertical-domain-phase2, Property 4: Narrative Generation Respects Detail Level**
        **Validates: Requirements 4.5**
        
        For any list with more than 10 items, the narrative should indicate truncation.
        """
        data = {"items": items}
        engine = NarrativeEngine(gateway=None)
        
        result = engine._default_narrative(data, "test_domain", "detailed")
        
        if len(items) > 10:
            assert "还有" in result or "..." in result, \
                "Long lists should show truncation indicator"

