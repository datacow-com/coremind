#!/usr/bin/env python3
"""
Database Seed Script for Providers and Model Configs

Phase 1: 多云算力基础设施
Task 7.5: 创建数据库种子数据

This script populates the providers and model_configs tables with
the enhanced provider configurations for Phase 1.

Usage:
    python scripts/seed_providers.py
    
    # Dry run (show SQL without executing)
    python scripts/seed_providers.py --dry-run
    
    # Force update existing records
    python scripts/seed_providers.py --force
"""
import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from core.llm.provider_config import ENHANCED_PROVIDER_CONFIGS, REQUIRED_ENV
from server.database import AsyncSessionLocal


# Provider seed data based on ENHANCED_PROVIDER_CONFIGS
PROVIDER_SEEDS = [
    {
        "name": "dashscope",
        "description": "阿里云百炼 DashScope - 通义千问系列模型",
        "category": "llm",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "priority": 1,
        "endpoints": {
            "chat": "/chat/completions",
            "embedding": "/embeddings",
            "vision": "/chat/completions"
        },
        "rate_limits": {"rpm": 1000, "tpm": 1000000},
        "is_active": True,
        "is_healthy": True,
    },
    {
        "name": "deepseek",
        "description": "DeepSeek - 高性价比推理模型",
        "category": "llm",
        "base_url": "https://api.deepseek.com/v1",
        "priority": 2,
        "endpoints": {
            "chat": "/chat/completions"
        },
        "rate_limits": {"rpm": 500, "tpm": 500000},
        "is_active": True,
        "is_healthy": True,
    },
    {
        "name": "volcengine",
        "description": "火山方舟 - 豆包系列模型",
        "category": "llm",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "priority": 3,
        "endpoints": {
            "chat": "/chat/completions"
        },
        "rate_limits": {"rpm": 600, "tpm": 600000},
        "is_active": True,
        "is_healthy": True,
    },
    {
        "name": "openai",
        "description": "OpenAI - GPT 系列模型",
        "category": "llm",
        "base_url": "https://api.openai.com/v1",
        "priority": 6,
        "endpoints": {
            "chat": "/chat/completions",
            "embedding": "/embeddings"
        },
        "rate_limits": {"rpm": 500, "tpm": 300000},
        "is_active": True,
        "is_healthy": True,
    },
    {
        "name": "azure",
        "description": "Azure OpenAI - 企业级 GPT 服务",
        "category": "llm",
        "base_url": None,  # Uses AZURE_OPENAI_ENDPOINT env var
        "priority": 5,
        "endpoints": {
            "chat": "/chat/completions"
        },
        "rate_limits": {"rpm": 500, "tpm": 300000},
        "is_active": True,
        "is_healthy": True,
    },
]

