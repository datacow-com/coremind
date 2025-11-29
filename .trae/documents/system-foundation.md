# OmniRAG 系统基盘设计文档

## 1. 系统架构概览

### 1.1 架构图
```mermaid
graph TB
    subgraph "前端层"
        UI[React UI]
    end
    
    subgraph "API网关层"
        GW[FastAPI Gateway]
        LS[LangServe]
    end
    
    subgraph "业务逻辑层 - LangGraph"
        LG[LangGraph引擎]
        IN[Ingestion节点]
        RET[Retriever节点]
        GEN[Generation节点]
        VIZ[Visualization节点]
    end
    
    subgraph "数据处理层"
        VPL[VisualPDFLoader]
        VLM[视觉语言模型]
        MD[Markdown处理器]
    end
    
    subgraph "存储层"
        MILVUS[(Milvus向量数据库)]
        PG[(PostgreSQL)]
        S3[(对象存储)]
    end
    
    subgraph "LLM服务"
        GEMINI[Gemini 3]
        GPT4[GPT-4o]
    end
    
    UI --> GW
    GW --> LS
    LS --> LG
    LG --> IN
    LG --> RET
    LG --> GEN
    LG --> VIZ
    
    IN --> VPL
    VPL --> VLM
    VLM --> MD
    MD --> MILVUS
    
    RET --> MILVUS
    GEN --> GEMINI
    VIZ --> GPT4
    
    LG --> PG
    VPL --> S3
```

### 1.2 核心组件职责

| 组件 | 职责描述 |
|------|----------|
| **LangGraph引擎** | 编排整个RAG流程，管理状态流转，协调各节点执行 |
| **VisualPDFLoader** | 将PDF转换为图像，通过VLM提取结构化Markdown内容 |
| **Milvus** | 存储文档向量，支持高效的相似度检索 |
| **PostgreSQL** | 存储文档元数据、用户数据、对话历史、Agent状态 |
| **FastAPI** | 提供RESTful API接口，集成LangServe部署LangGraph |
| **LangServe** | 将LangGraph封装为可调用的服务接口 |

## 2. 状态设计

### 2.1 LangGraph状态定义
```typescript
interface RAGState {
    // 输入相关
    query: string;                    // 用户查询
    documents: Document[];             // 原始文档列表
    
    // 处理过程
    chunks: ProcessedChunk[];        // 处理后的文本块
    vectors: number[][];             // 向量表示
    
    // 检索结果
    retrieved_chunks: RetrievedChunk[]; // 检索到的相关块
    scores: number[];                 // 相似度分数
    
    // 生成结果
    context: string;                  // 拼接的上下文
    answer: string;                   // 生成的答案
    sources: Source[];                // 引用源信息
    
    // 状态管理
    step: 'ingestion' | 'retrieval' | 'generation' | 'complete';
    error?: string;                   // 错误信息
    metadata: Record<string, any>;    // 额外元数据
}

interface ProcessedChunk {
    id: string;
    content: string;
    page_num: number;
    doc_id: string;
    chunk_index: number;
    metadata: Record<string, any>;
}

interface RetrievedChunk extends ProcessedChunk {
    score: number;
    rerank_score?: number;
}
```

### 2.2 数据库Schema设计

#### 2.2.1 文档表
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    upload_status VARCHAR(20) DEFAULT 'pending',
    processing_status VARCHAR(20) DEFAULT 'pending',
    total_pages INTEGER,
    processed_pages INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_documents_upload_status ON documents(upload_status);
CREATE INDEX idx_documents_processing_status ON documents(processing_status);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);
```

#### 2.2.2 文档块表
```sql
CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    page_number INTEGER,
    vector_id VARCHAR(100), -- Milvus中的向量ID
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

