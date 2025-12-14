"""
Reranker Non-blocking Performance Tests.

Tests that verify the reranker does not block the event loop
when processing documents, ensuring async operations remain responsive.

**Feature: performance-tests, Reranker Non-blocking Tests**
**Validates: Requirements 3.1-3.4**
"""

import asyncio
import inspect
import time
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_state():
    """Create a mock retrieval state for testing."""
    return {
        "strategy_config": {
            "reranker_provider": "cross_encoder",
            "reranker_model": "test-model",
            "fallback_rerank_models": [],
            "rerank_threshold": 0.0,
        },
        "input_query": "What is machine learning?",
        "fused_results": [
            {
                "id": f"doc{i}",
                "content": f"Document content {i} about machine learning and AI.",
                "score": 0.9 - i * 0.1,
                "metadata": {"doc_id": f"doc_{i}.pdf"},
            }
            for i in range(10)
        ],
    }


@pytest.fixture
def large_mock_state():
    """Create a mock state with 100 documents for stress testing."""
    return {
        "strategy_config": {
            "reranker_provider": "cross_encoder",
            "reranker_model": "test-model",
            "fallback_rerank_models": [],
            "rerank_threshold": 0.0,
        },
        "input_query": "What is machine learning?",
        "fused_results": [
            {
                "id": f"doc{i}",
                "content": f"Document content {i} about machine learning and AI. " * 10,
                "score": 0.9 - (i % 10) * 0.05,
                "metadata": {"doc_id": f"doc_{i}.pdf"},
            }
            for i in range(100)
        ],
    }


# =============================================================================
# TC-RR-001: Sync Reranker Wrapping Test
# =============================================================================


class TestSyncRerankerWrapping:
    """
    TC-RR-001: Verify sync reranker.score() is wrapped in asyncio.to_thread().
    
    **Validates: Requirements 3.1**
    """

    @pytest.mark.asyncio
    async def test_sync_reranker_uses_to_thread(self, mock_state):
        """
        Verify that synchronous reranker.score() is wrapped with asyncio.to_thread().
        
        This ensures the sync call doesn't block the event loop.
        """
        from core.retrieval.nodes.reranker import (
            CrossEncoderReranker,
            clear_reranker_cache,
        )

        clear_reranker_cache()

        # Create a sync reranker mock (score is NOT a coroutine)
        mock_sync_reranker = Mock()
        mock_sync_reranker.score = Mock(
            return_value=[0.9 - i * 0.05 for i in range(10)]
        )

        # Verify score is NOT a coroutine function
        assert not asyncio.iscoroutinefunction(mock_sync_reranker.score)

        to_thread_called = False
        original_to_thread = asyncio.to_thread

        async def tracking_to_thread(func, *args, **kwargs):
            nonlocal to_thread_called
            to_thread_called = True
            # Actually run in thread
            return await original_to_thread(func, *args, **kwargs)

        # Patch at the module where it's used, not where it's defined
        with patch(
            "core.retrieval.nodes.reranker.get_reranker",
            new=AsyncMock(return_value=mock_sync_reranker),
        ), patch(
            "core.retrieval.nodes.reranker.asyncio.to_thread",
            side_effect=tracking_to_thread,
        ):
            reranker = CrossEncoderReranker()
            result = await reranker(mock_state.copy())

            # Verify to_thread was called for sync reranker
            assert to_thread_called, "asyncio.to_thread should be called for sync reranker"

            # Verify reranking completed successfully
            assert "reranked_results" in result
            assert len(result["reranked_results"]) == 10

    @pytest.mark.asyncio
    async def test_sync_reranker_score_method_is_sync(self):
        """
        Verify that the base CrossEncoder reranker has a synchronous score method.
        """
        from core.reranker.cross_encoder import Reranker

        # Create reranker instance (will use fallback since model not loaded)
        reranker = Reranker(_skip_singleton=True)

        # Verify score is NOT a coroutine function
        assert not asyncio.iscoroutinefunction(reranker.score)
        assert callable(reranker.score)

    @pytest.mark.asyncio
    async def test_sync_detection_logic(self, mock_state):
        """
        Verify the iscoroutinefunction check correctly identifies sync methods.
        """
        # Create sync mock
        sync_mock = Mock()
        sync_mock.score = Mock(return_value=[0.5])

        # Create async mock
        async_mock = Mock()
        async_mock.score = AsyncMock(return_value=[0.5])

        # Verify detection
        assert not asyncio.iscoroutinefunction(sync_mock.score)
        assert asyncio.iscoroutinefunction(async_mock.score)