# Model config seed data
MODEL_SEEDS = [
    # DashScope models
    {"provider": "dashscope", "model_id": "qwen-max", "name": "Qwen Max", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 8192}, "is_default": False},
    {"provider": "dashscope", "model_id": "qwen-max-latest", "name": "Qwen Max Latest", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 8192}, "is_default": False},
    {"provider": "dashscope", "model_id": "qwen-plus", "name": "Qwen Plus", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 32768}, "is_default": False},
    {"provider": "dashscope", "model_id": "qwen-plus-latest", "name": "Qwen Plus Latest", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 32768}, "is_default": False},
    {"provider": "dashscope", "model_id": "qwen-turbo", "name": "Qwen Turbo", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 8192}, "is_default": True},
    {"provider": "dashscope", "model_id": "qwen-turbo-latest", "name": "Qwen Turbo Latest", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 8192}, "is_default": False},
    {"provider": "dashscope", "model_id": "qwen-vl-max", "name": "Qwen VL Max", "type": "vision",
     "parameters": {"temperature": 0.7, "max_tokens": 4096}, "is_default": False},
    {"provider": "dashscope", "model_id": "qwen-vl-plus", "name": "Qwen VL Plus", "type": "vision",
     "parameters": {"temperature": 0.7, "max_tokens": 4096}, "is_default": False},
    {"provider": "dashscope", "model_id": "text-embedding-v3", "name": "Text Embedding V3", "type": "embedding",
     "parameters": {"dimensions": 1024}, "is_default": False},
    
    # DeepSeek models
    {"provider": "deepseek", "model_id": "deepseek-chat", "name": "DeepSeek Chat", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 8192}, "is_default": True},
    {"provider": "deepseek", "model_id": "deepseek-reasoner", "name": "DeepSeek Reasoner", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 8192}, "is_default": False},
    {"provider": "deepseek", "model_id": "deepseek-coder", "name": "DeepSeek Coder", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 8192}, "is_default": False},
    
    # Volcengine models
    {"provider": "volcengine", "model_id": "doubao-pro-256k", "name": "Doubao Pro 256K", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 8192}, "is_default": True},
    {"provider": "volcengine", "model_id": "doubao-pro-128k", "name": "Doubao Pro 128K", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 8192}, "is_default": False},
    {"provider": "volcengine", "model_id": "doubao-pro-32k", "name": "Doubao Pro 32K", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 8192}, "is_default": False},
    {"provider": "volcengine", "model_id": "doubao-lite-128k", "name": "Doubao Lite 128K", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 8192}, "is_default": False},
    {"provider": "volcengine", "model_id": "doubao-lite-32k", "name": "Doubao Lite 32K", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 8192}, "is_default": False},
    
    # OpenAI models
    {"provider": "openai", "model_id": "gpt-4o", "name": "GPT-4o", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 4096}, "is_default": False},
    {"provider": "openai", "model_id": "gpt-4o-mini", "name": "GPT-4o Mini", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 4096}, "is_default": True},
    {"provider": "openai", "model_id": "gpt-4-turbo", "name": "GPT-4 Turbo", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 4096}, "is_default": False},
    {"provider": "openai", "model_id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 4096}, "is_default": False},
    {"provider": "openai", "model_id": "text-embedding-3-small", "name": "Text Embedding 3 Small", "type": "embedding",
     "parameters": {"dimensions": 1536}, "is_default": False},
    {"provider": "openai", "model_id": "text-embedding-3-large", "name": "Text Embedding 3 Large", "type": "embedding",
     "parameters": {"dimensions": 3072}, "is_default": False},
    
    # Azure models
    {"provider": "azure", "model_id": "gpt-4o", "name": "Azure GPT-4o", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 4096}, "is_default": True},
    {"provider": "azure", "model_id": "gpt-4o-mini", "name": "Azure GPT-4o Mini", "type": "chat",
     "parameters": {"temperature": 0.7, "max_tokens": 4096}, "is_default": False},
]

# Default budget configs
BUDGET_SEEDS = [
    {
        "scope": "global",
        "scope_id": None,
        "daily_limit": 100.00,
        "monthly_limit": 2000.00,
        "alert_threshold": 0.80,
        "hard_stop_threshold": 0.95,
        "is_active": True,
    },
]


async def get_api_key_from_env(provider_name: str) -> str | None:
    """Get API key from environment variable"""
    env_vars = REQUIRED_ENV.get(provider_name, [])
    for env_var in env_vars:
        if "API_KEY" in env_var:
            return os.environ.get(env_var)
    return None


