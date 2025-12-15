"""
Property-based tests for Pipeline Integration Resilience

**Feature: vertical-domain-phase2, Property 7: Pipeline Integration Resilience**
**Validates: Requirements 8.5**

For any document where domain interpretation fails, the ingestion pipeline should
continue with standard processing and not raise an exception to the caller.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Any
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

from core.domains.base_interpreter import BaseDomainInterpreter, InterpretationResult
from core.domains.ontology_schema import OntologySchema
from core.domains.registry import DomainRegistry, get_domain_registry, reset_domain_registry
from core.domains.exceptions import DomainInterpretationError
from core.ingestion.nodes.domain_router import DomainRouterNode


# Strategies for property tests
file_paths = st.text(
    min_size=1,
    max_size=100,
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_-./")
)

file_types = st.sampled_from(["pdf", "jpg", "png", "docx", "txt", "html"])

domain_ids = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_")
)

error_messages = st.text(min_size=1, max_size=200)

content_texts = st.text(min_size=0, max_size=1000)


class FailingInterpreter(BaseDomainInterpreter):
    """An interpreter that always fails with a specific error."""
    
    domain_id = "failing_domain"
    requires_gpu = False
    recommended_vram_mb = 0
    
    def __init__(self, error_type: str = "domain", error_message: str = "Test error"):
        super().__init__()
        self._error_type = error_type
        self._error_message = error_message
    
    async def interpret(self, document: dict, config: dict | None = None) -> InterpretationResult:
        if self._error_type == "domain":
            raise DomainInterpretationError(
                self._error_message,
                domain_id=self.domain_id,
                stage="interpret",
                details={"test": True}
            )
        elif self._error_type == "runtime":
            raise RuntimeError(self._error_message)
        elif self._error_type == "value":
            raise ValueError(self._error_message)
        else:
            raise Exception(self._error_message)
    
    def get_ontology(self) -> OntologySchema:
        return OntologySchema(domain_id=self.domain_id)
    
    def validate_output(self, result: InterpretationResult) -> tuple[bool, list[str]]:
        return True, []


class SuccessfulInterpreter(BaseDomainInterpreter):
    """An interpreter that always succeeds."""
    
    domain_id = "successful_domain"
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


def create_test_state(
    file_path: str = "test.pdf",
    file_type: str = "pdf",
    content: str = "",
    domain: str | None = None,
    enable_domain_interpretation: bool = True
) -> dict:
    """Create a test IngestState dictionary."""
    strategy_config = {
        "enable_domain_interpretation": enable_domain_interpretation,
    }
    if domain:
        strategy_config["domain"] = domain
    
    return {
        "channel_id": "test_channel",
        "task_id": "test_task",
        "file_path": file_path,
        "file_type": file_type,
        "batch_id": "test_batch",
        "kb_name": "test_kb",
        "version": 1,
        "strategy_config": strategy_config,
        "capability_loader": None,
        "raw_content": content.encode() if content else None,
        "extracted_text": content,
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


class TestPipelineIntegrationResilience:
    """
    **Feature: vertical-domain-phase2, Property 7: Pipeline Integration Resilience**
    **Validates: Requirements 8.5**
    """

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset registry before each test"""
        reset_domain_registry()
        yield
        reset_domain_registry()

    @given(file_paths, file_types, error_messages)
    @settings(max_examples=100)
    def test_domain_interpretation_error_does_not_propagate(
        self,
        file_path: str,
        file_type: str,
        error_message: str
    ):
        """
        For any document where DomainInterpretationError is raised,
        the router should catch it and continue without raising.
        """
        assume(len(file_path.strip()) > 0)
        assume(len(error_message.strip()) > 0)
        
        # Setup
        registry = get_domain_registry()
        failing_interpreter = FailingInterpreter(
            error_type="domain",
            error_message=error_message
        )
        registry.register(
            "failing_domain",
            type(failing_interpreter),
            detection_patterns=[".*"]  # Match everything
        )
        
        router = DomainRouterNode()
        state = create_test_state(
            file_path=file_path,
            file_type=file_type,
            domain="failing_domain"
        )
        
        # Execute - should NOT raise
        result_state = asyncio.get_event_loop().run_until_complete(
            router(state)
        )
        
        # Verify state is returned (not exception)
        assert result_state is not None
        assert isinstance(result_state, dict)
        
        # Verify error was logged
        error_log = result_state.get("error_log", [])
        assert len(error_log) > 0
        assert any(e.get("stage") == "domain_router" for e in error_log)

    @given(file_paths, file_types, st.sampled_from(["runtime", "value", "generic"]), error_messages)
    @settings(max_examples=100)
    def test_unexpected_errors_do_not_propagate(
        self,
        file_path: str,
        file_type: str,
        error_type: str,
        error_message: str
    ):
        """
        For any document where an unexpected error occurs during interpretation,
        the router should catch it and continue without raising.
        """
        assume(len(file_path.strip()) > 0)
        assume(len(error_message.strip()) > 0)
        
        # Setup
        registry = get_domain_registry()
        
        # Create a custom failing interpreter class for this test
        class CustomFailingInterpreter(FailingInterpreter):
            domain_id = "custom_failing"
            
            def __init__(self):
                super().__init__(error_type=error_type, error_message=error_message)
        
        registry.register(
            "custom_failing",
            CustomFailingInterpreter,
            detection_patterns=[".*"]
        )
        
        router = DomainRouterNode()
        state = create_test_state(
            file_path=file_path,
            file_type=file_type,
            domain="custom_failing"
        )
        
        # Execute - should NOT raise
        result_state = asyncio.get_event_loop().run_until_complete(
            router(state)
        )
        
        # Verify state is returned
        assert result_state is not None
        assert isinstance(result_state, dict)
        
        # Verify error was logged
        error_log = result_state.get("error_log", [])
        assert len(error_log) > 0

    @given(file_paths, file_types, content_texts)
    @settings(max_examples=50)
    def test_no_domain_detected_continues_normally(
        self,
        file_path: str,
        file_type: str,
        content: str
    ):
        """
        For any document where no domain is detected,
        the router should return state unchanged (except for any logging).
        """
        assume(len(file_path.strip()) > 0)
        
        # Setup - empty registry, no domains registered
        router = DomainRouterNode()
        state = create_test_state(
            file_path=file_path,
            file_type=file_type,
            content=content
        )
        
        # Execute
        result_state = asyncio.get_event_loop().run_until_complete(
            router(state)
        )
        
        # Verify state is returned unchanged (no interpretation added)
        assert result_state is not None
        parsed_blocks = result_state.get("parsed_blocks", [])
        has_interpretation = any(
            b.get("type") == "domain_interpretation"
            for b in parsed_blocks
        )
        assert not has_interpretation

    @given(file_paths, file_types, content_texts)
    @settings(max_examples=50)
    def test_disabled_interpretation_skips_processing(
        self,
        file_path: str,
        file_type: str,
        content: str
    ):
        """
        For any document with domain interpretation disabled,
        the router should skip processing entirely.
        """
        assume(len(file_path.strip()) > 0)
        
        # Setup - register a domain that would match
        registry = get_domain_registry()
        registry.register(
            "successful_domain",
            SuccessfulInterpreter,
            detection_patterns=[".*"]
        )
        
        router = DomainRouterNode()
        state = create_test_state(
            file_path=file_path,
            file_type=file_type,
            content=content,
            enable_domain_interpretation=False
        )
        
        # Execute
        result_state = asyncio.get_event_loop().run_until_complete(
            router(state)
        )
        
        # Verify no interpretation was added
        assert result_state is not None
        parsed_blocks = result_state.get("parsed_blocks", [])
        has_interpretation = any(
            b.get("type") == "domain_interpretation"
            for b in parsed_blocks
        )
        assert not has_interpretation

    @given(file_paths, file_types, content_texts)
    @settings(max_examples=50)
    def test_successful_interpretation_stores_result(
        self,
        file_path: str,
        file_type: str,
        content: str
    ):
        """
        For any document where interpretation succeeds,
        the result should be stored in the state.
        """
        assume(len(file_path.strip()) > 0)
        
        # Setup
        registry = get_domain_registry()
        registry.register(
            "successful_domain",
            SuccessfulInterpreter,
            detection_patterns=[".*"]
        )
        
        router = DomainRouterNode()
        state = create_test_state(
            file_path=file_path,
            file_type=file_type,
            content=content,
            domain="successful_domain"
        )
        
        # Execute
        result_state = asyncio.get_event_loop().run_until_complete(
            router(state)
        )
        
        # Verify interpretation was stored
        assert result_state is not None
        parsed_blocks = result_state.get("parsed_blocks", [])
        interpretation_blocks = [
            b for b in parsed_blocks
            if b.get("type") == "domain_interpretation"
        ]
        assert len(interpretation_blocks) == 1
        
        # Verify interpretation content
        interp = interpretation_blocks[0]
        assert interp["domain_id"] == "successful_domain"
        assert interp["confidence"] == 0.9
        assert "narrative" in interp["content"] or interp["content"] == "Test narrative"

    @given(file_paths, file_types)
    @settings(max_examples=30)
    def test_interpreter_not_found_continues_normally(
        self,
        file_path: str,
        file_type: str
    ):
        """
        For any document where the interpreter is not found,
        the router should continue without error.
        """
        assume(len(file_path.strip()) > 0)
        
        # Setup - register domain but mock get_interpreter to return None
        router = DomainRouterNode()
        state = create_test_state(
            file_path=file_path,
            file_type=file_type,
            domain="nonexistent_domain"
        )
        
        # Execute
        result_state = asyncio.get_event_loop().run_until_complete(
            router(state)
        )
        
        # Verify state is returned without interpretation
        assert result_state is not None
        parsed_blocks = result_state.get("parsed_blocks", [])
        has_interpretation = any(
            b.get("type") == "domain_interpretation"
            for b in parsed_blocks
        )
        assert not has_interpretation


