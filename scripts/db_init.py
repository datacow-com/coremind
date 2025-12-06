import os
import asyncio
from server.database import init_db, get_db
from server.models import Provider, ModelConfig
from sqlalchemy.future import select

async def seed_data():
    # Using local session context if possible or just execute
    # We need an async session
    from server.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # Check if data exists
        res = await session.execute(select(Provider))
        if res.scalars().first():
            print("Data already seeded.")
            return

        # Seed Providers
        dashscope = Provider(name="DashScope", category="llm", base_url="https://dashscope.aliyuncs.com", api_key=os.getenv("DASHSCOPE_API_KEY"))
        openai = Provider(name="OpenAI", category="llm", base_url="https://api.openai.com/v1", api_key=os.getenv("OPENAI_API_KEY"))
        
        session.add_all([dashscope, openai])
        await session.commit()
        await session.refresh(dashscope)
        await session.refresh(openai)
        
        # Seed Models
        models = [
            ModelConfig(provider_id=dashscope.id, model_id="qwen-plus", name="Qwen Plus", type="chat", is_default=True),
            ModelConfig(provider_id=dashscope.id, model_id="text-embedding-v3", name="Qwen Embedding", type="embedding"),
            ModelConfig(provider_id=openai.id, model_id="gpt-4o-mini", name="GPT-4o Mini", type="chat"),
            ModelConfig(provider_id=openai.id, model_id="text-embedding-3-small", name="OpenAI Embedding", type="embedding"),
        ]
        session.add_all(models)
        await session.commit()
        print("Seeding complete.")

def main() -> None:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required")
    
    # 1. Init Schema
    from server.database import init_db_sync
    init_db_sync()
    
    # 2. Seed Data (Async)
    asyncio.run(seed_data())

if __name__ == "__main__":
    main()
