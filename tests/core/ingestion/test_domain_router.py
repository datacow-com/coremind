"""
Test suite for core.ingestion.nodes.domain_router module.

Tests domain routing logic including:
- Domain detection and routing
- Interpretation result storage
- Fallback to standard processing
- Error handling and resilience
- Multi-tenant isolation

**Validates: Requirements 1.2, 1.4, 8.1, 8.2, 8.3, 8.5**
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Any, Dict

from core.ingestion.nodes.domain_router import (
    DomainRouterNode,
    route_after_domain,
    should_skip_domain_router,
)
from core.domains.registry import get_domain_registry, reset_domain_registry
from core.domains.base_interpreter import BaseDomainInterpreter, InterpretationResult
from core.domains.ontology_schema import OntologySchema
from core.domains.exceptions import DomainInterpretationError


class MockInterpreter(BaseDomainInterpreter):
    """Mock interpreter for testing."""
    
    domain_id = "mock_domain"
    requires_gpu = False
    recommended_vram_mb = 0
    
    def __init__(self, result: InterpretationResult | None = None, error: Exception | None = None):
        super().__init__()
        self._result = result or InterpretationResult(
            domain_id="mock_domain",
            structured_data={"test": "data"},
            narrative="Test narrative",
            confidence=0.9,
        )
        self._error = error
    
    async def interpret(self, document: dict, config: dict | None = None) -> InterpretationResult:
        if self._error:
            raise self._error
        return self._result
    
    def get_ontology(self) -> OntologySchema:
        return OntologySchema(domain_id=self.domain_id)
    
    def validate_output(self, result: InterpretationResult) -> tuple[bool, list[str]]:
        return True, []


@pytest.fixture
def sample_ingest_state() -> Dict[str, Any]:
    """Sample IngestState for testing."""
    return {
        "channel_id": "test_channel",
        "task_id": "task_001",
        "file_path": "test.pdf",
        "file_type": "pdf",
        "batch_id": "batch_001",
        "kb_name": "test_kb",
        "version": 1,
        "strategy_config": {
            "enable_domain_interpretation": True,
        },
        "capability_loader": None,
        "raw_content": b"test content",
        "extracted_text": "Test extracted text",
        "parsed_blocks": [],
        "images": [],
        "chunks": [],
        "vectors": [],
        "processing_stage": "parse",
        "retry_count": 0,
        "error_log": [],
        "progress": {},
        "quality_metrics": {},
    }


@pytest.fixture(autouse=True)
def reset_registry_fixture():
    """Reset registry before and after each test."""
    reset_domain_registry()
    yield
    reset_domain_registry()


class TestDomainRouterNode:
    """Test DomainRouterNode class."""
    
    @pytest.mark.asyncio
    async def test_router_node_no_domain_detected(self, sample_ingest_state):
        """P1: Test router returns state unchanged when no domain detected."""
        router = DomainRouterNode()
        
        result = await router(sample_ingest_state)
        
        assert result is not None
        # No interpretation should be added
        assert not any(
            b.get("type") == "domain_interpretation"
            for b in result.get("parsed_blocks", [])
        )
    
    @pytest.mark.asyncio
    async def test_router_node_domain_interpretation_disabled(self, sample_ingest_state):
        """P1: Test router skips when domain interpretation is disabled."""
        sample_ingest_state["strategy_config"]["enable_domain_interpretation"] = False
        
        # Register a domain that would match
        registry = get_domain_registry()
        registry.register("mock_domain", MockInterpreter, detection_patterns=[".*"])
        
        router = DomainRouterNode()
        result = await router(sample_ingest_state)
        
        assert result is not None
        # No interpretation should be added
        assert not any(
            b.get("type") == "domain_interpretation"
            for b in result.get("parsed_blocks", [])
        )
    
    @pytest.mark.asyncio
    async def test_router_node_successful_interpretation(self, sample_ingest_state):
        """P1: Test router stores interpretation result on success."""
        # Register mock interpreter
        registry = get_domain_registry()
        registry.register("mock_domain", MockInterpreter, detection_patterns=[".*"])
        sample_ingest_state["strategy_config"]["domain"] = "mock_domain"
        
        router = DomainRouterNode()
        result = await router(sample_ingest_state)
        
        assert result is not None
        
        # Check interpretation was stored
        parsed_blocks = result.get("parsed_blocks", [])
        interpretation_blocks = [
            b for b in parsed_blocks
            if b.get("type") == "domain_interpretation"
        ]
        assert len(interpretation_blocks) == 1
        
        interp = interpretation_blocks[0]
        assert interp["domain_id"] == "mock_domain"
        assert interp["confidence"] == 0.9
        assert interp["content"] == "Test narrative"
        assert interp["structured_data"] == {"test": "data"}
    
    @pytest.mark.asyncio
    async def test_router_node_interpretation_error_fallback(self, sample_ingest_state):
        """P1: Test router continues on interpretation error (Requirements 8.5)."""
        # Register failing interpreter
        class FailingInterpreter(MockInterpreter):
            domain_id = "failing_domain"
            
            async def interpret(self, document, config=None):
                raise DomainInterpretationError(
                    "Test error",
                    domain_id=self.domain_id,
                    stage="interpret",
                    details={"test": True}
                )
        
        registry = get_domain_registry()
        registry.register("failing_domain", FailingInterpreter, detection_patterns=[".*"])
        sample_ingest_state["strategy_config"]["domain"] = "failing_domain"
        
        router = DomainRouterNode()
        result = await router(sample_ingest_state)
        
        # Should not raise, should return state
        assert result is not None
        
        # Error should be logged
        error_log = result.get("error_log", [])
        assert len(error_log) > 0
        assert any(e.get("stage") == "domain_router" for e in error_log)
    
    @pytest.mark.asyncio
    async def test_router_node_unexpected_error_fallback(self, sample_ingest_state):
        """P1: Test router continues on unexpected error (Requirements 8.5)."""
        # Register interpreter that raises unexpected error
        class UnexpectedErrorInterpreter(MockInterpreter):
            domain_id = "unexpected_error_domain"
            
            async def interpret(self, document, config=None):
                raise RuntimeError("Unexpected error")
        
        registry = get_domain_registry()
        registry.register(
            "unexpected_error_domain",
            UnexpectedErrorInterpreter,
            detection_patterns=[".*"]
        )
        sample_ingest_state["strategy_config"]["domain"] = "unexpected_error_domain"
        
        router = DomainRouterNode()
        result = await router(sample_ingest_state)
        
        # Should not raise
        assert result is not None
        
        # Error should be logged
        error_log = result.get("error_log", [])
        assert len(error_log) > 0
    
    @pytest.mark.asyncio
    async def test_router_node_interpreter_not_found(self, sample_ingest_state):
        """P1: Test router handles missing interpreter gracefully."""
        sample_ingest_state["strategy_config"]["domain"] = "nonexistent_domain"
        
        router = DomainRouterNode()
        result = await router(sample_ingest_state)
        
        # Should not raise
        assert result is not None
        
        # No interpretation should be added
        assert not any(
            b.get("type") == "domain_interpretation"
            for b in result.get("parsed_blocks", [])
        )
    
    @pytest.mark.asyncio
    async def test_router_node_narrative_appended_to_text(self, sample_ingest_state):
        """P1: Test narrative is appended to extracted_text (Requirements 8.2)."""
        registry = get_domain_registry()
        registry.register("mock_domain", MockInterpreter, detection_patterns=[".*"])
        sample_ingest_state["strategy_config"]["domain"] = "mock_domain"
        sample_ingest_state["extracted_text"] = "Original text"
        
        router = DomainRouterNode()
        result = await router(sample_ingest_state)
        
        extracted_text = result.get("extracted_text", "")
        assert "Original text" in extracted_text
        assert "Test narrative" in extracted_text
        assert "Domain Interpretation" in extracted_text
    
    @pytest.mark.asyncio
    async def test_router_node_quality_metrics_updated(self, sample_ingest_state):
        """P1: Test quality metrics are updated with interpretation confidence."""
        registry = get_domain_registry()
        registry.register("mock_domain", MockInterpreter, detection_patterns=[".*"])
        sample_ingest_state["strategy_config"]["domain"] = "mock_domain"
        
        router = DomainRouterNode()
        result = await router(sample_ingest_state)
        
        quality_metrics = result.get("quality_metrics", {})
        assert quality_metrics.get("domain_interpretation_confidence") == 0.9
        assert quality_metrics.get("domain_id") == "mock_domain"


class TestRouteAfterDomain:
    """Test route_after_domain function."""
    
    def test_route_after_domain_with_interpretation(self, sample_ingest_state):
        """P1: Test routing when interpretation exists."""
        sample_ingest_state["parsed_blocks"] = [
            {"type": "domain_interpretation", "domain_id": "test"}
        ]
        
        result = route_after_domain(sample_ingest_state)
        
        assert result == "chunker"
    
    def test_route_after_domain_without_interpretation(self, sample_ingest_state):
        """P1: Test routing when no interpretation exists."""
        sample_ingest_state["parsed_blocks"] = [
            {"type": "text", "content": "test"}
        ]
        
        result = route_after_domain(sample_ingest_state)
        
        assert result == "chunker"
    
    def test_route_after_domain_empty_blocks(self, sample_ingest_state):
        """P1: Test routing with empty parsed_blocks."""
        sample_ingest_state["parsed_blocks"] = []
        
        result = route_after_domain(sample_ingest_state)
        
        assert result == "chunker"


class TestShouldSkipDomainRouter:
    """Test should_skip_domain_router function."""
    
    def test_skip_when_disabled(self, sample_ingest_state):
        """P1: Test skip when domain interpretation is disabled."""
        sample_ingest_state["strategy_config"]["enable_domain_interpretation"] = False
        
        result = should_skip_domain_router(sample_ingest_state)
        
        assert result is True
    
    def test_not_skip_when_enabled(self, sample_ingest_state):
        """P1: Test not skip when domain interpretation is enabled."""
        sample_ingest_state["strategy_config"]["enable_domain_interpretation"] = True
        
        result = should_skip_domain_router(sample_ingest_state)
        
        assert result is False
    
    def test_not_skip_when_default(self, sample_ingest_state):
        """P1: Test not skip when enable_domain_interpretation not set (default True)."""
        del sample_ingest_state["strategy_config"]["enable_domain_interpretation"]
        
        result = should_skip_domain_router(sample_ingest_state)
        
        assert result is False


class TestMultiTenantIsolation:
    """Test multi-tenant isolation in domain routing."""
    
    @pytest.mark.asyncio
    async def test_routing_tenant_isolation(self):
        """P0: Test routing doesn't leak data between tenants."""
        # Register interpreter
        registry = get_domain_registry()
        registry.register("mock_domain", MockInterpreter, detection_patterns=[".*"])
        
        tenant_a_state = {
            "channel_id": "tenant_a",
            "file_path": "tenant_a.pdf",
            "file_type": "pdf",
            "strategy_config": {"domain": "mock_domain"},
            "extracted_text": "Tenant A content",
            "parsed_blocks": [],
            "error_log": [],
            "quality_metrics": {},
        }
        
        tenant_b_state = {
            "channel_id": "tenant_b",
            "file_path": "tenant_b.pdf",
            "file_type": "pdf",
            "strategy_config": {"enable_domain_interpretation": False},
            "extracted_text": "Tenant B content",
            "parsed_blocks": [],
            "error_log": [],
            "quality_metrics": {},
        }
        
        router = DomainRouterNode()
        
        result_a = await router(tenant_a_state)
        result_b = await router(tenant_b_state)
        
        # Tenant A should have interpretation
        assert any(
            b.get("type") == "domain_interpretation"
            for b in result_a.get("parsed_blocks", [])
        )
        
        # Tenant B should not have interpretation
        assert not any(
            b.get("type") == "domain_interpretation"
            for b in result_b.get("parsed_blocks", [])
        )
        
        # Verify states are isolated
        assert result_a["channel_id"] != result_b["channel_id"]