async def seed_providers(session, dry_run: bool = False, force: bool = False):
    """Seed providers table"""
    print("\n=== Seeding Providers ===")
    
    for provider_data in PROVIDER_SEEDS:
        provider_name = provider_data["name"]
        
        # Get API key from environment
        api_key = await get_api_key_from_env(provider_name)
        
        # Check if provider exists
        result = await session.execute(
            text("SELECT id FROM providers WHERE name = :name"),
            {"name": provider_name}
        )
        existing = result.fetchone()
        
        if existing and not force:
            print(f"  [SKIP] {provider_name} already exists (use --force to update)")
            continue
        
        provider_id = existing[0] if existing else uuid.uuid4()
        
        if dry_run:
            print(f"  [DRY-RUN] Would {'update' if existing else 'insert'} {provider_name}")
            continue
        
        if existing:
            # Update existing
            await session.execute(
                text("""
                    UPDATE providers SET
                        description = :description,
                        category = :category,
                        base_url = :base_url,
                        api_key = COALESCE(:api_key, api_key),
                        priority = :priority,
                        endpoints = :endpoints,
                        rate_limits = :rate_limits,
                        is_active = :is_active,
                        is_healthy = :is_healthy,
                        updated_at = NOW()
                    WHERE name = :name
                """),
                {
                    "name": provider_name,
                    "description": provider_data["description"],
                    "category": provider_data["category"],
                    "base_url": provider_data["base_url"],
                    "api_key": api_key,
                    "priority": provider_data["priority"],
                    "endpoints": str(provider_data["endpoints"]).replace("'", '"'),
                    "rate_limits": str(provider_data["rate_limits"]).replace("'", '"'),
                    "is_active": provider_data["is_active"],
                    "is_healthy": provider_data["is_healthy"],
                }
            )
            print(f"  [UPDATE] {provider_name}")
        else:
            # Insert new
            await session.execute(
                text("""
                    INSERT INTO providers (
                        id, name, description, category, base_url, api_key,
                        priority, endpoints, rate_limits, is_active, is_healthy
                    ) VALUES (
                        :id, :name, :description, :category, :base_url, :api_key,
                        :priority, :endpoints::jsonb, :rate_limits::jsonb, :is_active, :is_healthy
                    )
                """),
                {
                    "id": str(provider_id),
                    "name": provider_name,
                    "description": provider_data["description"],
                    "category": provider_data["category"],
                    "base_url": provider_data["base_url"],
                    "api_key": api_key,
                    "priority": provider_data["priority"],
                    "endpoints": str(provider_data["endpoints"]).replace("'", '"'),
                    "rate_limits": str(provider_data["rate_limits"]).replace("'", '"'),
                    "is_active": provider_data["is_active"],
                    "is_healthy": provider_data["is_healthy"],
                }
            )
            print(f"  [INSERT] {provider_name}")


async def seed_model_configs(session, dry_run: bool = False, force: bool = False):
    """Seed model_configs table"""
    print("\n=== Seeding Model Configs ===")
    
    # Get provider IDs
    result = await session.execute(text("SELECT id, name FROM providers"))
    provider_map = {row[1]: row[0] for row in result.fetchall()}
    
    for model_data in MODEL_SEEDS:
        provider_name = model_data["provider"]
        model_id = model_data["model_id"]
        
        if provider_name not in provider_map:
            print(f"  [SKIP] {provider_name}/{model_id} - provider not found")
            continue
        
        provider_id = provider_map[provider_name]
        
        # Check if model exists
        result = await session.execute(
            text("""
                SELECT id FROM model_configs 
                WHERE provider_id = :provider_id AND model_id = :model_id
            """),
            {"provider_id": str(provider_id), "model_id": model_id}
        )
        existing = result.fetchone()
        
        if existing and not force:
            print(f"  [SKIP] {provider_name}/{model_id} already exists")
            continue
        
        config_id = existing[0] if existing else uuid.uuid4()
        
        if dry_run:
            print(f"  [DRY-RUN] Would {'update' if existing else 'insert'} {provider_name}/{model_id}")
            continue
        
        if existing:
            await session.execute(
                text("""
                    UPDATE model_configs SET
                        name = :name,
                        type = :type,
                        parameters = :parameters,
                        is_default = :is_default,
                        is_active = true,
                        updated_at = NOW()
                    WHERE provider_id = :provider_id AND model_id = :model_id
                """),
                {
                    "provider_id": str(provider_id),
                    "model_id": model_id,
                    "name": model_data["name"],
                    "type": model_data["type"],
                    "parameters": str(model_data["parameters"]).replace("'", '"'),
                    "is_default": model_data["is_default"],
                }
            )
            print(f"  [UPDATE] {provider_name}/{model_id}")
        else:
            await session.execute(
                text("""
                    INSERT INTO model_configs (
                        id, provider_id, model_id, name, type, parameters, is_default, is_active
                    ) VALUES (
                        :id, :provider_id, :model_id, :name, :type, :parameters::jsonb, :is_default, true
                    )
                """),
                {
                    "id": str(config_id),
                    "provider_id": str(provider_id),
                    "model_id": model_id,
                    "name": model_data["name"],
                    "type": model_data["type"],
                    "parameters": str(model_data["parameters"]).replace("'", '"'),
                    "is_default": model_data["is_default"],
                }
            )
            print(f"  [INSERT] {provider_name}/{model_id}")


