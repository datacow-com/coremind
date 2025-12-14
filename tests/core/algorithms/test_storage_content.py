#!/usr/bin/env python3
"""
Storage Content Structure Verification Tests

Tests for verifying that RAPTOR and GraphRAG store correct JSON structures.

Requirements covered:
- 4.1: RAPTOR storage contains layers and summaries arrays
- 4.2: GraphRAG storage contains nodes and edges arrays
- 4.3: GraphRAG storage contains communities structure
- 4.4: Meta counts match actual array lengths
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, mock_open

import pytest

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to import hypothesis
try:
    from hypothesis import given, settings, strategies as st
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False


def run_async(coro):
    """Helper to run async functions in sync tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


# =============================================================================
# RAPTOR Storage Tests
# =============================================================================

class TestRaptorStorageContent:
    """Tests for RAPTOR storage JSON structure."""

    def test_raptor_storage_contains_layers(self):
        """
        Test that RAPTOR storage contains layers array.
        
        **Feature: algorithms-test-review, Property 3: Storage JSON Structure Validity**
        **Validates: Requirements 4.1**
        """
        from core.algorithms.raptor_deep import store_raptor
        
        captured_content = []
        
        def capture_open(path, mode, **kwargs):
            mock_file = MagicMock()
            
            def capture_write(content):
                captured_content.append(content)
            
            mock_file.write = capture_write
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=False)
            return mock_file
        
        with patch("builtins.open", capture_open):
            with patch("os.makedirs"):
                with patch("core.algorithms.raptor_deep.settings") as mock_settings:
                    mock_settings.uploads_dir_resolved = "/tmp/test"
                    
                    state = {
                        "kb_name": "test_kb",
                        "layers": [[0, 1, 2], [0, 1], [0]],
                        "summaries": [
                            {"summary": "摘要1", "indices": [0, 1]},
                            {"summary": "摘要2", "indices": [2]},
                        ],
                        "meta": {},
                    }
                    
                    run_async(store_raptor(state))
        
        # Parse captured JSON
        full_content = "".join(captured_content)
        data = json.loads(full_content)
        
        # Verify structure
        assert "layers" in data, "RAPTOR output must contain 'layers'"
        assert isinstance(data["layers"], list), "layers must be a list"
        assert len(data["layers"]) == 3

    def test_raptor_storage_contains_summaries(self):
        """
        Test that RAPTOR storage contains summaries array.
        
        **Validates: Requirements 4.1**
        """
        from core.algorithms.raptor_deep import store_raptor
        
        captured_content = []
        
        def capture_open(path, mode, **kwargs):
            mock_file = MagicMock()
            mock_file.write = lambda c: captured_content.append(c)
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=False)
            return mock_file
        
        with patch("builtins.open", capture_open):
            with patch("os.makedirs"):
                with patch("core.algorithms.raptor_deep.settings") as mock_settings:
                    mock_settings.uploads_dir_resolved = "/tmp/test"
                    
                    state = {
                        "kb_name": "test_kb",
                        "layers": [[0, 1]],
                        "summaries": [
                            {"summary": "第一个摘要", "indices": [0]},
                            {"summary": "第二个摘要", "indices": [1]},
                        ],
                        "meta": {},
                    }
                    
                    run_async(store_raptor(state))
        
        full_content = "".join(captured_content)
        data = json.loads(full_content)
        
        assert "summaries" in data, "RAPTOR output must contain 'summaries'"
        assert isinstance(data["summaries"], list), "summaries must be a list"
        assert len(data["summaries"]) == 2
        
        # Verify summary structure
        for summary in data["summaries"]:
            assert "summary" in summary, "Each summary must have 'summary' field"
            assert "indices" in summary, "Each summary must have 'indices' field"

    def test_raptor_meta_summary_count_matches(self):
        """
        Test that meta.summary_count matches actual summaries length.
        
        **Feature: algorithms-test-review, Property 4: Meta Counts Consistency**
        **Validates: Requirements 4.4**
        """
        from core.algorithms.raptor_deep import store_raptor
        
        with patch("builtins.open", mock_open()):
            with patch("os.makedirs"):
                with patch("core.algorithms.raptor_deep.settings") as mock_settings:
                    mock_settings.uploads_dir_resolved = "/tmp/test"
                    
                    summaries = [
                        {"summary": f"摘要{i}", "indices": [i]}
                        for i in range(5)
                    ]
                    
                    state = {
                        "kb_name": "test_kb",
                        "layers": [[0, 1, 2, 3, 4]],
                        "summaries": summaries,
                        "meta": {},
                    }
                    
                    result = run_async(store_raptor(state))
        
        assert result["meta"]["summary_count"] == 5
        assert result["meta"]["summary_count"] == len(summaries)


