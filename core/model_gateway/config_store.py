from typing import Dict, Any
import os
import json


CONFIG_DIR = os.path.join(os.getcwd(), "data", "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "providers.json")


DEFAULT_CONFIG: Dict[str, Any] = {
    "bindings": {
        "parse": "gemini",
        "retrieve": "embedding",
        "chat": "gemini",
        "rerank": "cross_encoder",
    },
    "providers": [
        {"name": "openai", "model": "gpt-4o-mini", "base_url": "https://api.openai.com"},
        {"name": "gemini", "model": "gemini-1.5-flash", "base_url": "https://generativelanguage.googleapis.com"},
        {"name": "anthropic", "model": "claude-3-5-sonnet", "base_url": "https://api.anthropic.com"},
        {"name": "openrouter", "model": "meta-llama/llama-3.1-8b-instruct", "base_url": "https://openrouter.ai/api"},
        {"name": "dashscope", "model": "qwen-max", "base_url": "https://dashscope.aliyuncs.com"},
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
    "moonshot": ["MOONSHOT_API_KEY"],
    "qianfan": ["QIANFAN_API_KEY"],
    "zhipu": ["ZHIPU_API_KEY"],
    "deepseek": ["DEEPSEEK_API_KEY"],
    "ollama": [],
}


def load_config() -> Dict[str, Any]:
    try:
        if not os.path.exists(CONFIG_PATH):
            os.makedirs(CONFIG_DIR, exist_ok=True)
            save_config(DEFAULT_CONFIG)
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_CONFIG


def save_config(cfg: Dict[str, Any]) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def validate_provider(name: str) -> Dict[str, Any]:
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
    if n in {"dashscope", "moonshot", "qianfan", "zhipu", "deepseek"}:
        return "domestic"
    if n in {"openai", "anthropic", "gemini", "openrouter"}:
        return "foreign"
    if n in {"ollama"}:
        return "local"
    return "other"
