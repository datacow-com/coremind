from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, JSON, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    content_hash = Column(String(64), unique=True, nullable=False)
    upload_status = Column(String(20), default="pending")
    processing_status = Column(String(20), default="pending")
    total_pages = Column(Integer)
    processed_pages = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True))
    metadata = Column(JSON, default=dict)
    
    # Relationships
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    page_number = Column(Integer)
    vector_id = Column(String(100))
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
    
    __table_args__ = (
        # Unique constraint on document_id and chunk_index
        # This ensures no duplicate chunks for the same document
    )

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    title = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(10), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

# LangGraph checkpoint tables for state persistence
class Checkpoint(Base):
    __tablename__ = "checkpoints"
    
    thread_id = Column(String(100), primary_key=True)
    checkpoint_ns = Column(String(100), primary_key=True, default="")
    checkpoint_id = Column(String(100), primary_key=True)
    parent_checkpoint_id = Column(String(100))
    type = Column(String(100))
    checkpoint = Column(JSON, nullable=False)
    metadata = Column(JSON, default=dict)

class CheckpointWrite(Base):
    __tablename__ = "checkpoint_writes"
    
    thread_id = Column(String(100), primary_key=True)
    checkpoint_ns = Column(String(100), primary_key=True, default="")
    checkpoint_id = Column(String(100), primary_key=True)
    task_id = Column(String(100), primary_key=True)
    idx = Column(Integer, primary_key=True, default=0)
    channel = Column(String(100), nullable=False)
    type = Column(String(100))
    value = Column(JSON, nullable=False)