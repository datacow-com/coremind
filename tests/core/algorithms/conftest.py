#!/usr/bin/env python3
"""
Shared fixtures and Hypothesis strategies for algorithms tests.

Provides:
- Mock graph structures with known community patterns
- Mixed channel chunks for isolation testing
- Hypothesis strategies for property-based testing
"""

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Try to import hypothesis, skip if not available
try:
    from hypothesis import strategies as st
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    st = None


# =============================================================================
# Graph Fixtures
# =============================================================================

@pytest.fixture
def mock_graph_with_two_communities():
    """
    Generate a graph with two disconnected triangles.
    Should produce exactly 2 communities when using Louvain.
    """
    return {
        "nodes": [
            {"entity_name": "A1", "entity_type": "人物", "description": "人物A1"},
            {"entity_name": "A2", "entity_type": "人物", "description": "人物A2"},
            {"entity_name": "A3", "entity_type": "人物", "description": "人物A3"},
            {"entity_name": "B1", "entity_type": "组织", "description": "组织B1"},
            {"entity_name": "B2", "entity_type": "组织", "description": "组织B2"},
            {"entity_name": "B3", "entity_type": "组织", "description": "组织B3"},
        ],
        "edges": [
            # Triangle A (A1-A2-A3)
            {"src_id": "A1", "tgt_id": "A2", "weight": 1, "description": "关系1"},
            {"src_id": "A2", "tgt_id": "A3", "weight": 1, "description": "关系2"},
            {"src_id": "A3", "tgt_id": "A1", "weight": 1, "description": "关系3"},
            # Triangle B (B1-B2-B3)
            {"src_id": "B1", "tgt_id": "B2", "weight": 1, "description": "关系4"},
            {"src_id": "B2", "tgt_id": "B3", "weight": 1, "description": "关系5"},
            {"src_id": "B3", "tgt_id": "B1", "weight": 1, "description": "关系6"},
        ]
    }


@pytest.fixture
def mock_graph_single_component():
    """
    Generate a fully connected graph that should form a single community.
    """
    return {
        "nodes": [
            {"entity_name": "X", "entity_type": "人物", "description": ""},
            {"entity_name": "Y", "entity_type": "人物", "description": ""},
            {"entity_name": "Z", "entity_type": "人物", "description": ""},
        ],
        "edges": [
            {"src_id": "X", "tgt_id": "Y", "weight": 1, "description": ""},
            {"src_id": "Y", "tgt_id": "Z", "weight": 1, "description": ""},
            {"src_id": "Z", "tgt_id": "X", "weight": 1, "description": ""},
        ]
    }


@pytest.fixture
def mock_empty_graph():
    """Empty graph for edge case testing."""
    return {"nodes": [], "edges": []}


# =============================================================================
# Channel Isolation Fixtures
# =============================================================================

@pytest.fixture
def test_channel_a() -> str:
    """Generate unique channel_id for test isolation (channel A)."""
    return f"test_algo_a_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_channel_b() -> str:
    """Generate unique channel_id for cross-tenant testing (channel B)."""
    return f"test_algo_b_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def mixed_channel_chunks(test_channel_a: str, test_channel_b: str) -> list[dict[str, Any]]:
    """
    Generate chunks from two different channels for isolation testing.
    Channel A: Contains "张三", "北京"
    Channel B: Contains "李四", "上海"
    """
    return [
        {"content": "张三在北京工作，是一名教授", "metadata": {"channel_id": test_channel_a}},
        {"content": "李四在上海学习，是一名学生", "metadata": {"channel_id": test_channel_b}},
        {"content": "王五是张三的同事，也在北京", "metadata": {"channel_id": test_channel_a}},
        {"content": "赵六是李四的朋友，住在上海", "metadata": {"channel_id": test_channel_b}},
        {"content": "张三和王五一起研究人工智能", "metadata": {"channel_id": test_channel_a}},
        {"content": "李四和赵六一起学习计算机", "metadata": {"channel_id": test_channel_b}},
    ]


@pytest.fixture
def channel_a_chunks(test_channel_a: str) -> list[dict[str, Any]]:
    """Generate chunks only for channel A."""
    return [
        {"content": f"张三是北京大学的教授，研究人工智能领域。内容编号{i}", 
         "metadata": {"channel_id": test_channel_a, "doc_id": f"doc_a_{i}"}}
        for i in range(10)
    ]


@pytest.fixture
def channel_b_chunks(test_channel_b: str) -> list[dict[str, Any]]:
    """Generate chunks only for channel B."""
    return [
        {"content": f"李四是清华大学的学生，学习计算机科学。内容编号{i}",
         "metadata": {"channel_id": test_channel_b, "doc_id": f"doc_b_{i}"}}
        for i in range(10)
    ]


# =============================================================================
# MindMap Fixtures
# =============================================================================

@pytest.fixture
def mock_topics():
    """Sample topics for MindMap testing."""
    return [
        {"name": "人工智能", "subtopics": ["机器学习", "深度学习"], "keywords": ["AI", "ML"]},
        {"name": "教育", "subtopics": ["高等教育", "在线教育"], "keywords": ["学习", "大学"]},
    ]


@pytest.fixture
def mock_mindmap_state(mock_topics):
    """Complete MindMap state for testing."""
    return {
        "kb_name": "test_knowledge_base",
        "chunks": ["人工智能是计算机科学的分支", "教育是社会发展的基础"],
        "topics": mock_topics,
        "mindmap": {},
        "meta": {},
    }