class TestDomainDetection:
    """Test domain detection logic."""
    
    @pytest.mark.asyncio
    async def test_explicit_domain_in_config(self, sample_ingest_state):
        """P1: Test explicit domain in strategy_config is used."""
        registry = get_domain_registry()
        registry.register("explicit_domain", MockInterpreter)
        
        sample_ingest_state["strategy_config"]["domain"] = "explicit_domain"
        
        router = DomainRouterNode()
        result = await router(sample_ingest_state)
        
        # Should use explicit domain
        parsed_blocks = result.get("parsed_blocks", [])
        interpretation_blocks = [
            b for b in parsed_blocks
            if b.get("type") == "domain_interpretation"
        ]
        assert len(interpretation_blocks) == 1
    
    @pytest.mark.asyncio
    async def test_pattern_based_detection(self, sample_ingest_state):
        """P1: Test pattern-based domain detection."""
        registry = get_domain_registry()
        registry.register(
            "pattern_domain",
            MockInterpreter,
            detection_patterns=["test.*content"]
        )
        
        sample_ingest_state["extracted_text"] = "This is test content for detection"
        
        router = DomainRouterNode()
        result = await router(sample_ingest_state)
        
        # Should detect domain via pattern
        parsed_blocks = result.get("parsed_blocks", [])
        interpretation_blocks = [
            b for b in parsed_blocks
            if b.get("type") == "domain_interpretation"
        ]
        assert len(interpretation_blocks) == 1


