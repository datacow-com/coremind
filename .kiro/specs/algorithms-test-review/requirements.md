# Algorithms 测试目录深度评审报告

## 审查背景

**审查范围**: `tests/core/algorithms/` 目录
**实现代码**: `core/algorithms/` 目录及 `core/storage/index_router.py`
**审查日期**: 2025-12-13

---

## 1. 执行摘要

### 1.1 总体评估

| 维度            | 评分 | 说明                                                                    |
| :-------------- | :--: | :---------------------------------------------------------------------- |
| MindMap 覆盖率  | 30%  | 仅测试 extract_topics/build_mindmap，collect_texts/store_mindmap 未覆盖 |
| Community 检测  | 40%  | fallback 测试为空操作，happy path 断言过弱                              |
| Light 变体验证  | 60%  | channel_id 验证完整，kb_name 验证缺失                                   |
| 存储路径验证    | 50%  | 仅验证路径字符串，未验证 JSON 内容结构                                  |
| LLM/JSON 健壮性 | 45%  | 部分流程有异常测试，MindMap/RAPTOR 缺失                                 |
| Channel 隔离    | 55%  | 验证 chunk 文本，未验证 graph nodes/edges                               |

### 1.2 问题统计

| 优先级                 | 数量 | 说明       |
| :--------------------- | :--: | :--------- |
| P0 (测试无效/越权风险) |  2   | 需立即修复 |
| P1 (覆盖缺失/断言弱)   |  6   | 本迭代修复 |
| P2 (增强/边界)         |  4   | 下迭代规划 |

---

## 2. 详细发现

### 2.1 MindMap 覆盖率极低 (P1)

**文件**: `tests/core/algorithms/test_algorithms_real_docs.py`
**问题描述**:
MindMap 测试仅覆盖 `extract_topics` 和 `build_mindmap`，以下关键函数未测试：

- `collect_texts`: 从 `list_all_meta` 收集文本，无 channel 过滤
- `store_mindmap`: 文件写入、路径生成、元数据记录

**影响**:

- `collect_texts` 使用 `list_all_meta()` 无 channel 参数，存在跨租户数据泄露风险
- `store_mindmap` 的文件写入失败、路径冲突等场景未验证

**代码证据** (`core/algorithms/mindmap_light.py:35-40`):

```python
async def collect_texts(state: MindMapState) -> MindMapState:
    ms = list_all_meta()  # 无 channel_id 过滤!
    state["chunks"] = [
        str(m.get("content") or "") for m in ms if str(m.get("content") or "").strip()
    ]
    return state
```

---

### 2.2 Community Fallback 测试为空操作 (P0)

**文件**: `tests/core/algorithms/test_raptor_graphrag_comprehensive.py`
**函数**: `test_graphrag_community_fallback`, `test_detect_communities_fallback_without_networkx`
**问题描述**:
两个 fallback 测试的断言为 `assert len(result["communities"]) >= 0`，这永远为真，无法验证：

1. fallback 是否返回单一社区
2. 社区结构是否包含所有节点
3. 社区元数据是否正确

**代码证据** (`test_raptor_graphrag_comprehensive.py:650-660`):

```python
async def test_detect_communities_fallback_without_networkx(self):
    # ...
    result = await detect_communities(state)
    assert len(result["communities"]) >= 0  # 永远为真!
```

**预期行为** (`core/algorithms/graphrag_deep.py:130-140`):

```python
# Fallback: treat all nodes as one community
state["communities"] = [
    {
        "id": 0,
        "level": 0,
        "members": [n["entity_name"] for n in nodes],
        "size": len(nodes),
        "summary": "",
    }
]
```

---

### 2.3 NetworkX Happy Path 断言过弱 (P1)

**文件**: `tests/core/algorithms/test_algorithms_real_docs.py`
**函数**: `test_community_detection_with_networkx`
**问题描述**:
测试仅断言 `len(communities) >= 1`，未验证：

1. 社区分区是否正确（已知图应产生确定性分区）
2. `LOUVAIN_RESOLUTION` 环境变量是否生效
3. `top_entities` 计算是否正确

**影响**: Louvain 算法参数变更或 top-entity 计算错误无法被检测

---

### 2.4 Light 变体缺少 kb_name 验证 (P1)

**文件**: `tests/core/algorithms/test_raptor_graphrag_comprehensive.py`
**问题描述**:
RAPTOR/GraphRAG Light 的 `light_collect` 测试验证了 `channel_id` 必填，但未验证 `kb_name` 必填。

**代码证据** (`core/algorithms/raptor_deep.py:30-35`):

```python
if not kb_name:
    raise ValueError("kb_name is required for RAPTOR processing")
```

**缺失测试**: Light 版本调用 deep 版本的 `collect_texts`，应继承 kb_name 验证

---

### 2.5 存储路径断言浅层 (P1)

