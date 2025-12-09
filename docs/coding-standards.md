# OmniRAG 编码规范

> **版本**: v2.0 | **最后更新**: 2025-12-08
> **基准**: [Google Style Guides](https://google.github.io/styleguide/)
> **适用范围**: 全工程 (Python/TypeScript/React/CSS/Shell/Docker)

---

## 目录

1. [通用原则](#1-通用原则)
2. [Python 编码规范 (Google Python Style)](#2-python-编码规范)
3. [TypeScript/JavaScript 编码规范 (Google TS Style)](#3-typescriptjavascript-编码规范)
4. [React 组件规范](#4-react-组件规范)
5. [CSS/样式规范](#5-css样式规范)
6. [API 设计规范](#6-api-设计规范)
7. [错误处理与日志规范](#7-错误处理与日志规范)
8. [测试规范](#8-测试规范)
9. [安全规范](#9-安全规范)
10. [Git 提交规范](#10-git-提交规范)
11. [代码审查清单](#11-代码审查清单)
12. [工具配置](#12-工具配置)

---

## 1. 通用原则

### 1.1 核心理念

| 原则 | 描述 |
|:-----|:-----|
| **可读性优先** | 代码首先是给人读的，其次才是给机器执行的 |
| **简洁性** | 最简单的实现往往是最好的实现 (KISS) |
| **一致性** | 保持与项目现有代码风格一致 |
| **可测试性** | 所有业务逻辑必须可单元测试 |
| **无副作用** | 函数应尽量是纯函数，副作用需显式声明 |

### 1.2 工程约束

```yaml
# 硬性约束 - 违反将阻止 CI
python_version: "3.11"
node_version: ">=18.0.0"
line_length: 100
indent: 4 (Python) / 2 (TS/JSON/YAML)
quotes: double (统一)
禁止:
  - 提交密钥/凭据
  - 使用 print() (用 logging)
  - 未使用的导入/变量
  - 裸 except
  - eval/exec
  - any 类型滥用
```

---

## 2. Python 编码规范

> 基准: [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)

### 2.1 命名规范

| 类型 | 规范 | 示例 |
|:-----|:-----|:-----|
| **模块** | snake_case, 简短 | `vector_store.py`, `kb_config.py` |
| **类** | PascalCase | `VectorStoreClient`, `IngestState` |
| **函数/方法** | snake_case | `get_vector_client()`, `embed_batch()` |
| **常量** | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT`, `DEFAULT_CHUNK_SIZE` |
| **变量** | snake_case | `chunk_size`, `kb_name` |
| **私有成员** | 单下划线前缀 | `_cache`, `_client` |
| **内部方法** | 单下划线前缀 | `_parse_response()` |
| **类型变量** | PascalCase 或 大写单字母 | `T`, `StateT`, `ConfigType` |

### 2.2 导入规范

```python
# ✅ 正确：分组排序，绝对导入
# 标准库
import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

# 第三方库
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# 项目内部
from core.state import IngestState, RetrievalState
from core.storage.vector_store import get_vector_client
from server.config import settings


# ❌ 错误
from typing import *  # 禁止通配符导入
import os, sys  # 禁止同行多导入
from core.storage.vector_store import get_vector_client, get_milvus_client, \
    get_qdrant_client, init_client  # 过长应换行
```

### 2.3 类型注解

```python
# ✅ 完整的类型注解
from typing import TypedDict, Optional, List, Dict, Any, Literal


class ChunkMetadata(TypedDict):
    """Chunk 元数据结构."""
    doc_id: str
    page_num: Optional[int]
    block_type: Literal["text", "table", "image"]


async def embed_texts(
    texts: List[str],
    model: str = "bge-m3",
    batch_size: int = 64,
) -> List[List[float]]:
    """批量文本向量化.

    Args:
        texts: 待向量化的文本列表.
        model: Embedding 模型名称.
        batch_size: 每批处理数量.

    Returns:
        向量列表，每个向量为 float 列表.

    Raises:
        EmbeddingError: 向量化失败时抛出.
    """
    ...


# ❌ 禁止
def process(data):  # 缺少类型注解
    ...

def get_config() -> Any:  # 避免 Any
    ...
```

### 2.4 文档字符串 (Docstrings)

```python
# Google 风格 Docstring
class VectorStoreClient:
    """向量存储客户端.

    提供 Qdrant/Milvus 的统一访问接口，支持 CRUD 操作.

    Attributes:
        url: 向量库连接 URL.
        timeout: 请求超时时间（秒）.

    Example:
        >>> client = VectorStoreClient("http://localhost:6333")
        >>> await client.search("query", top_k=10)
    """

    def __init__(self, url: str, timeout: int = 30) -> None:
        """初始化客户端.

        Args:
            url: 向量库 URL.
            timeout: 超时时间.
        """
        self.url = url
        self.timeout = timeout


def calculate_similarity(
    query_vector: List[float],
    doc_vectors: List[List[float]],
) -> List[float]:
    """计算查询向量与文档向量的相似度.

    Args:
        query_vector: 查询向量.
        doc_vectors: 文档向量列表.

    Returns:
        相似度分数列表，范围 [0, 1].

    Raises:
        ValueError: 向量维度不匹配.
    """
    ...
```

### 2.5 异步编程规范

```python
# ✅ 正确的异步模式
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx


class AsyncHttpClient:
    """异步 HTTP 客户端 (单例模式)."""

    _instance: Optional["AsyncHttpClient"] = None
    _client: Optional[httpx.AsyncClient] = None

    def __new__(cls) -> "AsyncHttpClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


# ✅ 并发执行
async def fetch_all(urls: List[str]) -> List[str]:
    """并发获取多个 URL 内容."""
    async with httpx.AsyncClient() as client:
        tasks = [client.get(url) for url in urls]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        return [r.text if not isinstance(r, Exception) else "" for r in responses]


# ❌ 禁止在异步函数中使用阻塞操作
async def bad_example():
    import requests  # 阻塞！
    response = requests.get(url)  # 应使用 httpx.AsyncClient
```

### 2.6 类设计规范

```python
# ✅ 单例模式 (线程安全)
import threading
from functools import lru_cache


class Singleton:
    """线程安全的单例基类."""

    _instance: Optional["Singleton"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance


# ✅ 使用 dataclass 或 Pydantic
from dataclasses import dataclass, field
from pydantic import BaseModel, ConfigDict


@dataclass
class ChunkData:
    """分块数据."""
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class KBConfigModel(BaseModel):
    """知识库配置 (Pydantic v2)."""
    model_config = ConfigDict(from_attributes=True)

    name: str
    chunk_size: int = 512
    chunk_overlap: int = 50
```

---

## 3. TypeScript/JavaScript 编码规范

> 基准: [Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html)

### 3.1 命名规范

| 类型 | 规范 | 示例 |
|:-----|:-----|:-----|
| **文件** | kebab-case | `chat-panel.tsx`, `use-ingest.ts` |
| **组件** | PascalCase | `ChatPanel`, `IngestProgress` |
| **函数** | camelCase | `fetchDocuments()`, `handleSubmit()` |
| **常量** | UPPER_SNAKE_CASE | `MAX_FILE_SIZE`, `API_BASE_URL` |
| **变量** | camelCase | `chunkSize`, `isLoading` |
| **类型/接口** | PascalCase | `ChatMessage`, `KBConfig` |
| **枚举** | PascalCase (成员 UPPER_SNAKE) | `Status.PENDING` |

### 3.2 类型定义

```typescript
// ✅ 接口定义
interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  citations?: Citation[];
}

interface Citation {
  docId: string;
  page: number;
  bbox?: BoundingBox;
  content: string;
}

// ✅ 类型别名
type MessageRole = "user" | "assistant" | "system";
type EventHandler<T> = (event: T) => void;

// ✅ 泛型
interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

async function fetchApi<T>(url: string): Promise<ApiResponse<T>> {
  const response = await fetch(url);
  return response.json();
}

// ❌ 禁止
let data: any;  // 禁止 any
const items = [];  // 缺少类型，应为 const items: Item[] = [];
```

### 3.3 函数规范

```typescript
// ✅ 箭头函数 (简单场景)
const formatDate = (date: Date): string => {
  return date.toISOString().split("T")[0];
};

// ✅ 普通函数 (需要 this 或复杂逻辑)
async function uploadFile(
  file: File,
  kbName: string,
  options?: UploadOptions,
): Promise<UploadResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("kb_name", kbName);

  const response = await fetch("/api/ingest/upload_run", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }

  return response.json();
}

// ✅ 参数解构
function createChunk({ content, metadata }: ChunkInput): Chunk {
  return {
    id: generateId(),
    content,
    metadata,
    createdAt: new Date(),
  };
}
```

### 3.4 异步处理

```typescript
// ✅ async/await
async function fetchDocuments(kbName: string): Promise<Document[]> {
  try {
    const response = await api.get<Document[]>(`/kb/${kbName}/documents`);
    return response.data;
  } catch (error) {
    if (error instanceof ApiError) {
      console.error(`API Error: ${error.status}`);
    }
    throw error;
  }
}

// ✅ SSE 处理
async function* streamChat(query: string): AsyncGenerator<ChatEvent> {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    body: JSON.stringify({ query }),
  });

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  while (reader) {
    const { done, value } = await reader.read();
    if (done) break;

    const lines = decoder.decode(value).split("\n");
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        yield JSON.parse(line.slice(6));
      }
    }
  }
}
```

---

## 4. React 组件规范

### 4.1 组件结构

```tsx
// ✅ 函数组件模板
import React, { useState, useCallback, useMemo } from "react";

interface ChatPanelProps {
  kbName: string;
  onMessageSent?: (message: string) => void;
  className?: string;
}

/**
 * 聊天面板组件.
 *
 * @example
 * <ChatPanel kbName="legal" onMessageSent={handleSent} />
 */
export function ChatPanel({
  kbName,
  onMessageSent,
  className,
}: ChatPanelProps): React.ReactElement {
  // 1. State
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // 2. Computed/Memoized values
  const sortedMessages = useMemo(
    () => [...messages].sort((a, b) => a.timestamp - b.timestamp),
    [messages],
  );

  // 3. Callbacks
  const handleSubmit = useCallback(async () => {
    if (!input.trim()) return;

    setIsLoading(true);
    try {
      await sendMessage(input);
      onMessageSent?.(input);
      setInput("");
    } finally {
      setIsLoading(false);
    }
  }, [input, onMessageSent]);

  // 4. Effects (minimal, extracted to hooks when complex)

  // 5. Render
  return (
    <div className={className}>
      <MessageList messages={sortedMessages} />
      <InputBox
        value={input}
        onChange={setInput}
        onSubmit={handleSubmit}
        disabled={isLoading}
      />
    </div>
  );
}
```

### 4.2 Hooks 规范

```tsx
// ✅ 自定义 Hook
import { useState, useEffect, useCallback } from "react";

interface UseIngestResult {
  progress: number;
  status: IngestStatus;
  error: Error | null;
  startIngest: (file: File) => Promise<void>;
}

export function useIngest(kbName: string): UseIngestResult {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<IngestStatus>("idle");
  const [error, setError] = useState<Error | null>(null);

  const startIngest = useCallback(async (file: File) => {
    setStatus("uploading");
    setError(null);

    try {
      const eventSource = new EventSource(
        `/api/ingest/upload_run/stream?kb_name=${kbName}`,
      );

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "progress") {
          setProgress(data.progress);
        } else if (data.type === "complete") {
          setStatus("complete");
          eventSource.close();
        }
      };

      eventSource.onerror = (e) => {
        setError(new Error("Ingest failed"));
        setStatus("error");
        eventSource.close();
      };
    } catch (e) {
      setError(e as Error);
      setStatus("error");
    }
  }, [kbName]);

  return { progress, status, error, startIngest };
}
```

### 4.3 Props 规范

```tsx
// ✅ Props 定义
interface ButtonProps {
  /** 按钮文字 */
  children: React.ReactNode;
  /** 按钮类型 */
  variant?: "primary" | "secondary" | "danger";
  /** 是否禁用 */
  disabled?: boolean;
  /** 是否加载中 */
  loading?: boolean;
  /** 点击回调 */
  onClick?: () => void;
  /** 自定义类名 */
  className?: string;
}

// ✅ 默认值使用解构
export function Button({
  children,
  variant = "primary",
  disabled = false,
  loading = false,
  onClick,
  className,
}: ButtonProps): React.ReactElement {
  return (
    <button
      className={`btn btn-${variant} ${className ?? ""}`}
      disabled={disabled || loading}
      onClick={onClick}
    >
      {loading ? <Spinner /> : children}
    </button>
  );
}
```

---

## 5. CSS/样式规范

### 5.1 命名规范 (BEM)

```css
/* Block__Element--Modifier */
.chat-panel { }
.chat-panel__header { }
.chat-panel__message--user { }
.chat-panel__message--assistant { }
.chat-panel__input { }
.chat-panel__input--disabled { }
```

### 5.2 CSS 变量

```css
/* 设计系统变量 */
:root {
  /* Colors */
  --color-primary: #3b82f6;
  --color-primary-hover: #2563eb;
  --color-secondary: #64748b;
  --color-success: #22c55e;
  --color-error: #ef4444;
  --color-warning: #f59e0b;

  /* Typography */
  --font-family: "Inter", -apple-system, BlinkMacSystemFont, sans-serif;
  --font-size-xs: 0.75rem;
  --font-size-sm: 0.875rem;
  --font-size-base: 1rem;
  --font-size-lg: 1.125rem;
  --font-size-xl: 1.25rem;

  /* Spacing */
  --spacing-1: 0.25rem;
  --spacing-2: 0.5rem;
  --spacing-4: 1rem;
  --spacing-6: 1.5rem;
  --spacing-8: 2rem;

  /* Border Radius */
  --radius-sm: 0.25rem;
  --radius-md: 0.375rem;
  --radius-lg: 0.5rem;
  --radius-full: 9999px;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1);

  /* Transitions */
  --transition-fast: 150ms ease;
  --transition-normal: 200ms ease;
}

/* 使用变量 */
.button {
  background: var(--color-primary);
  border-radius: var(--radius-md);
  padding: var(--spacing-2) var(--spacing-4);
  transition: background var(--transition-fast);
}

.button:hover {
  background: var(--color-primary-hover);
}
```

---

## 6. API 设计规范

### 6.1 RESTful 规范

```yaml
# 命名规范
GET    /api/kb                     # 列表
POST   /api/kb                     # 创建
GET    /api/kb/{name}              # 获取单个
PATCH  /api/kb/{name}              # 部分更新
DELETE /api/kb/{name}              # 删除
GET    /api/kb/{name}/documents    # 子资源列表

# 响应格式
Success:
  code: 0
  message: "ok"
  data: { ... }

Error:
  code: 40001  # 业务错误码
  message: "Knowledge base not found"
  detail: { ... }  # 可选的详细信息
```

### 6.2 SSE 事件规范

```typescript
// 事件类型定义
type SSEEventType =
  | "phase"      // 阶段开始/结束
  | "answer"     // 增量回答
  | "citation"   // 引用信息
  | "final"      // 最终结果
  | "error"      // 错误
  | "ping";      // 心跳

interface PhaseEvent {
  type: "phase";
  name: string;
  status: "start" | "end" | "fallback";
}

interface AnswerEvent {
  type: "answer";
  delta: string;
}

interface FinalEvent {
  type: "final";
  answer: string;
  citations: Citation[];
}

interface ErrorEvent {
  type: "error";
  code: number;
  message: string;
}
```

---

## 7. 错误处理与日志规范

### 7.1 Python 错误处理

```python
# ✅ 自定义异常层次
class OmniRAGError(Exception):
    """OmniRAG 基础异常."""
    pass


class ConfigurationError(OmniRAGError):
    """配置错误."""
    pass


class StorageError(OmniRAGError):
    """存储层错误."""
    pass


class EmbeddingError(OmniRAGError):
    """向量化错误."""
    pass


# ✅ 异常处理模式
async def embed_with_retry(
    texts: List[str],
    max_retries: int = 3,
) -> List[List[float]]:
    """带重试的向量化."""
    for attempt in range(max_retries):
        try:
            return await _do_embed(texts)
        except httpx.TimeoutException as e:
            if attempt == max_retries - 1:
                raise EmbeddingError(f"Embedding timeout after {max_retries} retries") from e
            await asyncio.sleep(2 ** attempt)
        except Exception as e:
            raise EmbeddingError(f"Embedding failed: {e}") from e
```

### 7.2 日志规范

```python
import logging
from core.utils.trace import set_span_attrs

# 模块级 logger
logger = logging.getLogger(__name__)


class Embedder:
    async def embed(self, texts: List[str]) -> List[List[float]]:
        logger.info("Starting embedding", extra={
            "text_count": len(texts),
            "model": self.model_name,
        })

        try:
            result = await self._do_embed(texts)
            logger.info("Embedding completed", extra={
                "text_count": len(texts),
                "vector_dim": len(result[0]) if result else 0,
            })
            set_span_attrs({
                "embedding.count": len(texts),
                "embedding.model": self.model_name,
            })
            return result
        except Exception as e:
            logger.error("Embedding failed", exc_info=True, extra={
                "text_count": len(texts),
                "error": str(e),
            })
            raise


# ❌ 禁止
print("Debug:", data)  # 使用 logger.debug
logger.info(f"Processing {secret_key}")  # 禁止记录敏感信息
```

---

## 8. 测试规范

### 8.1 Python 单元测试

```python
# tests/test_embedder.py
import pytest
from unittest.mock import AsyncMock, patch

from core.embedding.registry import get_embedder


class TestEmbedder:
    """Embedder 单元测试."""

    @pytest.fixture
    def mock_client(self):
        """Mock HTTP 客户端."""
        with patch("core.embedding.registry.httpx.AsyncClient") as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_embed_single_text(self, mock_client):
        """测试单文本向量化."""
        # Arrange
        mock_client.return_value.post = AsyncMock(
            return_value=Mock(json=lambda: {"embeddings": [[0.1, 0.2, 0.3]]})
        )
        embedder = get_embedder()

        # Act
        result = await embedder.embed(["hello world"])

        # Assert
        assert len(result) == 1
        assert len(result[0]) == 3

    @pytest.mark.asyncio
    async def test_embed_empty_list(self):
        """测试空列表输入."""
        embedder = get_embedder()
        result = await embedder.embed([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_timeout(self, mock_client):
        """测试超时重试."""
        mock_client.return_value.post = AsyncMock(
            side_effect=httpx.TimeoutException("timeout")
        )
        embedder = get_embedder()

        with pytest.raises(EmbeddingError, match="timeout"):
            await embedder.embed(["test"])
```

### 8.2 覆盖率要求

```yaml
# 覆盖率门槛
minimum_coverage: 80%

# 必须 100% 覆盖的模块
critical_modules:
  - core/state.py
  - core/storage/vector_store.py
  - server/auth.py
  - server/schemas.py

# 可豁免的模块
excluded:
  - "**/migrations/**"
  - "**/tests/**"
  - "scripts/**"
```

---

## 9. 安全规范

### 9.1 禁止清单

```python
# ❌ 绝对禁止
eval(user_input)
exec(user_input)
pickle.loads(untrusted_data)
yaml.load(data)  # 应使用 yaml.safe_load
subprocess.run(cmd, shell=True)
os.system(cmd)
__import__(user_input)

# ❌ 禁止硬编码凭据
API_KEY = "sk-xxxxx"  # 应使用环境变量

# ❌ 禁止 SQL 拼接
f"SELECT * FROM users WHERE id = {user_id}"  # 应使用参数化查询
```

### 9.2 安全最佳实践

```python
# ✅ 使用环境变量
import os
API_KEY = os.environ.get("API_KEY")

# ✅ 参数化查询
await db.execute("SELECT * FROM users WHERE id = $1", user_id)

# ✅ 安全的 YAML 加载
import yaml
data = yaml.safe_load(content)

# ✅ 路径安全
from pathlib import Path

def safe_path(base_dir: Path, user_path: str) -> Path:
    """安全的路径拼接，防止目录遍历."""
    result = (base_dir / user_path).resolve()
    if not str(result).startswith(str(base_dir.resolve())):
        raise ValueError("Path traversal detected")
    return result

# ✅ 密钥脱敏
def mask_secret(secret: str) -> str:
    """脱敏显示密钥."""
    if len(secret) <= 8:
        return "***"
    return f"{secret[:4]}...{secret[-4:]}"
```

---

## 10. Git 提交规范

### 10.1 Commit Message 格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 10.2 Type 定义

| Type | 描述 |
|:-----|:-----|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `style` | 代码格式 (不影响逻辑) |
| `refactor` | 重构 |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建/工具 |

### 10.3 示例

```
feat(retrieval): add RRF weight configuration

- Add vector_weight and keyword_weight to RetrievalState
- Update HybridRetriever to use configurable weights
- Default: vector=0.6, keyword=0.4

Closes #123
```

---

## 11. 代码审查清单

### 11.1 必查项

```markdown
## 功能
- [ ] 代码实现符合需求
- [ ] 边界条件已处理
- [ ] 错误场景已考虑

## 质量
- [ ] 无 lint 错误 (ruff, eslint)
- [ ] 类型检查通过 (mypy, tsc)
- [ ] 无安全告警 (bandit)
- [ ] 测试覆盖新增代码

## 规范
- [ ] 命名符合规范
- [ ] 注释/文档完整
- [ ] 无硬编码凭据
- [ ] 日志级别正确

## 性能
- [ ] 无明显性能问题
- [ ] 资源已正确释放
- [ ] 异步操作无阻塞
```

---

## 12. 工具配置

### 12.1 ruff.toml (Python)

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes
    "W",   # pycodestyle warnings
    "I",   # isort
    "B",   # flake8-bugbear
    "UP",  # pyupgrade
    "S",   # flake8-bandit
    "C4",  # flake8-comprehensions
    "SIM", # flake8-simplify
]
ignore = ["E501"]  # line too long (handled by formatter)

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### 12.2 .eslintrc.json (TypeScript)

```json
{
  "extends": [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended"
  ],
  "rules": {
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/explicit-function-return-type": "warn",
    "react/prop-types": "off",
    "react-hooks/rules-of-hooks": "error",
    "react-hooks/exhaustive-deps": "warn"
  }
}
```

### 12.3 mypy.ini

```ini
[mypy]
python_version = 3.11
strict = true
warn_return_any = true
warn_unused_configs = true
no_implicit_optional = true
disallow_untyped_defs = true

[mypy-tests.*]
disallow_untyped_defs = false
```

### 12.4 pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, types-redis]

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: [-c, pyproject.toml]

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
```

---

## 附录: 快速检查命令

```bash
# Python
ruff check .                    # Lint
ruff format .                   # Format
mypy .                          # Type check
bandit -r .                     # Security scan
pytest --cov=core --cov=server  # Test with coverage

# TypeScript
npm run lint                    # ESLint
npm run type-check              # TypeScript check
npm run test                    # Jest

# 全量检查
pre-commit run --all-files
```

---

*本规范基于 Google Style Guide，结合项目实际进行定制。如有疑问请联系技术负责人。*
