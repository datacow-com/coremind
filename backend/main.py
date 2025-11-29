from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
from typing import List, Optional
from pydantic import BaseModel
import uuid
import asyncio
from datetime import datetime

from src.config import settings
from src.database import init_db, get_db
from src.models import Document, Conversation, Message
from src.langgraph_engine import RAGGraph
from src.visual_parser import VisualPDFLoader
from src.vector_store import VectorStore
from src.rag_state import RAGState, QueryRequest, ChatResponse

# Global instances
rag_graph: Optional[RAGGraph] = None
vector_store: Optional[VectorStore] = None
pdf_loader: Optional[VisualPDFLoader] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global rag_graph, vector_store, pdf_loader
    
    # Initialize database
    await init_db()
    
    # Initialize components
    vector_store = VectorStore()
    await vector_store.initialize()
    
    pdf_loader = VisualPDFLoader()
    
    rag_graph = RAGGraph(vector_store, pdf_loader)
    
    yield
    
    # Shutdown
    if vector_store:
        await vector_store.close()

app = FastAPI(
    title="OmniRAG API",
    description="Enterprise-grade RAG system with visual parsing",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create upload directory
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Pydantic models
class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    estimated_time: int

class DocumentStatusResponse(BaseModel):
    document_id: str
    filename: str
    processing_status: str
    processed_pages: int
    total_pages: int
    chunks_count: int

class ConversationCreateResponse(BaseModel):
    conversation_id: str
    title: str

# API Routes
@app.post("/api/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """Upload a PDF document for processing"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Generate unique document ID
    document_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{document_id}_{file.filename}")
    
    # Save file
    try:
        contents = await file.read()
        with open(file_path, 'wb') as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Create document record
    async with get_db() as db:
        document = Document(
            id=document_id,
            filename=file.filename,
            file_path=file_path,
            file_size=len(contents),
            content_hash=str(hash(contents)),
            upload_status="completed",
            processing_status="pending",
            total_pages=0  # Will be updated during processing
        )
        db.add(document)
        await db.commit()
    
    # Start background processing
    asyncio.create_task(process_document_async(document_id))
    
    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        status="processing",
        estimated_time=120  # 2 minutes estimated
    )

async def process_document_async(document_id: str):
    """Background task to process uploaded document"""
    try:
        async with get_db() as db:
            document = await db.get(Document, document_id)
            if not document:
                return
            
            # Process with VisualPDFLoader
            chunks = await pdf_loader.process_pdf(document.file_path)
            
            # Update document status
            document.processing_status = "processing"
            document.total_pages = len(set(chunk.page_number for chunk in chunks))
            document.processed_pages = document.total_pages
            
            # Store chunks in vector database
            await vector_store.add_document_chunks(document_id, chunks)
            
            document.processing_status = "completed"
            document.processed_at = datetime.utcnow()
            await db.commit()
            
    except Exception as e:
        async with get_db() as db:
            document = await db.get(Document, document_id)
            if document:
                document.processing_status = "failed"
                document.metadata = {"error": str(e)}
                await db.commit()

@app.get("/api/documents/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(document_id: str):
    """Get document processing status"""
    async with get_db() as db:
        document = await db.get(Document, document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return DocumentStatusResponse(
            document_id=document_id,
            filename=document.filename,
            processing_status=document.processing_status,
            processed_pages=document.processed_pages,
            total_pages=document.total_pages,
            chunks_count=0  # Will be calculated from vector store
        )

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: QueryRequest):
    """Process a chat query using RAG"""
    try:
        # Create or get conversation
        if not request.conversation_id:
            conversation_id = str(uuid.uuid4())
            async with get_db() as db:
                conversation = Conversation(id=conversation_id, title=request.query[:50])
                db.add(conversation)
                await db.commit()
        else:
            conversation_id = request.conversation_id
        
        # Save user message
        async with get_db() as db:
            user_message = Message(
                conversation_id=conversation_id,
                role="user",
                content=request.query
            )
            db.add(user_message)
            await db.commit()
        
        # Process query with RAG
        result = await rag_graph.process_query(request)
        
        # Save assistant message
        async with get_db() as db:
            assistant_message = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=result.answer,
                metadata={"sources": [s.dict() for s in result.sources]}
            )
            db.add(assistant_message)
            await db.commit()
        
        return ChatResponse(
            answer=result.answer,
            sources=result.sources,
            conversation_id=conversation_id,
            message_id=str(assistant_message.id)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.get("/api/conversations")
async def get_conversations():
    """Get list of conversations"""
    async with get_db() as db:
        conversations = await db.execute(
            select(Conversation).order_by(Conversation.updated_at.desc())
        )
        conversations = conversations.scalars().all()
        
        return {
            "conversations": [
                {
                    "id": conv.id,
                    "title": conv.title,
                    "last_message": conv.updated_at.isoformat(),
                    "message_count": len(conv.messages)
                }
                for conv in conversations
            ]
        }

@app.get("/api/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str):
    """Get messages for a conversation"""
    async with get_db() as db:
        conversation = await db.get(Conversation, conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return {
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "metadata": msg.metadata,
                    "created_at": msg.created_at.isoformat()
                }
                for msg in conversation.messages
            ]
        }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": "connected",
            "vector_store": "connected" if vector_store else "disconnected",
            "rag_graph": "ready" if rag_graph else "not_ready"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)