class TestErrorLogPreservation:
    """Test error log preservation."""
    
    @pytest.mark.asyncio
    async def test_existing_errors_preserved(self, sample_ingest_state):
        """P1: Test existing errors are preserved when new error occurs."""
        # Add existing error
        sample_ingest_state["error_log"] = [
            {"stage": "previous", "error": "Previous error"}
        ]
        
        # Register failing interpreter
        class FailingInterpreter(MockInterpreter):
            domain_id = "failing"
            
            async def interpret(self, document, config=None):
                raise DomainInterpretationError(
                    "New error",
                    domain_id=self.domain_id,
                    stage="interpret"
                )
        
        registry = get_domain_registry()
        registry.register("failing", FailingInterpreter, detection_patterns=[".*"])
        sample_ingest_state["strategy_config"]["domain"] = "failing"
        
        router = DomainRouterNode()
        result = await router(sample_ingest_state)
        
        error_log = result.get("error_log", [])
        
        # Both errors should be present
        assert len(error_log) >= 2
        assert any(e.get("stage") == "previous" for e in error_log)
        assert any(e.get("stage") == "domain_router" for e in error_log)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_empty_state(self):
        """P1: Test router handles minimal state."""
        state = {
            "strategy_config": {},
            "parsed_blocks": [],
            "error_log": [],
        }
        
        router = DomainRouterNode()
        result = await router(state)
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_missing_strategy_config(self):
        """P1: Test router handles missing strategy_config."""
        state = {
            "file_path": "test.pdf",
            "parsed_blocks": [],
            "error_log": [],
        }
        
        router = DomainRouterNode()
        result = await router(state)
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_unicode_content(self, sample_ingest_state):
        """P1: Test router handles unicode content."""
        registry = get_domain_registry()
        
        # Create interpreter with unicode result
        class UnicodeInterpreter(MockInterpreter):
            domain_id = "unicode_domain"
            
            async def interpret(self, document, config=None):
                return InterpretationResult(
                    domain_id=self.domain_id,
                    structured_data={"八字": "甲子年"},
                    narrative="这是一份命理分析报告",
                    confidence=0.85,
                )
        
        registry.register("unicode_domain", UnicodeInterpreter, detection_patterns=[".*"])
        sample_ingest_state["strategy_config"]["domain"] = "unicode_domain"
        
        router = DomainRouterNode()
        result = await router(sample_ingest_state)
        
        parsed_blocks = result.get("parsed_blocks", [])
        interpretation_blocks = [
            b for b in parsed_blocks
            if b.get("type") == "domain_interpretation"
        ]
        
        assert len(interpretation_blocks) == 1
        assert interpretation_blocks[0]["structured_data"]["八字"] == "甲子年"
        assert "命理" in interpretation_blocks[0]["content"]
    
    @pytest.mark.asyncio
    async def test_empty_narrative(self, sample_ingest_state):
        """P1: Test router handles empty narrative."""
        registry = get_domain_registry()
        
        class EmptyNarrativeInterpreter(MockInterpreter):
            domain_id = "empty_narrative"
            
            async def interpret(self, document, config=None):
                return InterpretationResult(
                    domain_id=self.domain_id,
                    structured_data={"key": "value"},
                    narrative="",
                    confidence=0.7,
                )
        
        registry.register("empty_narrative", EmptyNarrativeInterpreter, detection_patterns=[".*"])
        sample_ingest_state["strategy_config"]["domain"] = "empty_narrative"
        
        router = DomainRouterNode()
        result = await router(sample_ingest_state)
        
        # Should still work with empty narrative
        assert result is not None
        parsed_blocks = result.get("parsed_blocks", [])
        assert any(b.get("type") == "domain_interpretation" for b in parsed_blocks)