class TestPipelineResilienceEdgeCases:
    """
    Edge case tests for pipeline resilience.
    """

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset registry before each test"""
        reset_domain_registry()
        yield
        reset_domain_registry()

    def test_empty_state_does_not_crash(self):
        """Router should handle minimal state without crashing."""
        router = DomainRouterNode()
        state = {
            "strategy_config": {},
            "parsed_blocks": [],
            "error_log": [],
        }
        
        result = asyncio.get_event_loop().run_until_complete(router(state))
        assert result is not None

    def test_missing_strategy_config_uses_defaults(self):
        """Router should use defaults when strategy_config is missing."""
        router = DomainRouterNode()
        state = {
            "file_path": "test.pdf",
            "file_type": "pdf",
            "parsed_blocks": [],
            "error_log": [],
        }
        
        result = asyncio.get_event_loop().run_until_complete(router(state))
        assert result is not None

    def test_multiple_errors_all_logged(self):
        """Multiple interpretation attempts should all be logged."""
        registry = get_domain_registry()
        
        # Register failing interpreter
        registry.register(
            "failing_domain",
            FailingInterpreter,
            detection_patterns=[".*"]
        )
        
        router = DomainRouterNode()
        
        # Run multiple times
        for i in range(3):
            state = create_test_state(
                file_path=f"test_{i}.pdf",
                domain="failing_domain"
            )
            result = asyncio.get_event_loop().run_until_complete(router(state))
            
            # Each run should have its own error logged
            error_log = result.get("error_log", [])
            assert len(error_log) >= 1

    def test_error_log_preserves_existing_errors(self):
        """New errors should be appended, not replace existing ones."""
        registry = get_domain_registry()
        registry.register(
            "failing_domain",
            FailingInterpreter,
            detection_patterns=[".*"]
        )
        
        router = DomainRouterNode()
        state = create_test_state(domain="failing_domain")
        
        # Add existing error
        state["error_log"] = [{"stage": "previous", "error": "Previous error"}]
        
        result = asyncio.get_event_loop().run_until_complete(router(state))
        
        error_log = result.get("error_log", [])
        assert len(error_log) >= 2
        assert any(e.get("stage") == "previous" for e in error_log)
        assert any(e.get("stage") == "domain_router" for e in error_log)

    def test_unicode_error_messages_handled(self):
        """Unicode characters in error messages should be handled."""
        registry = get_domain_registry()
        
        class UnicodeFailingInterpreter(FailingInterpreter):
            domain_id = "unicode_failing"
            
            def __init__(self):
                super().__init__(
                    error_type="domain",
                    error_message="错误信息：解读失败 🚫"
                )
        
        registry.register(
            "unicode_failing",
            UnicodeFailingInterpreter,
            detection_patterns=[".*"]
        )
        
        router = DomainRouterNode()
        state = create_test_state(domain="unicode_failing")
        
        result = asyncio.get_event_loop().run_until_complete(router(state))
        
        assert result is not None
        error_log = result.get("error_log", [])
        assert len(error_log) > 0