# =============================================================================
# LLM Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_llm_gateway():
    """Mock LLM gateway for testing without real LLM calls."""
    with patch("core.llm.gateway.LLMGateway") as mock_class:
        mock_instance = MagicMock()
        
        async def mock_chat(*args, **kwargs):
            prompt = kwargs.get("prompt", "") or (args[0] if args else "")
            context = kwargs.get("context", "")
            
            # Return mock responses based on prompt content
            if "摘要" in prompt or "总结" in prompt:
                return "这是一段关于人工智能研究的摘要内容。"
            elif "实体" in prompt or "抽取" in prompt:
                # Extract entities based on context
                entities = []
                relations = []
                if "张三" in context:
                    entities.append({"name": "张三", "type": "人物", "desc": "教授"})
                if "北京" in context:
                    entities.append({"name": "北京", "type": "地点", "desc": "首都"})
                if "李四" in context:
                    entities.append({"name": "李四", "type": "人物", "desc": "学生"})
                if "上海" in context:
                    entities.append({"name": "上海", "type": "地点", "desc": "城市"})
                if "张三" in context and "北京" in context:
                    relations.append({"src": "张三", "tgt": "北京", "desc": "工作于", "keywords": ["工作"]})
                return json.dumps({"entities": entities, "relations": relations})
            elif "主题" in prompt or "topics" in prompt.lower():
                return json.dumps({
                    "topics": [
                        {"name": "人工智能", "subtopics": ["机器学习", "深度学习"], "keywords": ["AI"]},
                        {"name": "教育", "subtopics": ["高等教育"], "keywords": ["学习"]},
                    ]
                })
            return "默认响应"
        
        mock_instance.chat = mock_chat
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_llm_error():
    """Mock LLM gateway that always raises an error."""
    with patch("core.llm.gateway.LLMGateway") as mock_class:
        mock_instance = MagicMock()
        
        async def mock_chat_error(*args, **kwargs):
            raise Exception("LLM service unavailable")
        
        mock_instance.chat = mock_chat_error
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_llm_malformed_json():
    """Mock LLM gateway that returns malformed JSON."""
    with patch("core.llm.gateway.LLMGateway") as mock_class:
        mock_instance = MagicMock()
        
        async def mock_chat_malformed(*args, **kwargs):
            return "This is not valid JSON {{{{"
        
        mock_instance.chat = mock_chat_malformed
        mock_class.return_value = mock_instance
        yield mock_instance


# =============================================================================
# Storage Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_list_all_meta():
    """Mock list_all_meta for MindMap testing."""
    return [
        {"content": "人工智能是计算机科学的一个分支", "metadata": {}},
        {"content": "机器学习是人工智能的核心技术", "metadata": {}},
        {"content": "深度学习使用神经网络进行学习", "metadata": {}},
    ]


@pytest.fixture
def capture_file_writes():
    """Fixture to capture file write operations."""
    written_files = {}
    
    original_open = open
    
    def mock_open(path, mode='r', **kwargs):
        if 'w' in mode:
            mock_file = MagicMock()
            content_buffer = []
            
            def write(content):
                content_buffer.append(content)
            
            def get_content():
                return ''.join(content_buffer)
            
            mock_file.write = write
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=False)
            
            # Store reference for later inspection
            written_files[path] = {'file': mock_file, 'get_content': get_content}
            return mock_file
        else:
            return original_open(path, mode, **kwargs)
    
    with patch('builtins.open', mock_open):
        yield written_files


# =============================================================================
# Hypothesis Strategies (if available)
# =============================================================================

if HYPOTHESIS_AVAILABLE:
    # Node strategy
    node_strategy = st.fixed_dictionaries({
        "entity_name": st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N')),
            min_size=1, 
            max_size=20
        ),
        "entity_type": st.sampled_from(["人物", "组织", "地点", "事件", "类别"]),
        "description": st.text(max_size=100),
    })
    
    # Edge strategy
    edge_strategy = st.fixed_dictionaries({
        "src_id": st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N')),
            min_size=1, 
            max_size=20
        ),
        "tgt_id": st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N')),
            min_size=1, 
            max_size=20
        ),
        "weight": st.integers(min_value=1, max_value=10),
        "description": st.text(max_size=50),
    })
    
    # Graph strategy
    graph_strategy = st.fixed_dictionaries({
        "nodes": st.lists(node_strategy, min_size=1, max_size=20),
        "edges": st.lists(edge_strategy, max_size=50),
    })
    
    # Topic strategy
    topic_strategy = st.fixed_dictionaries({
        "name": st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N')),
            min_size=1, 
            max_size=30
        ),
        "subtopics": st.lists(
            st.text(alphabet=st.characters(whitelist_categories=('L', 'N')), min_size=1, max_size=20),
            max_size=5
        ),
        "keywords": st.lists(
            st.text(alphabet=st.characters(whitelist_categories=('L', 'N')), min_size=1, max_size=10),
            max_size=5
        ),
    })
    
    # Summary strategy for RAPTOR
    summary_strategy = st.fixed_dictionaries({
        "summary": st.text(max_size=200),
        "indices": st.lists(st.integers(min_value=0, max_value=100), min_size=1, max_size=10),
    })