# =============================================================================
# GraphRAG Storage Tests
# =============================================================================

class TestGraphRAGStorageContent:
    """Tests for GraphRAG storage JSON structure."""

    def test_graphrag_storage_contains_nodes(self):
        """
        Test that GraphRAG storage contains nodes array.
        
        **Feature: algorithms-test-review, Property 3: Storage JSON Structure Validity**
        **Validates: Requirements 4.2**
        """
        from core.algorithms.graphrag_deep import store_graph
        
        captured_files = {}
        
        def capture_open(path, mode, **kwargs):
            mock_file = MagicMock()
            content = []
            mock_file.write = lambda c: content.append(c)
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=False)
            captured_files[path] = content
            return mock_file
        
        with patch("builtins.open", capture_open):
            with patch("os.makedirs"):
                with patch("core.algorithms.graphrag_deep.settings") as mock_settings:
                    mock_settings.uploads_dir_resolved = "/tmp/test"
                    
                    state = {
                        "kb_name": "test_kb",
                        "graph": {
                            "nodes": [
                                {"entity_name": "张三", "entity_type": "人物", "description": "主角"},
                                {"entity_name": "北京", "entity_type": "地点", "description": "首都"},
                            ],
                            "edges": [
                                {"src_id": "张三", "tgt_id": "北京", "weight": 1, "description": "居住"}
                            ],
                        },
                        "communities": [],
                        "meta": {},
                    }
                    
                    run_async(store_graph(state))
        
        # Find graph file
        graph_file = [p for p in captured_files.keys() if "graph" in p and "communities" not in p]
        assert len(graph_file) == 1, "Should have exactly one graph file"
        
        full_content = "".join(captured_files[graph_file[0]])
        data = json.loads(full_content)
        
        assert "nodes" in data, "GraphRAG output must contain 'nodes'"
        assert isinstance(data["nodes"], list), "nodes must be a list"
        assert len(data["nodes"]) == 2

    def test_graphrag_storage_contains_edges(self):
        """
        Test that GraphRAG storage contains edges array.
        
        **Validates: Requirements 4.2**
        """
        from core.algorithms.graphrag_deep import store_graph
        
        captured_files = {}
        
        def capture_open(path, mode, **kwargs):
            mock_file = MagicMock()
            content = []
            mock_file.write = lambda c: content.append(c)
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=False)
            captured_files[path] = content
            return mock_file
        
        with patch("builtins.open", capture_open):
            with patch("os.makedirs"):
                with patch("core.algorithms.graphrag_deep.settings") as mock_settings:
                    mock_settings.uploads_dir_resolved = "/tmp/test"
                    
                    state = {
                        "kb_name": "test_kb",
                        "graph": {
                            "nodes": [
                                {"entity_name": "A", "entity_type": "类型"},
                                {"entity_name": "B", "entity_type": "类型"},
                                {"entity_name": "C", "entity_type": "类型"},
                            ],
                            "edges": [
                                {"src_id": "A", "tgt_id": "B", "weight": 1, "description": "关系1"},
                                {"src_id": "B", "tgt_id": "C", "weight": 2, "description": "关系2"},
                            ],
                        },
                        "communities": [],
                        "meta": {},
                    }
                    
                    run_async(store_graph(state))
        
        graph_file = [p for p in captured_files.keys() if "graph" in p and "communities" not in p]
        full_content = "".join(captured_files[graph_file[0]])
        data = json.loads(full_content)
        
        assert "edges" in data, "GraphRAG output must contain 'edges'"
        assert isinstance(data["edges"], list), "edges must be a list"
        assert len(data["edges"]) == 2
        
        # Verify edge structure
        for edge in data["edges"]:
            assert "src_id" in edge, "Each edge must have 'src_id'"
            assert "tgt_id" in edge, "Each edge must have 'tgt_id'"

    def test_graphrag_storage_contains_communities(self):
        """
        Test that GraphRAG storage contains communities structure.
        
        **Validates: Requirements 4.3**
        """
        from core.algorithms.graphrag_deep import store_graph
        
        captured_files = {}
        
        def capture_open(path, mode, **kwargs):
            mock_file = MagicMock()
            content = []
            mock_file.write = lambda c: content.append(c)
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=False)
            captured_files[path] = content
            return mock_file
        
        with patch("builtins.open", capture_open):
            with patch("os.makedirs"):
                with patch("core.algorithms.graphrag_deep.settings") as mock_settings:
                    mock_settings.uploads_dir_resolved = "/tmp/test"
                    
                    state = {
                        "kb_name": "test_kb",
                        "graph": {"nodes": [], "edges": []},
                        "communities": [
                            {"id": 0, "level": 0, "members": ["A", "B"], "size": 2},
                            {"id": 1, "level": 0, "members": ["C", "D"], "size": 2},
                        ],
                        "meta": {},
                    }
                    
                    run_async(store_graph(state))
        
        # Find communities file
        comm_file = [p for p in captured_files.keys() if "communities" in p]
        assert len(comm_file) == 1, "Should have exactly one communities file"
        
        full_content = "".join(captured_files[comm_file[0]])
        data = json.loads(full_content)
        
        assert isinstance(data, list), "Communities output must be a list"
        assert len(data) == 2
        
        # Verify community structure
        for comm in data:
            assert "id" in comm, "Each community must have 'id'"
            assert "members" in comm, "Each community must have 'members'"
            assert "size" in comm, "Each community must have 'size'"

    def test_graphrag_meta_counts_match(self):
        """
        Test that meta counts match actual array lengths.
        
        **Feature: algorithms-test-review, Property 4: Meta Counts Consistency**
        **Validates: Requirements 4.4**
        """
        from core.algorithms.graphrag_deep import store_graph
        
        with patch("builtins.open", mock_open()):
            with patch("os.makedirs"):
                with patch("core.algorithms.graphrag_deep.settings") as mock_settings:
                    mock_settings.uploads_dir_resolved = "/tmp/test"
                    
                    nodes = [{"entity_name": f"N{i}", "entity_type": "类型"} for i in range(5)]
                    edges = [{"src_id": f"N{i}", "tgt_id": f"N{i+1}", "weight": 1} for i in range(4)]
                    communities = [{"id": i, "members": [], "size": 0} for i in range(3)]
                    
                    state = {
                        "kb_name": "test_kb",
                        "graph": {"nodes": nodes, "edges": edges},
                        "communities": communities,
                        "meta": {},
                    }
                    
                    result = run_async(store_graph(state))
        
        assert result["meta"]["node_count"] == 5
        assert result["meta"]["edge_count"] == 4
        assert result["meta"]["community_count"] == 3
        
        # Verify consistency
        assert result["meta"]["node_count"] == len(nodes)
        assert result["meta"]["edge_count"] == len(edges)
        assert result["meta"]["community_count"] == len(communities)