# =============================================================================
# TC-RR-002: Async Reranker Direct Call Test
# =============================================================================


class TestAsyncRerankerDirectCall:
    """
    TC-RR-002: Verify async reranker.score() is called directly without thread wrapping.
    
    **Validates: Requirements 3.2**
    """

    @pytest.mark.asyncio
    async def test_async_reranker_direct_call(self, mock_state):
        """
        Verify that asynchronous reranker.score() is called directly.
        
        This ensures we don't unnecessarily wrap async calls in threads.
        """
        from core.retrieval.nodes.reranker import (
            CrossEncoderReranker,
            clear_reranker_cache,
        )

        clear_reranker_cache()

        # Create an async reranker mock (score IS a coroutine)
        mock_async_reranker = Mock()
        mock_async_reranker.score = AsyncMock(
            return_value=[0.9 - i * 0.05 for i in range(10)]
        )

        # Verify score IS a coroutine function
        assert asyncio.iscoroutinefunction(mock_async_reranker.score)

        to_thread_called = False

        async def tracking_to_thread(func, *args, **kwargs):
            nonlocal to_thread_called
            to_thread_called = True
            return func(*args, **kwargs)

        # Patch at the module where it's used
        with patch(
            "core.retrieval.nodes.reranker.get_reranker",
            new=AsyncMock(return_value=mock_async_reranker),
        ), patch(
            "core.retrieval.nodes.reranker.asyncio.to_thread",
            side_effect=tracking_to_thread,
        ):
            reranker = CrossEncoderReranker()
            result = await reranker(mock_state.copy())

            # Verify to_thread was NOT called for async reranker
            assert not to_thread_called, "asyncio.to_thread should NOT be called for async reranker"

            # Verify the async score method was called directly
            mock_async_reranker.score.assert_called_once()

            # Verify reranking completed successfully
            assert "reranked_results" in result
            assert len(result["reranked_results"]) == 10

    @pytest.mark.asyncio
    async def test_async_reranker_awaited_correctly(self, mock_state):
        """
        Verify that async reranker.score() is properly awaited.
        """
        from core.retrieval.nodes.reranker import (
            CrossEncoderReranker,
            clear_reranker_cache,
        )

        clear_reranker_cache()

        call_order = []

        async def async_score(query, texts):
            call_order.append("score_start")
            await asyncio.sleep(0.01)  # Simulate async work
            call_order.append("score_end")
            return [0.5] * len(texts)

        mock_async_reranker = Mock()
        mock_async_reranker.score = async_score

        # Patch at the module where it's used
        with patch(
            "core.retrieval.nodes.reranker.get_reranker",
            new=AsyncMock(return_value=mock_async_reranker),
        ):
            reranker = CrossEncoderReranker()
            await reranker(mock_state.copy())

            # Verify the async method completed
            assert call_order == ["score_start", "score_end"]


# =============================================================================
# Helper for Event Loop Responsiveness Tests
# =============================================================================


async def concurrent_timer(interval_ms: float, results: list, stop_event: asyncio.Event):
    """
    A concurrent timer that records timestamps at regular intervals.
    
    Used to verify the event loop remains responsive during reranking.
    """
    start = time.perf_counter()
    while not stop_event.is_set():
        elapsed = (time.perf_counter() - start) * 1000  # ms
        results.append(elapsed)
        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=interval_ms / 1000,
            )
            break
        except asyncio.TimeoutError:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
