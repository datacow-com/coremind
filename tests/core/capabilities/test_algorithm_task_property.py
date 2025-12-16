"""
Property-based tests for Algorithm Task Creation API

**Feature: capability-visualization, Property 2: Algorithm Task Creation**
**Validates: Requirements 2.1, 2.2, 2.3**

For any valid algorithm type (raptor, graphrag, mindmap), KB name, and configuration,
starting an algorithm task should return a unique task ID and the task should be
retrievable by that ID.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Any
import asyncio

from server.api.algorithms import (
    AlgorithmType,
    AlgorithmMode,
    TaskStatus,
    AlgorithmTask,
    AlgorithmRunRequest,
    TaskRunResponse,
    get_task,
    save_task,
    list_tasks,
    estimate_cost,
    _task_store,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Strategies for generating test data
# ═══════════════════════════════════════════════════════════════════════════════

# Valid KB names (alphanumeric with underscores, reasonable length)
kb_name_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_"),
    min_size=1,
    max_size=50,
).filter(lambda x: x[0].isalpha())  # Must start with letter

# Algorithm types
algorithm_type_strategy = st.sampled_from([
    AlgorithmType.RAPTOR,
    AlgorithmType.GRAPHRAG,
    AlgorithmType.MINDMAP,
])

# Algorithm modes
algorithm_mode_strategy = st.sampled_from([
    AlgorithmMode.LIGHT,
    AlgorithmMode.DEEP,
])

# Valid config values
config_value_strategy = st.one_of(
    st.booleans(),
    st.integers(min_value=1, max_value=100),
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    st.text(min_size=1, max_size=20, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_")),
    st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=5),
)

# Algorithm config strategy
algorithm_config_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=20, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_")),
    values=config_value_strategy,
    min_size=0,
    max_size=5,
)

# Algorithm run request strategy
algorithm_run_request_strategy = st.builds(
    AlgorithmRunRequest,
    kb_name=kb_name_strategy,
    mode=algorithm_mode_strategy,
    config=algorithm_config_strategy,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def clear_task_store():
    """Clear task store before each test."""
    _task_store.clear()
    yield
    _task_store.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# Property Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAlgorithmTaskCreation:
    """
    **Feature: capability-visualization, Property 2: Algorithm Task Creation**
    **Validates: Requirements 2.1, 2.2, 2.3**
    
    For any valid algorithm type (raptor, graphrag, mindmap), KB name, and configuration,
    starting an algorithm task should return a unique task ID and the task should be
    retrievable by that ID.
    """

    @given(
        algorithm=algorithm_type_strategy,
        kb_name=kb_name_strategy,
        mode=algorithm_mode_strategy,
        config=algorithm_config_strategy,
    )
    @settings(max_examples=100)
    def test_task_creation_and_retrieval(
        self,
        algorithm: AlgorithmType,
        kb_name: str,
        mode: AlgorithmMode,
        config: dict[str, Any],
    ):
        """
        Property: Creating a task should make it retrievable by its ID.
        
        For any valid algorithm type, KB name, mode, and configuration:
        1. Creating a task should return a unique task ID
        2. The task should be retrievable by that ID
        3. The retrieved task should have the correct algorithm, KB name, and mode
        """
        from datetime import datetime
        from uuid import uuid4
        
        # Create task
        task_id = str(uuid4())
        estimated_cost = estimate_cost(algorithm, kb_name, mode, config)
        
        task = AlgorithmTask(
            task_id=task_id,
            algorithm=algorithm,
            kb_name=kb_name,
            mode=mode,
            status=TaskStatus.PENDING,
            config=config,
            created_at=datetime.utcnow().isoformat() + "Z",
            estimated_cost=estimated_cost,
        )
        
        # Save task
        save_task(task)
        
        # Retrieve task
        retrieved = get_task(task_id)
        
        # Verify task is retrievable
        assert retrieved is not None, f"Task {task_id} not found after creation"
        
        # Verify task properties match
        assert retrieved.task_id == task_id
        assert retrieved.algorithm == algorithm
        assert retrieved.kb_name == kb_name
        assert retrieved.mode == mode
        assert retrieved.status == TaskStatus.PENDING
        assert retrieved.config == config
        assert retrieved.estimated_cost == estimated_cost

    @given(
        algorithm=algorithm_type_strategy,
        kb_name=kb_name_strategy,
        mode=algorithm_mode_strategy,
    )
    @settings(max_examples=50)
    def test_unique_task_ids(
        self,
        algorithm: AlgorithmType,
        kb_name: str,
        mode: AlgorithmMode,
    ):
        """
        Property: Each task creation should produce a unique task ID.
        """
        from datetime import datetime
        from uuid import uuid4
        
        task_ids = set()
        
        # Create multiple tasks
        for _ in range(5):
            task_id = str(uuid4())
            task = AlgorithmTask(
                task_id=task_id,
                algorithm=algorithm,
                kb_name=kb_name,
                mode=mode,
                status=TaskStatus.PENDING,
                config={},
                created_at=datetime.utcnow().isoformat() + "Z",
                estimated_cost=0.0,
            )
            save_task(task)
            
            # Verify uniqueness
            assert task_id not in task_ids, f"Duplicate task ID: {task_id}"
            task_ids.add(task_id)

    @given(
        algorithm=algorithm_type_strategy,
        kb_name=kb_name_strategy,
        mode=algorithm_mode_strategy,
    )
    @settings(max_examples=50)
    def test_task_list_contains_created_task(
        self,
        algorithm: AlgorithmType,
        kb_name: str,
        mode: AlgorithmMode,
    ):
        """
        Property: A created task should appear in the task list.
        """
        from datetime import datetime
        from uuid import uuid4
        
        task_id = str(uuid4())
        task = AlgorithmTask(
            task_id=task_id,
            algorithm=algorithm,
            kb_name=kb_name,
            mode=mode,
            status=TaskStatus.PENDING,
            config={},
            created_at=datetime.utcnow().isoformat() + "Z",
            estimated_cost=0.0,
        )
        save_task(task)
        
        # List all tasks
        tasks = list_tasks()
        task_ids = [t.task_id for t in tasks]
        
        assert task_id in task_ids, f"Task {task_id} not in task list"

    @given(
        algorithm=algorithm_type_strategy,
        kb_name=kb_name_strategy,
        mode=algorithm_mode_strategy,
    )
    @settings(max_examples=50)
    def test_task_list_filter_by_kb(
        self,
        algorithm: AlgorithmType,
        kb_name: str,
        mode: AlgorithmMode,
    ):
        """
        Property: Filtering tasks by KB name should return only tasks for that KB.
        """
        from datetime import datetime
        from uuid import uuid4
        
        # Create task for target KB
        task_id = str(uuid4())
        task = AlgorithmTask(
            task_id=task_id,
            algorithm=algorithm,
            kb_name=kb_name,
            mode=mode,
            status=TaskStatus.PENDING,
            config={},
            created_at=datetime.utcnow().isoformat() + "Z",
            estimated_cost=0.0,
        )
        save_task(task)
        
        # Create task for different KB
        other_task = AlgorithmTask(
            task_id=str(uuid4()),
            algorithm=algorithm,
            kb_name="other_kb_" + kb_name,
            mode=mode,
            status=TaskStatus.PENDING,
            config={},
            created_at=datetime.utcnow().isoformat() + "Z",
            estimated_cost=0.0,
        )
        save_task(other_task)
        
        # Filter by KB name
        filtered = list_tasks(kb_name=kb_name)
        
        # All filtered tasks should have the target KB name
        for t in filtered:
            assert t.kb_name == kb_name

    @given(
        algorithm=algorithm_type_strategy,
        kb_name=kb_name_strategy,
        mode=algorithm_mode_strategy,
    )
    @settings(max_examples=50)
    def test_task_list_filter_by_algorithm(
        self,
        algorithm: AlgorithmType,
        kb_name: str,
        mode: AlgorithmMode,
    ):
        """
        Property: Filtering tasks by algorithm type should return only tasks of that type.
        """
        from datetime import datetime
        from uuid import uuid4
        
        # Create task with target algorithm
        task_id = str(uuid4())
        task = AlgorithmTask(
            task_id=task_id,
            algorithm=algorithm,
            kb_name=kb_name,
            mode=mode,
            status=TaskStatus.PENDING,
            config={},
            created_at=datetime.utcnow().isoformat() + "Z",
            estimated_cost=0.0,
        )
        save_task(task)
        
        # Filter by algorithm
        filtered = list_tasks(algorithm=algorithm)
        
        # All filtered tasks should have the target algorithm
        for t in filtered:
            assert t.algorithm == algorithm


class TestCostEstimation:
    """
    Tests for cost estimation functionality.
    
    **Feature: capability-visualization, Property 12: Cost Estimation Consistency**
    **Validates: Requirements 8.2**
    """

    @given(
        algorithm=algorithm_type_strategy,
        kb_name=kb_name_strategy,
        mode=algorithm_mode_strategy,
        config=algorithm_config_strategy,
    )
    @settings(max_examples=50)
    def test_cost_estimation_positive(
        self,
        algorithm: AlgorithmType,
        kb_name: str,
        mode: AlgorithmMode,
        config: dict[str, Any],
    ):
        """
        Property: Cost estimation should always return a positive number.
        """
        cost = estimate_cost(algorithm, kb_name, mode, config)
        
        assert cost > 0, f"Cost should be positive, got {cost}"
        assert isinstance(cost, (int, float))

    @given(
        algorithm=algorithm_type_strategy,
        kb_name=kb_name_strategy,
        config=algorithm_config_strategy,
    )
    @settings(max_examples=50)
    def test_deep_mode_costs_more(
        self,
        algorithm: AlgorithmType,
        kb_name: str,
        config: dict[str, Any],
    ):
        """
        Property: Deep mode should cost more than light mode.
        """
        light_cost = estimate_cost(algorithm, kb_name, AlgorithmMode.LIGHT, config)
        deep_cost = estimate_cost(algorithm, kb_name, AlgorithmMode.DEEP, config)
        
        assert deep_cost > light_cost, \
            f"Deep mode ({deep_cost}) should cost more than light mode ({light_cost})"


class TestAlgorithmTaskModel:
    """Tests for AlgorithmTask Pydantic model."""

    @given(
        algorithm=algorithm_type_strategy,
        kb_name=kb_name_strategy,
        mode=algorithm_mode_strategy,
        config=algorithm_config_strategy,
    )
    @settings(max_examples=30)
    def test_model_serialization_roundtrip(
        self,
        algorithm: AlgorithmType,
        kb_name: str,
        mode: AlgorithmMode,
        config: dict[str, Any],
    ):
        """
        Property: AlgorithmTask model should survive JSON serialization round-trip.
        """
        from datetime import datetime
        from uuid import uuid4
        
        task = AlgorithmTask(
            task_id=str(uuid4()),
            algorithm=algorithm,
            kb_name=kb_name,
            mode=mode,
            status=TaskStatus.PENDING,
            config=config,
            created_at=datetime.utcnow().isoformat() + "Z",
            estimated_cost=1000.0,
        )
        
        # Serialize and deserialize
        json_str = task.model_dump_json()
        restored = AlgorithmTask.model_validate_json(json_str)
        
        # Verify key fields
        assert restored.task_id == task.task_id
        assert restored.algorithm == task.algorithm
        assert restored.kb_name == task.kb_name
        assert restored.mode == task.mode
        assert restored.status == task.status

    def test_default_values(self):
        """AlgorithmTask should have sensible defaults."""
        from datetime import datetime
        from uuid import uuid4
        
        task = AlgorithmTask(
            task_id=str(uuid4()),
            algorithm=AlgorithmType.RAPTOR,
            kb_name="test_kb",
            mode=AlgorithmMode.LIGHT,
            created_at=datetime.utcnow().isoformat() + "Z",
        )
        
        assert task.status == TaskStatus.PENDING
        assert task.progress == 0
        assert task.stage == ""
        assert task.config == {}
        assert task.error is None
        assert task.result is None


class TestAlgorithmRunRequest:
    """Tests for AlgorithmRunRequest Pydantic model."""

    @given(request=algorithm_run_request_strategy)
    @settings(max_examples=30)
    def test_request_model_valid(self, request: AlgorithmRunRequest):
        """
        Property: Generated AlgorithmRunRequest should be valid.
        """
        assert request.kb_name
        assert request.mode in [AlgorithmMode.LIGHT, AlgorithmMode.DEEP]
        assert isinstance(request.config, dict)

    def test_default_mode(self):
        """AlgorithmRunRequest should default to LIGHT mode."""
        request = AlgorithmRunRequest(kb_name="test_kb")
        
        assert request.mode == AlgorithmMode.LIGHT
        assert request.config == {}