**文件**: `tests/core/algorithms/test_raptor_graphrag_comprehensive.py`
**函数**: `test_store_creates_correct_path`, `test_store_includes_summary_count`
**问题描述**:
测试仅验证：

- 路径字符串包含 kb_name
- meta 包含 summary_count

未验证：

- 写入的 JSON 内容结构是否正确
- summaries 数组元素是否包含必需字段
- graph nodes/edges 结构是否符合预期

**影响**: `store_raptor`/`store_graph` 的序列化逻辑错误无法被检测

---

### 2.6 MindMap/RAPTOR LLM 健壮性未测试 (P1)

**文件**: `tests/core/algorithms/test_algorithms_real_docs.py`
**问题描述**:
GraphRAG 有 `test_llm_error_handling` 测试 LLM 异常，但：

- MindMap `extract_topics` 的 LLM 异常未测试
- RAPTOR `summarize_groups` 的 LLM 异常未测试
- 两者的 JSON 解析失败场景未测试

**代码证据** (`core/algorithms/mindmap_light.py:55-60`):

```python
try:
    out = await gw.chat(prompt=prompt, context=context)
    data = json.loads(out) if out else {}  # JSON 解析可能失败
    state["topics"] = data.get("topics", [])
except Exception:
    state["topics"] = []  # 静默失败，未测试
```

---

### 2.7 Channel 隔离仅验证 Chunk 文本 (P0)

**文件**: `tests/core/algorithms/test_algorithms_real_docs.py`
**函数**: `test_graphrag_light_channel_filtering`
**问题描述**:
测试验证收集的 chunk 文本包含特定字符串，但未验证：

1. 最终 graph 的 nodes 是否仅来自指定 channel
2. 最终 graph 的 edges 是否仅连接指定 channel 的实体
3. 混合 channel 数据时是否正确过滤

**影响**: 如果 `extract_graph` 处理了错误 channel 的数据，测试无法检测

---

### 2.8 GraphRAG 实体去重/边权重聚合未测试 (P2)

**文件**: `tests/core/algorithms/test_raptor_graphrag_comprehensive.py`
**函数**: `test_extract_graph_entities`
**问题描述**:
测试仅验证实体和关系数量，未验证：

1. 相同实体名称是否正确去重
2. 相同边是否正确聚合权重
3. description 是否正确拼接

**代码证据** (`core/algorithms/graphrag_deep.py:85-95`):

```python
# 实体去重逻辑
cur = nodes.setdefault(nm, {...})
if desc:
    cur["description"] = cur.get("description", "") + "\n" + desc

# 边权重聚合
cur["weight"] = int(cur.get("weight") or 0) + 1
```

---

### 2.9 scroll_kb_chunks batch 级别截断问题 (P2)

**文件**: `tests/core/algorithms/test_raptor_graphrag_comprehensive.py`
**函数**: `test_scroll_respects_max_chunks_limit`
**问题描述**:
测试注释指出 "截断发生在 batch 级别，不是 chunk 级别"，断言为 `total <= 150`（max_chunks=100）。
这表明实现可能超过 max_chunks 限制。

**影响**: 大库处理时可能消耗超预期内存

---

### 2.10 MindMap 无 Channel 感知 (P2)

**文件**: `core/algorithms/mindmap_light.py`
**问题描述**:
`MindMapState` 无 `channel_id` 字段，`collect_texts` 使用 `list_all_meta()` 无过滤。
这是设计缺陷，但测试也未覆盖此场景。

**影响**: MindMap 在多租户环境下存在数据泄露风险

---

## 3. 建议新增测试

### 3.1 MindMap 完整覆盖 (P1)

```markdown
### Requirement 1

**User Story:** As a developer, I want MindMap collect_texts and store_mindmap to be tested, so that I can ensure data collection and persistence work correctly.

#### Acceptance Criteria

1. WHEN collect_texts is called THEN the system SHALL collect texts from list_all_meta
2. WHEN store_mindmap is called THEN the system SHALL write JSON to correct path
3. WHEN store_mindmap is called THEN the system SHALL update meta with mindmap_path and topic_count
4. IF storage write fails THEN the system SHALL handle error gracefully
5. WHEN collect_texts returns empty THEN the system SHALL produce empty mindmap
```

### 3.2 Community Detection 精确验证 (P0)

```markdown
### Requirement 2

**User Story:** As a developer, I want community detection tests to verify exact fallback structure, so that I can ensure graceful degradation works correctly.

#### Acceptance Criteria

1. WHEN networkx is unavailable THEN the system SHALL return single community containing all nodes
2. WHEN networkx is unavailable THEN the community SHALL have correct size equal to node count
3. WHEN networkx is available THEN the system SHALL detect correct number of communities for known graph
4. WHEN LOUVAIN_RESOLUTION env is set THEN the system SHALL use specified resolution value
5. WHEN communities are detected THEN the system SHALL compute correct top_entities by degree
```

### 3.3 Light 变体 kb_name 验证 (P1)