CREATE INDEX idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_chunks_vector_id ON document_chunks(vector_id);
```

#### 2.2.3 对话历史表
```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    title VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(10) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_created_at ON messages(created_at DESC);
```

#### 2.2.4 Agent状态表（LangGraph Checkpointer）
```sql
CREATE TABLE checkpoint_writes (
    thread_id VARCHAR(100) NOT NULL,
    checkpoint_ns VARCHAR(100) DEFAULT '',
    checkpoint_id VARCHAR(100) NOT NULL,
    task_id VARCHAR(100) NOT NULL,
    idx INTEGER DEFAULT 0,
    channel VARCHAR(100) NOT NULL,
    type VARCHAR(100),
    value JSONB NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

CREATE TABLE checkpoints (
    thread_id VARCHAR(100) NOT NULL,
    checkpoint_ns VARCHAR(100) DEFAULT '',
    checkpoint_id VARCHAR(100) NOT NULL,
    parent_checkpoint_id VARCHAR(100),
    type VARCHAR(100),
    checkpoint JSONB NOT NULL,
    metadata JSONB DEFAULT '{}',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE INDEX idx_checkpoints_thread_id ON checkpoints(thread_id);
CREATE INDEX idx_checkpoints_checkpoint_id ON checkpoints(checkpoint_id);
```

## 3. 数据流设计

### 3.1 文档摄入流程
```mermaid
sequenceDiagram
    participant User
    participant API
    participant VPL as VisualPDFLoader
    participant VLM as 视觉语言模型
    participant Milvus
    participant PG as PostgreSQL
    
    User->>API: 上传PDF文件
    API->>PG: 创建文档记录
    API->>VPL: 调用处理流程
    VPL->>VPL: PDF转图像
    loop 每页图像
        VPL->>VLM: 发送图像
        VLM-->>VPL: 返回Markdown
        VPL->>VPL: 文本分块
        VPL->>Milvus: 存储向量
        VPL->>PG: 存储块信息
    end
    VPL-->>API: 处理完成
    API-->>User: 返回成功状态
```

### 3.2 问答流程
```mermaid
sequenceDiagram
    participant User
    participant API
    participant LG as LangGraph
    participant Milvus
    participant LLM
    participant PG as PostgreSQL
    
    User->>API: 发送查询
    API->>LG: 启动RAG流程
    LG->>Milvus: 向量检索
    Milvus-->>LG: 返回相关块
    LG->>PG: 获取块详情
    PG-->>LG: 返回块内容
    LG->>LG: 构建上下文
    LG->>LLM: 生成答案
    LLM-->>LG: 返回答案
    LG->>PG: 保存对话历史
    LG-->>API: 返回结果
    API-->>User: 显示答案
```

## 4. API设计

### 4.1 RESTful API

#### 文档管理
```
POST /api/documents/upload
功能：上传PDF文档
请求：multipart/form-data
响应：
{
    "document_id": "uuid",
    "filename": "example.pdf",
    "status": "processing",
    "estimated_time": 120
}

GET /api/documents/{document_id}/status
功能：查询文档处理状态
响应：
{
    "document_id": "uuid",
    "filename": "example.pdf",
    "processing_status": "completed",
    "processed_pages": 10,
    "total_pages": 10,
    "chunks_count": 45
}

DELETE /api/documents/{document_id}
功能：删除文档及其相关数据
```

#### 问答接口
```
POST /api/chat
功能：发送查询并获取答案
请求：
{
    "query": "什么是LangGraph?",
    "conversation_id": "uuid", // 可选
    "document_ids": ["uuid"], // 可选，指定文档范围
    "top_k": 5, // 检索数量
    "temperature": 0.7
}

响应：
{
    "answer": "LangGraph是...",
    "sources": [
        {
            "chunk_id": "uuid",
            "content": "相关文本片段",
            "score": 0.89,
            "document_name": "文档1.pdf",
            "page_number": 3
        }
    ],
    "conversation_id": "uuid",
    "message_id": "uuid"
}
```

#### 对话管理
```
GET /api/conversations
功能：获取用户对话列表
响应：
{
    "conversations": [
        {
            "id": "uuid",
            "title": "LangGraph相关问题",
            "last_message": "2024-01-15T10:30:00Z",
            "message_count": 15
        }
    ]
}

GET /api/conversations/{conversation_id}/messages
功能：获取对话历史
```

### 4.2 LangGraph服务接口
```python
from langserve import add_routes
from langgraph.graph import StateGraph

# 创建LangGraph应用
graph = StateGraph(RAGState)
graph.add_node("ingest", ingestion_node)
graph.add_node("retrieve", retrieval_node)
graph.add_node("generate", generation_node)

# 添加路由
app = FastAPI()
add_routes(app, graph, path="/rag")

# 调用方式：POST /rag/invoke
# 请求体：{"input": {"query": "问题", "document_ids": []}}
```

## 5. 非功能性需求

### 5.1 性能要求
- **响应时间**：单次问答响应时间 < 3秒
- **并发处理**：支持100个并发请求
- **吞吐量**：文档处理速度 > 10页/分钟
- **向量检索**：单次检索时间 < 100ms

### 5.2 可扩展性
- **水平扩展**：支持多实例部署，通过负载均衡分发请求
- **数据分片**：Milvus支持集合分片，PostgreSQL支持分区表
- **缓存策略**：实现多级缓存（Redis + 应用内存）

### 5.3 可靠性
- **容错机制**：节点失败自动重试，最大重试次数3次
- **数据备份**：每日自动备份数据库，保留7天
- **监控告警**：关键指标异常时发送告警

### 5.4 可维护性
- **日志规范**：统一日志格式，包含trace_id
- **健康检查**：提供/health接口，检查各组件状态
- **配置管理**：支持环境变量和配置文件热加载

## 6. 安全设计

### 6.1 认证授权
```python
# JWT Token验证
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### 6.2 数据安全
- **敏感信息加密**：数据库连接信息、API密钥使用AES加密
- **传输加密**：所有API通信使用HTTPS
- **文件安全**：上传文件进行病毒扫描，限制文件类型和大小

### 6.3 访问控制
```sql
-- 行级安全策略
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_documents ON documents
    FOR ALL TO authenticated
    USING (user_id = auth.uid());

-- 权限控制
GRANT SELECT ON documents TO anon;
GRANT ALL ON documents TO authenticated;
```

## 7. 部署架构

### 7.1 容器化部署
```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: ./api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/omnirag
      - MILVUS_URI=milvus:19530
    depends_on:
      - postgres
      - milvus
      
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: omnirag
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
      
  milvus:
    image: milvusdb/milvus:latest
    ports:
      - "19530:19530"
    volumes:
      - milvus_data:/var/lib/milvus
```

### 7.2 环境配置
```bash
# .env.production
DATABASE_URL=postgresql://user:pass@prod-db:5432/omnirag
MILVUS_URI=http://milvus-cluster:19530
GEMINI_API_KEY=${GEMINI_API_KEY}
GPT4_API_KEY=${GPT4_API_KEY}
SECRET_KEY=${SECRET_KEY}
REDIS_URL=redis://redis:6379
```

### 7.3 监控运维
- **Prometheus**：收集应用指标
- **Grafana**：可视化监控面板
- **ELK Stack**：日志收集和分析
- **Kubernetes**：容器编排和自动扩缩容

## 8. 核心算法设计

### 8.1 VisualPDFLoader算法
```python
class VisualPDFLoader:
    def __init__(self, vlm_model: str = "gemini-pro-vision"):
        self.vlm = load_vlm_model(vlm_model)
        
    async def process_pdf(self, pdf_path: str) -> List[DocumentChunk]:
        # 1. PDF转图像
        images = await self._pdf_to_images(pdf_path)
        
        chunks = []
        for i, image in enumerate(images):
            # 2. VLM提取结构化内容
            markdown = await self._extract_markdown(image)
            
            # 3. 文本分块
            text_chunks = self._chunk_text(markdown)
            
            for j, chunk in enumerate(text_chunks):
                chunk_obj = DocumentChunk(
                    content=chunk,
                    page_number=i + 1,
                    chunk_index=j,
                    metadata={"type": "visual", "confidence": 0.95}
                )
                chunks.append(chunk_obj)
                
        return chunks
```

### 8.2 检索重排序算法
```python
async def retrieve_and_rerank(
    query: str, 
    top_k: int = 10,
    rerank_k: int = 5
) -> List[RetrievedChunk]:
    # 1. 向量检索
    initial_results = await milvus_search(query, top_k=top_k)
    
    # 2. 重排序
    reranked = await reranker.rerank(query, initial_results[:rerank_k])
    
    # 3. 融合分数
    final_results = []
    for i, result in enumerate(reranked):
        result.rerank_score = result.score * 0.7 + reranked[i].score * 0.3
        final_results.append(result)
        
    return sorted(final_results, key=lambda x: x.rerank_score, reverse=True)
```

这个系统基盘设计为OmniRAG提供了完整的技术架构基础，确保系统具备高性能、高可用性和良好的可扩展性。