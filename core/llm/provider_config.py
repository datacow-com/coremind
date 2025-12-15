import json
import os
from typing import Any

# 说明：此文件仅保留“文件化默认配置 + 环境校验”能力，供少量 API 读取。
# 实际在线调用请使用 core/llm/gateway.py（DB 驱动），避免重复网关实现。

CONFIG_DIR = os.path.join(os.getcwd(), "data", "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "providers.json")


DEFAULT_CONFIG: dict[str, Any] = {
    "bindings": {
        "parse": "dashscope",
        "retrieve": "embedding",
        "chat": "gemini",
        "rerank": "cross_encoder",
    },
    "settings": {
        "vector_weight": 0.6,
        "keyword_weight": 0.4,
        "web_search_enabled": True,
    },
    "providers": [
        {"name": "openai", "model": "gpt-4o-mini", "base_url": "https://api.openai.com"},
        {
            "name": "gemini",
            "model": "gemini-1.5-flash",
            "base_url": "https://generativelanguage.googleapis.com",
        },
        {
            "name": "anthropic",
            "model": "claude-3-5-sonnet",
            "base_url": "https://api.anthropic.com",
        },
        {
            "name": "openrouter",
            "model": "meta-llama/llama-3.1-8b-instruct",
            "base_url": "https://openrouter.ai/api",
        },
        {"name": "dashscope", "model": "qwen-max", "base_url": "https://dashscope.aliyuncs.com"},
        {"name": "ark", "model": "ep-vision", "base_url": "https://api.ark.cn-beijing.volces.com"},
        {"name": "moonshot", "model": "moonshot-v1-8k", "base_url": "https://api.moonshot.cn"},
        {"name": "qianfan", "model": "ERNIE-Speed-8K", "base_url": "https://api.baidu.com"},
        {"name": "zhipu", "model": "glm-4-flash", "base_url": "https://open.bigmodel.cn"},
        {"name": "deepseek", "model": "deepseek-chat", "base_url": "https://api.deepseek.com"},
        {"name": "ollama", "model": "qwen2:7b", "base_url": "http://localhost:11434"},
    ],
}


REQUIRED_ENV = {
    "openai": ["OPENAI_API_KEY"],
    "gemini": ["GEMINI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY"],
    "dashscope": ["DASHSCOPE_API_KEY"],
    "ark": ["VOLCENGINE_API_KEY"],
    "volcengine": ["VOLCENGINE_API_KEY"],
    "moonshot": ["MOONSHOT_API_KEY"],
    "qianfan": ["QIANFAN_API_KEY"],
    "zhipu": ["ZHIPU_API_KEY"],
    "deepseek": ["DEEPSEEK_API_KEY"],
    "azure": ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"],
    "ollama": [],
}


# Phase 1: 增强的 Provider 配置
ENHANCED_PROVIDER_CONFIGS: dict[str, dict] = {
    "dashscope": {
        "name": "dashscope",
        "category": "domestic",
        "priority": 1,
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key_env": "DASHSCOPE_API_KEY",
        "models": {
            "qwen-max": {
                "cost_per_1k_input": 0.02,
                "cost_per_1k_output": 0.06,
                "context_length": 32000,
                "type": "chat",
            },
            "qwen-plus": {
                "cost_per_1k_input": 0.004,
                "cost_per_1k_output": 0.012,
                "context_length": 131072,
                "type": "chat",
            },
            "qwen-turbo": {
                "cost_per_1k_input": 0.002,
                "cost_per_1k_output": 0.006,
                "context_length": 131072,
                "type": "chat",
            },
            "qwen-vl-max": {
                "cost_per_1k_input": 0.02,
                "cost_per_1k_output": 0.06,
                "context_length": 32000,
                "type": "vision",
            },
            "qwen-vl-plus": {
                "cost_per_1k_input": 0.008,
                "cost_per_1k_output": 0.008,
                "context_length": 8000,
                "type": "vision",
            },
            "text-embedding-v3": {
                "cost_per_1k_input": 0.0007,
                "cost_per_1k_output": 0.0,
                "context_length": 8192,
                "type": "embedding",
                "dimensions": 1024,
            },
        },
        "rate_limits": {"rpm": 1000, "tpm": 1000000},
    },
    "deepseek": {
        "name": "deepseek",
        "category": "domestic",
        "priority": 2,
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "models": {
            "deepseek-chat": {
                "cost_per_1k_input": 0.00014,
                "cost_per_1k_output": 0.00028,
                "context_length": 64000,
                "type": "chat",
            },
            "deepseek-reasoner": {
                "cost_per_1k_input": 0.00055,
                "cost_per_1k_output": 0.00219,
                "context_length": 64000,
                "type": "chat",
            },
        },
        "rate_limits": {"rpm": 500, "tpm": 500000},
    },
    "volcengine": {
        "name": "volcengine",
        "category": "domestic",
        "priority": 3,
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "api_key_env": "VOLCENGINE_API_KEY",
        "models": {
            "doubao-pro-256k": {
                "cost_per_1k_input": 0.005,
                "cost_per_1k_output": 0.009,
                "context_length": 256000,
                "type": "chat",
            },
            "doubao-lite-128k": {
                "cost_per_1k_input": 0.0008,
                "cost_per_1k_output": 0.001,
                "context_length": 128000,
                "type": "chat",
            },
        },
        "rate_limits": {"rpm": 600, "tpm": 600000},
    },
    "azure": {
        "name": "azure",
        "category": "foreign",
        "priority": 5,
        "base_url_env": "AZURE_OPENAI_ENDPOINT",
        "api_key_env": "AZURE_OPENAI_API_KEY",
        "models": {
            "gpt-4o": {
                "cost_per_1k_input": 0.0025,
                "cost_per_1k_output": 0.01,
                "context_length": 128000,
                "type": "chat",
            },
            "gpt-4o-mini": {
                "cost_per_1k_input": 0.00015,
                "cost_per_1k_output": 0.0006,
                "context_length": 128000,
                "type": "chat",
            },
        },
        "rate_limits": {"rpm": 500, "tpm": 300000},
    },
    "openai": {
        "name": "openai",
        "category": "foreign",
        "priority": 6,
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "models": {
            "gpt-4o": {
                "cost_per_1k_input": 0.0025,
                "cost_per_1k_output": 0.01,
                "context_length": 128000,
                "type": "chat",
            },
            "gpt-4o-mini": {
                "cost_per_1k_input": 0.00015,
                "cost_per_1k_output": 0.0006,
                "context_length": 128000,
                "type": "chat",
            },
        },
        "rate_limits": {"rpm": 500, "tpm": 300000},
    },
}


def load_config() -> dict[str, Any]:
    try:
        if not os.path.exists(CONFIG_PATH):
            os.makedirs(CONFIG_DIR, exist_ok=True)
            save_config(DEFAULT_CONFIG)
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_CONFIG


def save_config(cfg: dict[str, Any]) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def validate_provider(name: str) -> dict[str, Any]:
    envs = REQUIRED_ENV.get(name, [])
    missing = [e for e in envs if not os.environ.get(e)]
    return {
        "provider": name,
        "required_env": envs,
        "missing_env": missing,
        "configured": len(missing) == 0,
    }


def provider_category(name: str) -> str:
    n = name.lower()
    if n in {"dashscope", "ark", "moonshot", "qianfan", "zhipu", "deepseek"}:
        return "domestic"
    if n in {"openai", "anthropic", "gemini", "openrouter"}:
        return "foreign"
    if n in {"ollama"}:
        return "local"
    return "other"


def get_enhanced_provider_config(name: str) -> dict | None:
    """获取增强的 Provider 配置"""
    return ENHANCED_PROVIDER_CONFIGS.get(name.lower())


def get_all_enhanced_providers() -> list[str]:
    """获取所有增强配置的 Provider 名称"""
    return list(ENHANCED_PROVIDER_CONFIGS.keys())


def get_domestic_providers() -> list[str]:
    """获取国内 Provider 列表"""
    return [
        name for name, cfg in ENHANCED_PROVIDER_CONFIGS.items()
        if cfg.get("category") == "domestic"
    ]


def get_foreign_providers() -> list[str]:
    """获取国外 Provider 列表"""
    return [
        name for name, cfg in ENHANCED_PROVIDER_CONFIGS.items()
        if cfg.get("category") == "foreign"
    ]


def validate_all_providers() -> dict[str, dict]:
    """验证所有 Provider 的环境变量配置"""
    results = {}
    for name in ENHANCED_PROVIDER_CONFIGS:
        results[name] = validate_provider(name)
    return results