```markdown
### Requirement 3

**User Story:** As a developer, I want Light variants to validate kb_name, so that I can ensure required inputs are enforced.

#### Acceptance Criteria

1. WHEN RAPTOR Light is called without kb_name THEN the system SHALL raise ValueError
2. WHEN GraphRAG Light is called without kb_name THEN the system SHALL raise ValueError
3. WHEN Light variants apply defaults THEN the system SHALL set entity_types correctly
```

### 3.4 存储内容结构验证 (P1)

```markdown
### Requirement 4

**User Story:** As a developer, I want storage tests to validate JSON content structure, so that I can ensure serialization is correct.

#### Acceptance Criteria

1. WHEN store_raptor writes JSON THEN the content SHALL contain layers and summaries arrays
2. WHEN store_graph writes JSON THEN the content SHALL contain nodes and edges arrays
3. WHEN store_graph writes communities THEN the content SHALL contain id, members, size fields
4. WHEN meta is updated THEN the counts SHALL match actual data
```

### 3.5 LLM/JSON 健壮性测试 (P1)

```markdown
### Requirement 5

**User Story:** As a developer, I want LLM error handling tests for all algorithms, so that I can ensure graceful degradation.

#### Acceptance Criteria

1. WHEN MindMap extract_topics receives LLM error THEN the system SHALL return empty topics
2. WHEN MindMap extract_topics receives malformed JSON THEN the system SHALL return empty topics
3. WHEN RAPTOR summarize_groups receives LLM error THEN the system SHALL return empty summary
4. WHEN GraphRAG extract_graph receives malformed JSON THEN the system SHALL skip that chunk
```

### 3.6 Channel 隔离端到端验证 (P0)

```markdown
### Requirement 6

**User Story:** As a developer, I want channel isolation tests to verify graph output, so that I can ensure no cross-tenant data leakage.

#### Acceptance Criteria

1. WHEN mixed-channel chunks are processed THEN the graph nodes SHALL only contain entities from specified channel
2. WHEN mixed-channel chunks are processed THEN the graph edges SHALL only connect entities from specified channel
3. WHEN channel_id is specified THEN the final output SHALL not contain any data from other channels
```

---

## 4. 修复优先级清单

### 立即修复 (P0)

1. [ ] P0-1: Community fallback 测试添加精确断言
2. [ ] P0-2: Channel 隔离测试验证 graph nodes/edges

### 本迭代修复 (P1)

3. [ ] P1-1: MindMap collect_texts/store_mindmap 测试
4. [ ] P1-2: NetworkX happy path 添加确定性分区验证
5. [ ] P1-3: Light 变体添加 kb_name 验证测试
6. [ ] P1-4: 存储测试验证 JSON 内容结构
7. [ ] P1-5: MindMap/RAPTOR LLM 异常测试
8. [ ] P1-6: MindMap/RAPTOR JSON 解析失败测试

### 下迭代规划 (P2)

9. [ ] P2-1: GraphRAG 实体去重/边权重聚合测试
10. [ ] P2-2: scroll_kb_chunks chunk 级别截断验证
11. [ ] P2-3: MindMap channel 感知设计评估
12. [ ] P2-4: LOUVAIN_RESOLUTION 环境变量测试

---

## 5. 验证计划

### 5.1 单元测试命令

```bash
# 运行现有 algorithms 测试
pytest tests/core/algorithms/ -v

# 运行新增测试（修复后）
pytest tests/core/algorithms/test_mindmap_comprehensive.py -v
pytest tests/core/algorithms/test_community_detection.py -v
pytest tests/core/algorithms/test_channel_isolation_e2e.py -v
```

### 5.2 覆盖率目标

| 模块             | 当前覆盖率 | 目标覆盖率 |
| :--------------- | :--------: | :--------: |
| mindmap_light.py |    ~30%    |    80%     |
| graphrag_deep.py |    ~60%    |    85%     |
| raptor_deep.py   |    ~55%    |    80%     |
| index_router.py  |    ~50%    |    75%     |

---

## 6. 附录：文件引用索引

| 文件路径                                                      | 审查状态 | 主要问题               |
| :------------------------------------------------------------ | :------: | :--------------------- |
| `tests/core/algorithms/test_algorithms_real_docs.py`          |    ✅    | P1-1, P1-2, P1-5, P0-2 |
| `tests/core/algorithms/test_raptor_graphrag_comprehensive.py` |    ✅    | P0-1, P1-3, P1-4, P2-1 |
| `core/algorithms/mindmap_light.py`                            |    ✅    | P2-3 (设计问题)        |
| `core/algorithms/graphrag_deep.py`                            |    ✅    | -                      |
| `core/algorithms/raptor_deep.py`                              |    ✅    | -                      |
| `core/algorithms/graphrag_light.py`                           |    ✅    | -                      |
| `core/algorithms/raptor_light.py`                             |    ✅    | -                      |
| `core/storage/index_router.py`                                |    ✅    | P2-2                   |
