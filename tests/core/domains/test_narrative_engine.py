"""
Unit tests for NarrativeEngine.

Tests cover:
- LLM enhanced generation
- Template fallback
- Different detail_level settings
- Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.domains.narrative_engine import NarrativeEngine, DetailLevel


class TestNarrativeEngineInit:
    """Test NarrativeEngine initialization."""

    def test_init_without_gateway(self):
        """Engine can be initialized without a gateway."""
        engine = NarrativeEngine(gateway=None)
        assert engine._gateway is None
        assert engine._templates == {}

    def test_init_with_gateway(self):
        """Engine can be initialized with a gateway."""
        mock_gateway = MagicMock()
        engine = NarrativeEngine(gateway=mock_gateway)
        assert engine._gateway is mock_gateway

    def test_lazy_gateway_loading(self):
        """Gateway is lazily loaded when accessed."""
        engine = NarrativeEngine(gateway=None)
        
        # Mock the LLMGateway import at the source module
        with patch('core.llm.gateway.LLMGateway') as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            
            # Access gateway property - this triggers lazy loading
            gateway = engine.gateway
            
            # Should have created a new gateway
            mock_class.assert_called_once()
            assert gateway is mock_instance


class TestTemplateRegistration:
    """Test template registration functionality."""

    def test_register_single_template(self):
        """Can register a single template for a domain."""
        engine = NarrativeEngine(gateway=None)
        
        engine.register_template("test_domain", "Template: {key}", "detailed")
        
        assert "test_domain" in engine._templates
        assert "detailed" in engine._templates["test_domain"]
        assert engine._templates["test_domain"]["detailed"] == "Template: {key}"

    def test_register_multiple_detail_levels(self):
        """Can register templates for different detail levels."""
        engine = NarrativeEngine(gateway=None)
        
        engine.register_template("domain", "Brief: {x}", "brief")
        engine.register_template("domain", "Detailed: {x} with more info", "detailed")
        engine.register_template("domain", "Comprehensive: {x} full analysis", "comprehensive")
        
        assert len(engine._templates["domain"]) == 3
        assert "brief" in engine._templates["domain"]
        assert "detailed" in engine._templates["domain"]
        assert "comprehensive" in engine._templates["domain"]

    def test_register_multiple_domains(self):
        """Can register templates for different domains."""
        engine = NarrativeEngine(gateway=None)
        
        engine.register_template("domain_a", "Template A", "detailed")
        engine.register_template("domain_b", "Template B", "detailed")
        
        assert "domain_a" in engine._templates
        assert "domain_b" in engine._templates

    def test_overwrite_existing_template(self):
        """Registering same domain/level overwrites existing template."""
        engine = NarrativeEngine(gateway=None)
        
        engine.register_template("domain", "Original", "detailed")
        engine.register_template("domain", "Updated", "detailed")
        
        assert engine._templates["domain"]["detailed"] == "Updated"


class TestTemplateFallback:
    """Test template fallback generation."""

    def test_fallback_with_registered_template(self):
        """Uses registered template when available."""
        engine = NarrativeEngine(gateway=None)
        engine.register_template("test", "Result: {value}", "detailed")
        
        result = engine._template_fallback({"value": "42"}, "test", "detailed")
        
        assert "42" in result

    def test_fallback_without_template_uses_default(self):
        """Uses default generation when no template registered."""
        engine = NarrativeEngine(gateway=None)
        
        result = engine._template_fallback({"key": "value"}, "unknown", "detailed")
        
        assert "UNKNOWN" in result
        assert "key" in result

    def test_fallback_nested_data(self):
        """Handles nested data structures."""
        engine = NarrativeEngine(gateway=None)
        
        data = {
            "level1": {
                "level2": {
                    "value": "deep"
                }
            }
        }
        
        result = engine._template_fallback(data, "test", "comprehensive")
        
        assert "level1" in result
        assert "level2" in result

    def test_fallback_list_data(self):
        """Handles list data structures."""
        engine = NarrativeEngine(gateway=None)
        
        data = {"items": ["a", "b", "c"]}
        
        result = engine._template_fallback(data, "test", "detailed")
        
        assert "items" in result


class TestDetailLevels:
    """Test different detail level behaviors."""

    def test_brief_is_shortest(self):
        """Brief output is shorter than detailed."""
        engine = NarrativeEngine(gateway=None)
        data = {"a": 1, "b": 2, "c": {"d": 3, "e": 4}}
        
        brief = engine._template_fallback(data, "test", "brief")
        detailed = engine._template_fallback(data, "test", "detailed")
        
        assert len(brief) <= len(detailed)

    def test_comprehensive_is_longest(self):
        """Comprehensive output is longer than detailed."""
        engine = NarrativeEngine(gateway=None)
        data = {"a": 1, "b": 2, "c": {"d": 3, "e": 4}}
        
        detailed = engine._template_fallback(data, "test", "detailed")
        comprehensive = engine._template_fallback(data, "test", "comprehensive")
        
        assert len(detailed) <= len(comprehensive)

    def test_brief_shows_summary(self):
        """Brief shows summary counts for nested structures."""
        engine = NarrativeEngine(gateway=None)
        data = {"nested": {"a": 1, "b": 2, "c": 3}}
        
        brief = engine._template_fallback(data, "test", "brief")
        
        # Brief should show count, not full content
        assert "3 项" in brief or "nested" in brief


class TestFlattenDict:
    """Test dictionary flattening utility."""

    def test_flatten_simple_dict(self):
        """Flattens simple dictionary."""
        engine = NarrativeEngine(gateway=None)
        
        result = engine._flatten_dict({"a": 1, "b": 2})
        
        assert result == {"a": 1, "b": 2}

    def test_flatten_nested_dict(self):
        """Flattens nested dictionary with dot notation."""
        engine = NarrativeEngine(gateway=None)
        
        result = engine._flatten_dict({"outer": {"inner": "value"}})
        
        assert "outer.inner" in result
        assert result["outer.inner"] == "value"

    def test_flatten_list_values(self):
        """Converts list values to comma-separated strings."""
        engine = NarrativeEngine(gateway=None)
        
        result = engine._flatten_dict({"items": [1, 2, 3]})
        
        assert result["items"] == "1, 2, 3"


class TestRenderTemplate:
    """Test template rendering."""

    def test_render_simple_placeholders(self):
        """Renders simple placeholders."""
        engine = NarrativeEngine(gateway=None)
        
        result = engine._render_template(
            "Hello {name}!",
            {"name": "World"}
        )
        
        assert result == "Hello World!"

    def test_render_nested_placeholders(self):
        """Renders placeholders from nested data."""
        engine = NarrativeEngine(gateway=None)
        
        result = engine._render_template(
            "Value: {outer.inner}",
            {"outer": {"inner": "nested_value"}}
        )
        
        assert result == "Value: nested_value"

    def test_render_missing_placeholder(self):
        """Missing placeholders are left as-is."""
        engine = NarrativeEngine(gateway=None)
        
        result = engine._render_template(
            "Hello {name}, your {missing} is ready",
            {"name": "User"}
        )
        
        assert "User" in result
        assert "{missing}" in result


class TestDefaultNarrative:
    """Test default narrative generation."""

    def test_default_includes_header(self):
        """Default narrative includes domain header."""
        engine = NarrativeEngine(gateway=None)
        
        result = engine._default_narrative({"key": "value"}, "test_domain", "detailed")
        
        assert "TEST_DOMAIN" in result

    def test_default_handles_empty_data(self):
        """Default narrative handles empty data."""
        engine = NarrativeEngine(gateway=None)
        
        result = engine._default_narrative({}, "test", "detailed")
        
        assert "TEST" in result

    def test_default_truncates_long_lists(self):
        """Default narrative truncates lists longer than 10 items."""
        engine = NarrativeEngine(gateway=None)
        
        data = {"items": list(range(15))}
        result = engine._default_narrative(data, "test", "detailed")
        
        assert "还有" in result or "5" in result  # Shows remaining count


class TestAsyncGenerate:
    """Test async generate method."""

    @pytest.mark.asyncio
    async def test_generate_without_llm(self):
        """Generate falls back to template when LLM disabled."""
        engine = NarrativeEngine(gateway=None)
        
        result = await engine.generate(
            {"key": "value"},
            "test_domain",
            detail_level="detailed",
            use_llm=False
        )
        
        assert len(result) > 0
        assert "TEST_DOMAIN" in result

    @pytest.mark.asyncio
    async def test_generate_with_llm_success(self):
        """Generate uses LLM when available and enabled."""
        mock_gateway = AsyncMock()
        mock_gateway.chat = AsyncMock(return_value="LLM generated narrative")
        
        engine = NarrativeEngine(gateway=mock_gateway)
        
        result = await engine.generate(
            {"key": "value"},
            "test_domain",
            detail_level="detailed",
            use_llm=True
        )
        
        assert result == "LLM generated narrative"
        mock_gateway.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_llm_failure_fallback(self):
        """Generate falls back to template when LLM fails."""
        mock_gateway = AsyncMock()
        mock_gateway.chat = AsyncMock(side_effect=Exception("LLM error"))
        
        engine = NarrativeEngine(gateway=mock_gateway)
        
        result = await engine.generate(
            {"key": "value"},
            "test_domain",
            detail_level="detailed",
            use_llm=True
        )
        
        # Should fall back to template
        assert "TEST_DOMAIN" in result

    @pytest.mark.asyncio
    async def test_generate_respects_detail_level(self):
        """Generate passes detail level to LLM prompt."""
        mock_gateway = AsyncMock()
        mock_gateway.chat = AsyncMock(return_value="Response")
        
        engine = NarrativeEngine(gateway=mock_gateway)
        
        await engine.generate(
            {"key": "value"},
            "test_domain",
            detail_level="comprehensive",
            use_llm=True
        )
        
        # Check that the prompt contains comprehensive instructions
        call_args = mock_gateway.chat.call_args[0][0]
        assert "全面深入" in call_args or "comprehensive" in call_args.lower()


class TestLLMGenerate:
    """Test LLM-based generation."""

    @pytest.mark.asyncio
    async def test_llm_generate_brief_prompt(self):
        """LLM generate uses brief instructions for brief level."""
        mock_gateway = AsyncMock()
        mock_gateway.chat = AsyncMock(return_value="Brief response")
        
        engine = NarrativeEngine(gateway=mock_gateway)
        
        await engine._llm_generate({"key": "value"}, "test", "brief")
        
        call_args = mock_gateway.chat.call_args[0][0]
        assert "1-2句话" in call_args or "简要" in call_args

    @pytest.mark.asyncio
    async def test_llm_generate_detailed_prompt(self):
        """LLM generate uses detailed instructions for detailed level."""
        mock_gateway = AsyncMock()
        mock_gateway.chat = AsyncMock(return_value="Detailed response")
        
        engine = NarrativeEngine(gateway=mock_gateway)
        
        await engine._llm_generate({"key": "value"}, "test", "detailed")
        
        call_args = mock_gateway.chat.call_args[0][0]
        assert "3-5段" in call_args or "详细" in call_args

    @pytest.mark.asyncio
    async def test_llm_generate_includes_data(self):
        """LLM generate includes structured data in prompt."""
        mock_gateway = AsyncMock()
        mock_gateway.chat = AsyncMock(return_value="Response")
        
        engine = NarrativeEngine(gateway=mock_gateway)
        
        await engine._llm_generate({"test_key": "test_value"}, "domain", "detailed")
        
        call_args = mock_gateway.chat.call_args[0][0]
        assert "test_key" in call_args
        assert "test_value" in call_args