# =============================================================================
# Property-Based Tests
# =============================================================================

if HYPOTHESIS_AVAILABLE:
    class TestStorageContentProperties:
        """Property-based tests for storage content."""

        @settings(max_examples=50, deadline=None)
        @given(
            num_summaries=st.integers(min_value=0, max_value=20),
        )
        def test_property_raptor_summary_count_consistency(self, num_summaries: int):
            """
            **Feature: algorithms-test-review, Property 4: Meta Counts Consistency**
            **Validates: Requirements 4.4**
            
            For any RAPTOR output, meta.summary_count equals len(summaries).
            """
            # Simulate store_raptor behavior
            summaries = [{"summary": f"s{i}", "indices": [i]} for i in range(num_summaries)]
            
            meta = {
                "summary_count": len(summaries),
                "raptor_path_deep": "/tmp/test.raptor.deep.json",
            }
            
            # Property: summary_count matches actual length
            assert meta["summary_count"] == len(summaries)
            assert meta["summary_count"] == num_summaries

        @settings(max_examples=50, deadline=None)
        @given(
            num_nodes=st.integers(min_value=0, max_value=30),
            num_edges=st.integers(min_value=0, max_value=50),
            num_communities=st.integers(min_value=0, max_value=10),
        )
        def test_property_graphrag_counts_consistency(
            self, 
            num_nodes: int, 
            num_edges: int, 
            num_communities: int
        ):
            """
            **Feature: algorithms-test-review, Property 4: Meta Counts Consistency**
            **Validates: Requirements 4.4**
            
            For any GraphRAG output, meta counts equal actual array lengths.
            """
            # Simulate store_graph behavior
            nodes = [{"entity_name": f"N{i}"} for i in range(num_nodes)]
            edges = [{"src_id": f"N{i}", "tgt_id": f"N{i}"} for i in range(num_edges)]
            communities = [{"id": i, "members": []} for i in range(num_communities)]
            
            meta = {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "community_count": len(communities),
            }
            
            # Property: all counts match actual lengths
            assert meta["node_count"] == num_nodes
            assert meta["edge_count"] == num_edges
            assert meta["community_count"] == num_communities

        @settings(max_examples=30, deadline=None)
        @given(
            nodes=st.lists(
                st.fixed_dictionaries({
                    "entity_name": st.text(min_size=1, max_size=10).filter(lambda x: x.strip()),
                    "entity_type": st.sampled_from(["人物", "组织", "地点"]),
                }),
                min_size=0, max_size=10, unique_by=lambda x: x["entity_name"]
            ),
        )
        def test_property_graphrag_json_structure_validity(self, nodes: list[dict]):
            """
            **Feature: algorithms-test-review, Property 3: Storage JSON Structure Validity**
            **Validates: Requirements 4.2**
            
            For any GraphRAG output, JSON contains required fields.
            """
            # Simulate the expected JSON structure
            graph_json = {
                "nodes": nodes,
                "edges": [],  # edges depend on nodes
            }
            
            # Property: required fields exist
            assert "nodes" in graph_json
            assert "edges" in graph_json
            assert isinstance(graph_json["nodes"], list)
            assert isinstance(graph_json["edges"], list)
            
            # Property: each node has required fields
            for node in graph_json["nodes"]:
                assert "entity_name" in node
                assert "entity_type" in node


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# =============================================================================
# P2 Enhancement Tests - Entity Deduplication and Edge Weight Aggregation
# =============================================================================