async def seed_budget_configs(session, dry_run: bool = False, force: bool = False):
    """Seed budget_configs table"""
    print("\n=== Seeding Budget Configs ===")
    
    for budget_data in BUDGET_SEEDS:
        scope = budget_data["scope"]
        scope_id = budget_data["scope_id"]
        
        # Check if budget exists
        if scope_id:
            result = await session.execute(
                text("SELECT id FROM budget_configs WHERE scope = :scope AND scope_id = :scope_id"),
                {"scope": scope, "scope_id": scope_id}
            )
        else:
            result = await session.execute(
                text("SELECT id FROM budget_configs WHERE scope = :scope AND scope_id IS NULL"),
                {"scope": scope}
            )
        existing = result.fetchone()
        
        if existing and not force:
            print(f"  [SKIP] {scope}/{scope_id or 'NULL'} already exists")
            continue
        
        if dry_run:
            print(f"  [DRY-RUN] Would {'update' if existing else 'insert'} {scope}/{scope_id or 'NULL'}")
            continue
        
        if existing:
            await session.execute(
                text("""
                    UPDATE budget_configs SET
                        daily_limit = :daily_limit,
                        monthly_limit = :monthly_limit,
                        alert_threshold = :alert_threshold,
                        hard_stop_threshold = :hard_stop_threshold,
                        is_active = :is_active,
                        updated_at = NOW()
                    WHERE id = :id
                """),
                {
                    "id": existing[0],
                    "daily_limit": budget_data["daily_limit"],
                    "monthly_limit": budget_data["monthly_limit"],
                    "alert_threshold": budget_data["alert_threshold"],
                    "hard_stop_threshold": budget_data["hard_stop_threshold"],
                    "is_active": budget_data["is_active"],
                }
            )
            print(f"  [UPDATE] {scope}/{scope_id or 'NULL'}")
        else:
            await session.execute(
                text("""
                    INSERT INTO budget_configs (
                        scope, scope_id, daily_limit, monthly_limit,
                        alert_threshold, hard_stop_threshold, is_active
                    ) VALUES (
                        :scope, :scope_id, :daily_limit, :monthly_limit,
                        :alert_threshold, :hard_stop_threshold, :is_active
                    )
                """),
                {
                    "scope": scope,
                    "scope_id": scope_id,
                    "daily_limit": budget_data["daily_limit"],
                    "monthly_limit": budget_data["monthly_limit"],
                    "alert_threshold": budget_data["alert_threshold"],
                    "hard_stop_threshold": budget_data["hard_stop_threshold"],
                    "is_active": budget_data["is_active"],
                }
            )
            print(f"  [INSERT] {scope}/{scope_id or 'NULL'}")


async def main():
    parser = argparse.ArgumentParser(description="Seed database with provider configurations")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--force", action="store_true", help="Force update existing records")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Phase 1: Provider Database Seed Script")
    print("=" * 60)
    
    if args.dry_run:
        print("\n[DRY-RUN MODE] No changes will be made to the database\n")
    
    try:
        async with AsyncSessionLocal() as session:
            await seed_providers(session, args.dry_run, args.force)
            await seed_model_configs(session, args.dry_run, args.force)
            await seed_budget_configs(session, args.dry_run, args.force)
            
            if not args.dry_run:
                await session.commit()
                print("\n✓ All changes committed successfully")
            else:
                print("\n[DRY-RUN] No changes were made")
                
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
