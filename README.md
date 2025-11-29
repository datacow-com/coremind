# OmniRAG: Enterprise-Grade RAG System

OmniRAG is a cutting-edge Retrieval-Augmented Generation (RAG) system that combines the deep parsing precision of RAGFlow, the orchestration capabilities of Dify, and the deployment experience of MaxKB. Built with LangGraph as the architectural backbone, it features visual PDF parsing as its core innovation.

## 🚀 Key Features

- **Visual PDF Parsing**: Core innovation using Gemini Vision for understanding document layout and visual elements
- **LangGraph Orchestration**: State-of-the-art workflow management for complex RAG pipelines
- **Hybrid Retrieval**: Combines vector search and keyword search with intelligent reranking
- **Web Search Integration**: Augments knowledge with real-time web search capabilities
- **Enterprise-Ready**: Docker containerization, PostgreSQL persistence, Milvus vector database

## 🏗️ Architecture (ACIS)

- **L1 Acquisition**: VisualPDFLoader processes documents through visual understanding
- **L2 Cognition**: LangGraph orchestrates RAG workflows with state management
- **L3 Interaction**: React-based UI with real-time chat and PDF preview
- **L4 Service**: FastAPI backend with comprehensive RESTful endpoints

## 📋 Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)
- API Keys:
  - Google Gemini API Key
  - Serper API Key (for web search)
  - Optional: OpenAI/Anthropic API Keys

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd OmniRAG
```

### 2. Environment Configuration

Create a `.env` file in the root directory:

```env
# LLM API Keys
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Web Search API Key
SERPER_API_KEY=your_serper_api_key_here

# Database Configuration
DATABASE_URL=postgresql://omnirag:omnirag_password@postgres:5432/omnirag

# Vector Store Configuration
MILVUS_HOST=milvus
MILVUS_PORT=19530
```

### 3. Docker Deployment

```bash
docker-compose up -d
```

The application will be available at:
- Frontend: http://localhost
- Backend API: http://localhost/api
- Milvus: localhost:19530
- PostgreSQL: localhost:5432

### 4. Local Development

**Backend Setup:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend Setup:**
```bash
cd frontend
npm install
npm run dev
```

## 📖 Usage

### 1. Upload Documents

Navigate to the Chat page and upload PDF documents. The system will:
- Process documents visually using Gemini Vision
- Extract text, tables, and layout information
- Generate embeddings and store in Milvus
- Create searchable chunks with metadata

### 2. Chat with Documents

Ask questions about your uploaded documents:
- The system retrieves relevant chunks using hybrid search
- Grades document relevance automatically
- Generates answers with source citations
- Falls back to web search when needed
- Checks for hallucinations in responses

### 3. Vector Store Management

Use the Vector Store page to:
- View collection statistics
- Perform vector searches
- Monitor embedding quality
- Manage document chunks

### 4. Settings Configuration

Configure system settings:
- LLM provider and model selection
- Vector store parameters
- Web search settings
- API key management

## 🔧 Configuration

### Backend Configuration

The backend uses Pydantic settings with environment variables:

```python
# backend/src/config.py
class Settings(BaseSettings):
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")
    database_url: str = Field(..., env="DATABASE_URL")
    milvus_host: str = Field("localhost", env="MILVUS_HOST")
    milvus_port: int = Field(19530, env="MILVUS_PORT")
```

### Frontend Configuration

The frontend uses environment variables for API endpoints:

```typescript
// frontend/src/config.ts
export const API_BASE_URL = process.env.VITE_API_BASE_URL || '/api'
export const WS_BASE_URL = process.env.VITE_WS_BASE_URL || '/ws'
```

## 🏛️ System Components

### LangGraph Workflow

The RAG pipeline is orchestrated through LangGraph with the following nodes:

1. **retrieve**: Hybrid retrieval from Milvus and keyword search
2. **grade_documents**: Relevance grading of retrieved documents
3. **generate**: Answer generation using LLM
4. **web_search**: Web search fallback for insufficient context
5. **hallucination_check**: Hallucination detection in generated answers

### Visual PDF Parser

The core innovation processes PDFs visually:

```python
# backend/src/visual_parser.py
class VisualPDFLoader:
    async def _process_pdf_visually(self, pdf_path: str) -> List[DocumentChunk]:
        # Convert PDF to images
        # Analyze layout with Gemini Vision
        # Extract structured content
        # Generate embeddings
```

### Database Schema

PostgreSQL stores:
- Documents with processing status
- Conversations and messages
- User interactions and feedback
- System configuration and settings

## 🔒 Security

- API key management through environment variables
- SQL injection prevention through SQLAlchemy ORM
- Input validation and sanitization
- CORS configuration for frontend-backend communication
- Docker security best practices

## 📊 Monitoring

The system includes:
- Health check endpoints
- Processing status tracking
- Error logging and reporting
- Performance metrics collection
- Vector store statistics

## 🧪 Testing

Run tests for both frontend and backend:

```bash
# Backend tests
cd backend
pytest tests/

# Frontend tests
cd frontend
npm run test
```

## 🚀 Deployment

### Production Deployment

1. **SSL/TLS Setup**: Configure nginx with SSL certificates
2. **Environment Variables**: Set production API keys and database URLs
3. **Database Backups**: Configure PostgreSQL backup strategy
4. **Monitoring**: Set up application monitoring and alerting
5. **Scaling**: Configure horizontal scaling for high availability

### Cloud Deployment

The system supports deployment on:
- AWS ECS/Fargate
- Google Cloud Run
- Azure Container Instances
- Kubernetes clusters

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- LangGraph team for the orchestration framework
- Milvus team for the vector database
- Google Gemini team for the vision capabilities
- The open-source community for various dependencies

## 📞 Support

For support and questions:
- Create an issue in the GitHub repository
- Check the documentation in the `/docs` directory
- Review the system logs for troubleshooting

---

**OmniRAG**: Where visual understanding meets intelligent retrieval.