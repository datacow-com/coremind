"""
Property-based tests for SSE Progress Event Structure

**Feature: capability-visualization, Property 3: SSE Progress Event Structure**
**Validates: Requirements 2.4, 11.2**

For any running algorithm task, progress events emitted via SSE should contain
stage (string), progress (0-100), and message (string) fields.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Any
from datetime import datetime, timezone
from uuid import uuid4

from server.api.algorithms import (
    AlgorithmType,
    AlgorithmMode,
    TaskStatus,
    AlgorithmTask,
    AlgorithmProgress,
    add_progress,
    get_progress_history,
    _task_store,
    _task_progress,
    _progress_subscribers,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Strategies for generating test data
# ═══════════════════════════════════════════════════════════════════════════════

# Valid stage names
stage_strategy = st.sampled_from([
    "initializing",
    "collecting",
    "summarizing",
    "extracting",
    "building",
    "storing",
    "completed",
    "failed",
])

# Progress percentage (0-100)
progress_strategy = st.integers(min_value=0, max_value=100)

# Message text
message_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?-_"),
    min_size=1,
    max_size=200,
)

# Task ID
task_id_strategy = st.uuids().map(str)

# Timestamp
timestamp_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
).map(lambda dt: dt.isoformat() + "Z")


# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def clear_stores():
    """Clear all stores before each test."""
    _task_store.clear()
    _task_progress.clear()
    _progress_subscribers.clear()
    yield
    _task_store.clear()
    _task_progress.clear()
    _progress_subscribers.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# Property Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSSEProgressEventStructure:
    """
    **Feature: capability-visualization, Property 3: SSE Progress Event Structure**
    **Validates: Requirements 2.4, 11.2**
    
    For any running algorithm task, progress events emitted via SSE should contain
    stage (string), progress (0-100), and message (string) fields.
    """

    @given(
        task_id=task_id_strategy,
        stage=stage_strategy,
        progress=progress_strategy,
        message=message_strategy,
        timestamp=timestamp_strategy,
    )
    @settings(max_examples=100)
    def test_progress_event_has_required_fields(
        self,
        task_id: str,
        stage: str,
        progress: int,
        message: str,
        timestamp: str,
    ):
        """
        Property: Every progress event should have stage, progress, and message fields.
        """
        event = AlgorithmProgress(
            task_id=task_id,
            stage=stage,
            progress=progress,
            message=message,
            timestamp=timestamp,
        )
        
        # Verify required fields exist and have correct types
        assert hasattr(event, 'task_id')
        assert hasattr(event, 'stage')
        assert hasattr(event, 'progress')
        assert hasattr(event, 'message')
        assert hasattr(event, 'timestamp')
        
        assert isinstance(event.task_id, str)
        assert isinstance(event.stage, str)
        assert isinstance(event.progress, int)
        assert isinstance(event.message, str)
        assert isinstance(event.timestamp, str)

    @given(
        task_id=task_id_strategy,
        stage=stage_strategy,
        progress=progress_strategy,
        message=message_strategy,
    )
    @settings(max_examples=100)
    def test_progress_in_valid_range(
        self,
        task_id: str,
        stage: str,
        progress: int,
        message: str,
    ):
        """
        Property: Progress percentage should always be between 0 and 100.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        event = AlgorithmProgress(
            task_id=task_id,
            stage=stage,
            progress=progress,
            message=message,
            timestamp=timestamp,
        )
        
        assert 0 <= event.progress <= 100, \
            f"Progress {event.progress} out of valid range [0, 100]"

    @given(progress=st.integers(min_value=-100, max_value=-1))
    @settings(max_examples=20)
    def test_negative_progress_rejected(self, progress: int):
        """
        Property: Negative progress values should be rejected by validation.
        """
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            AlgorithmProgress(
                task_id=str(uuid4()),
                stage="test",
                progress=progress,
                message="test",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    @given(progress=st.integers(min_value=101, max_value=200))
    @settings(max_examples=20)
    def test_progress_over_100_rejected(self, progress: int):
        """
        Property: Progress values over 100 should be rejected by validation.
        """
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            AlgorithmProgress(
                task_id=str(uuid4()),
                stage="test",
                progress=progress,
                message="test",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    @given(
        task_id=task_id_strategy,
        stage=stage_strategy,
        progress=progress_strategy,
        message=message_strategy,
    )
    @settings(max_examples=50)
    def test_progress_event_serialization_roundtrip(
        self,
        task_id: str,
        stage: str,
        progress: int,
        message: str,
    ):
        """
        Property: Progress events should survive JSON serialization round-trip.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        event = AlgorithmProgress(
            task_id=task_id,
            stage=stage,
            progress=progress,
            message=message,
            timestamp=timestamp,
        )
        
        # Serialize and deserialize
        json_str = event.model_dump_json()
        restored = AlgorithmProgress.model_validate_json(json_str)
        
        # Verify all fields preserved
        assert restored.task_id == event.task_id
        assert restored.stage == event.stage
        assert restored.progress == event.progress
        assert restored.message == event.message
        assert restored.timestamp == event.timestamp

    @given(
        stages=st.lists(stage_strategy, min_size=1, max_size=10),
    )
    @settings(max_examples=50)
    def test_progress_history_preserves_order(
        self,
        stages: list[str],
    ):
        """
        Property: Progress history should preserve the order of events.
        """
        # Use a unique task_id for each iteration to avoid cross-contamination
        task_id = str(uuid4())
        
        # Add progress events
        for i, stage in enumerate(stages):
            event = AlgorithmProgress(
                task_id=task_id,
                stage=stage,
                progress=min(i * 10, 100),
                message=f"Stage {i}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            add_progress(task_id, event)
        
        # Get history
        history = get_progress_history(task_id)
        
        # Verify order preserved
        assert len(history) == len(stages)
        for i, event in enumerate(history):
            assert event.stage == stages[i]

    @given(
        num_events=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=30)
    def test_progress_history_completeness(
        self,
        num_events: int,
    ):
        """
        Property: All added progress events should be retrievable from history.
        """
        # Use a unique task_id for each iteration to avoid cross-contamination
        task_id = str(uuid4())
        
        # Add events
        for i in range(num_events):
            event = AlgorithmProgress(
                task_id=task_id,
                stage=f"stage_{i}",
                progress=min(i * 5, 100),
                message=f"Message {i}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            add_progress(task_id, event)
        
        # Get history
        history = get_progress_history(task_id)
        
        # Verify all events present
        assert len(history) == num_events


class TestProgressEventContent:
    """Tests for progress event content validation."""

    @given(stage=st.text(min_size=0, max_size=100))
    @settings(max_examples=30)
    def test_stage_accepts_any_string(self, stage: str):
        """
        Property: Stage field should accept any string value.
        """
        event = AlgorithmProgress(
            task_id=str(uuid4()),
            stage=stage,
            progress=50,
            message="test",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        
        assert event.stage == stage

    @given(message=st.text(min_size=0, max_size=1000))
    @settings(max_examples=30)
    def test_message_accepts_any_string(self, message: str):
        """
        Property: Message field should accept any string value.
        """
        event = AlgorithmProgress(
            task_id=str(uuid4()),
            stage="test",
            progress=50,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        
        assert event.message == message

    def test_empty_stage_allowed(self):
        """Empty stage string should be allowed."""
        event = AlgorithmProgress(
            task_id=str(uuid4()),
            stage="",
            progress=0,
            message="Starting",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        
        assert event.stage == ""

    def test_empty_message_allowed(self):
        """Empty message string should be allowed."""
        event = AlgorithmProgress(
            task_id=str(uuid4()),
            stage="running",
            progress=50,
            message="",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        
        assert event.message == ""


class TestProgressEventBoundaries:
    """Tests for progress event boundary conditions."""

    def test_progress_zero(self):
        """Progress of 0 should be valid."""
        event = AlgorithmProgress(
            task_id=str(uuid4()),
            stage="initializing",
            progress=0,
            message="Starting",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        
        assert event.progress == 0

    def test_progress_100(self):
        """Progress of 100 should be valid."""
        event = AlgorithmProgress(
            task_id=str(uuid4()),
            stage="completed",
            progress=100,
            message="Done",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        
        assert event.progress == 100

    @given(progress=st.integers(min_value=0, max_value=100))
    @settings(max_examples=50)
    def test_all_valid_progress_values(self, progress: int):
        """All integer values from 0 to 100 should be valid."""
        event = AlgorithmProgress(
            task_id=str(uuid4()),
            stage="running",
            progress=progress,
            message="Processing",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        
        assert event.progress == progress
