# Relational Data Models (SQLModel)

## 1. Database Standards
- **ORM**: SQLModel (Async).
- **ID Type**: UUIDv4 (Security requirement, no auto-increment integers).
- **JSON Handling**: Use Postgres `JSONB` for flexible metadata.

## 2. Table Definitions

### Class `KnowledgeBase`
Represents a collection of documents (MaxKB concept).
```python
class KnowledgeBase(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True) # Multi-tenancy isolation
    name: str
    description: Optional[str]
    
    # Configuration (High Value)
    parser_config: Dict = Field(sa_column=Column(JSONB)) 
    # e.g., {"method": "visual", "chunk_size": 512, "use_vlm": true}
    
    embedding_model: str # e.g., "bge-m3"
    created_at: datetime