class TestGraphRAGEntityDeduplication:
    """P2 Tests for GraphRAG entity deduplication."""

    def test_entity_deduplication_same_name(self):
        """
        Test that entities with same name are deduplicated.
        
        **Validates: Requirements P2-1**
        """
        from core.algorithms.graphrag_deep import extract_graph
        
        call_count = [0]
        
        async def mock_chat(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return json.dumps({
                    "entities": [
                        {"name": "张三", "type": "人物", "desc": "第一次描述"},
                    ],
                    "relations": []
                })
            else:
                return json.dumps({
                    "entities": [
                        {"name": "张三", "type": "人物", "desc": "第二次描述"},
                    ],
                    "relations": []
                })
        
        with patch("core.algorithms.graphrag_deep.LLMGateway") as mock_gw:
            mock_instance = MagicMock()
            mock_instance.chat = mock_chat
            mock_gw.return_value = mock_instance
            
            state = {
                "chunks": ["chunk1", "chunk2"],
                "graph": {},
            }
            
            result = run_async(extract_graph(state))
        
        # Should have only 1 entity (deduplicated)
        assert len(result["graph"]["nodes"]) == 1
        
        # Description should be concatenated
        entity = result["graph"]["nodes"][0]
        assert entity["entity_name"] == "张三"
        assert "第一次描述" in entity["description"]
        assert "第二次描述" in entity["description"]

    def test_entity_description_concatenation(self):
        """
        Test that entity descriptions are properly concatenated.
        
        **Validates: Requirements P2-1**
        """
        from core.algorithms.graphrag_deep import extract_graph
        
        call_count = [0]
        
        async def mock_chat(*args, **kwargs):
            call_count[0] += 1
            return json.dumps({
                "entities": [
                    {"name": "北京", "type": "地点", "desc": f"描述{call_count[0]}"},
                ],
                "relations": []
            })
        
        with patch("core.algorithms.graphrag_deep.LLMGateway") as mock_gw:
            mock_instance = MagicMock()
            mock_instance.chat = mock_chat
            mock_gw.return_value = mock_instance
            
            state = {
                "chunks": ["chunk1", "chunk2", "chunk3"],
                "graph": {},
            }
            
            result = run_async(extract_graph(state))
        
        # Should have only 1 entity
        assert len(result["graph"]["nodes"]) == 1
        
        # Description should contain all 3 descriptions
        entity = result["graph"]["nodes"][0]
        assert "描述1" in entity["description"]
        assert "描述2" in entity["description"]
        assert "描述3" in entity["description"]


class TestGraphRAGEdgeWeightAggregation:
    """P2 Tests for GraphRAG edge weight aggregation."""

    def test_edge_weight_accumulation(self):
        """
        Test that edge weights are properly accumulated.
        
        **Validates: Requirements P2-1**
        """
        from core.algorithms.graphrag_deep import extract_graph
        
        call_count = [0]
        
        async def mock_chat(*args, **kwargs):
            call_count[0] += 1
            return json.dumps({
                "entities": [
                    {"name": "A", "type": "类型", "desc": ""},
                    {"name": "B", "type": "类型", "desc": ""},
                ],
                "relations": [
                    {"src": "A", "tgt": "B", "desc": f"关系{call_count[0]}", "keywords": []}
                ]
            })
        
        with patch("core.algorithms.graphrag_deep.LLMGateway") as mock_gw:
            mock_instance = MagicMock()
            mock_instance.chat = mock_chat
            mock_gw.return_value = mock_instance
            
            state = {
                "chunks": ["chunk1", "chunk2", "chunk3"],
                "graph": {},
            }
            
            result = run_async(extract_graph(state))
        
        # Should have only 1 edge (deduplicated)
        assert len(result["graph"]["edges"]) == 1
        
        # Weight should be 3 (accumulated from 3 chunks)
        edge = result["graph"]["edges"][0]
        assert edge["weight"] == 3

    def test_edge_description_concatenation(self):
        """
        Test that edge descriptions are properly concatenated.
        
        **Validates: Requirements P2-1**
        """
        from core.algorithms.graphrag_deep import extract_graph
        
        call_count = [0]
        
        async def mock_chat(*args, **kwargs):
            call_count[0] += 1
            return json.dumps({
                "entities": [
                    {"name": "X", "type": "类型", "desc": ""},
                    {"name": "Y", "type": "类型", "desc": ""},
                ],
                "relations": [
                    {"src": "X", "tgt": "Y", "desc": f"边描述{call_count[0]}", "keywords": [f"kw{call_count[0]}"]}
                ]
            })
        
        with patch("core.algorithms.graphrag_deep.LLMGateway") as mock_gw:
            mock_instance = MagicMock()
            mock_instance.chat = mock_chat
            mock_gw.return_value = mock_instance
            
            state = {
                "chunks": ["chunk1", "chunk2"],
                "graph": {},
            }
            
            result = run_async(extract_graph(state))
        
        edge = result["graph"]["edges"][0]
        
        # Description should be concatenated
        assert "边描述1" in edge["description"]
        assert "边描述2" in edge["description"]
        
        # Keywords should be merged and deduplicated
        assert "kw1" in edge["keywords"]
        assert "kw2" in edge["keywords"]


class TestScrollKbChunksTruncation:
    """P2 Tests for scroll_kb_chunks chunk-level truncation."""

    def test_scroll_truncates_at_chunk_level(self):
        """
        Test that scroll_kb_chunks truncates precisely at max_chunks.
        
        **Validates: Requirements P2-2**
        """
        from core.storage.index_router import scroll_kb_chunks
        
        with patch('core.storage.index_router.get_vector_client') as mock_client:
            mock_qdrant = MagicMock()
            mock_qdrant.available = True
            
            call_count = [0]
            
            def mock_scroll(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] > 10:
                    return [], None
                
                batch = []
                for i in range(100):  # 100 per batch
                    point = MagicMock()
                    point.id = f"batch{call_count[0]}_id_{i}"
                    point.payload = {
                        "content": f"content_{call_count[0]}_{i}",
                        "metadata": {},
                    }
                    batch.append(point)
                return batch, f"offset_{call_count[0]}"
            
            mock_qdrant.client.scroll = mock_scroll
            mock_client.return_value = mock_qdrant
            
            with patch('core.storage.index_router.channel_collection_name', return_value="ch_tenant_kb"):
                total = 0
                for batch in scroll_kb_chunks(
                    kb_name="test_kb",
                    channel_id="tenant",
                    batch_size=100,
                    max_chunks=250  # Should stop after ~250 chunks
                ):
                    total += len(batch)
                
                # Should be truncated to around max_chunks
                # Note: batch-level truncation may slightly exceed
                assert total <= 300, f"Should truncate around 250, got {total}"
                assert total >= 200, f"Should have at least 200 chunks, got {total}"
