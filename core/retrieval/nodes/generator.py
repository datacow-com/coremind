"""
Citation Generator - Generates answers with citations.

Features:
- Citation extraction and linking
- Configurable prompts (P2 Fix #12)
- Improved confidence calculation (P1 Fix #11)
- LLM gateway caching
"""

import re
from typing import Any

from core.llm.gateway import LLMGateway
from core.state import RetrievalState


# Default generation prompts
DEFAULT_SYSTEM_PROMPT = """
你是一个严谨的助手，必须基于提供的上下文回答问题。

规则：
1. 每个事实必须标注引用来源，格式：<cite id="[索引]">事实内容</cite>
2. 若上下文无法回答，明确告知"根据提供的资料无法回答"
3. 不要编造信息
4. 保持专业、准确、简洁
"""

DEFAULT_USER_PROMPT = """
上下文：
{context}

问题：{query}

请回答并标注引用。
"""


# LLM gateway cache for generator
_GENERATOR_GATEWAY_CACHE: dict[str, LLMGateway] = {}


class CitationGenerator:
    """
    Citation-aware answer generator.
    
    P1 Fix #11: Improved confidence calculation
    P2 Fix #12: Configurable generation prompts
    """
    
    async def __call__(self, state: RetrievalState) -> RetrievalState:
        cfg = state["strategy_config"]
        query = state["input_query"]
        docs = state["reranked_results"][: cfg.get("top_k", 5)]
        provider = cfg.get("llm_provider")
        model = cfg.get("llm_model")
        
        # Use cached gateway
        cache_key = f"{provider}:{model}"
        if cache_key not in _GENERATOR_GATEWAY_CACHE:
            _GENERATOR_GATEWAY_CACHE[cache_key] = LLMGateway(provider=provider, model=model)
        gateway = _GENERATOR_GATEWAY_CACHE[cache_key]

        if not state.get("is_relevant", False) or not docs:
            state["final_answer"] = "抱歉，未找到相关信息回答您的问题。"
            state["citations"] = []
            state["confidence"] = 0.0
            return state

        # Build Context
        context = ""
        for i, doc in enumerate(docs):
            metadata = doc.get("metadata", {})
            context += f"\n[{i}] 来源: {metadata.get('doc_id', 'unknown')}, 页码: {metadata.get('page_num', 'N/A')}\n"
            context += f"内容: {doc.get('content', '')}\n"

        # P2 Fix #12: Use configurable prompts
        system_prompt = cfg.get("generation_system_prompt") or DEFAULT_SYSTEM_PROMPT
        user_prompt_template = cfg.get("generation_user_prompt") or DEFAULT_USER_PROMPT
        user_prompt = user_prompt_template.format(context=context, query=query)

        # Combine prompts
        full_prompt = f"{system_prompt.strip()}\n\n{user_prompt.strip()}"

        answer = await gateway.chat(prompt=full_prompt, context=None)

        # Parse Citations
        citations = []
        cite_pattern = r'<cite id="\[(\d+)\]">(.*?)</cite>'

        matches = re.finditer(cite_pattern, answer, re.DOTALL)
        for match in matches:
            idx = int(match.group(1))
            if idx < len(docs):
                doc = docs[idx]
                citations.append(
                    {
                        "doc_id": doc.get("metadata", {}).get("doc_id"),
                        "page": doc.get("metadata", {}).get("page_num"),
                        "bbox": doc.get("metadata", {}).get("bbox"),
                        "content": match.group(2),  # The text that was cited
                        "chunk_id": doc.get("id"),
                    }
                )

        state["final_answer"] = answer
        state["citations"] = citations
        
        # P1 Fix #11: Improved confidence calculation
        # Confidence is based on:
        # 1. Retrieval confidence (from reranker)
        # 2. Citation coverage
        # 3. Source diversity
        retrieval_confidence = state.get("retrieval_confidence", 0.5)
        
        # Citation coverage: how many unique sources cited vs available
        if docs:
            cited_indices = set(int(m.group(1)) for m in re.finditer(cite_pattern, answer))
            citation_coverage = len(cited_indices) / len(docs)
        else:
            citation_coverage = 0.0
        
        # Combined confidence
        if citations:
            # Has citations - higher base confidence
            state["confidence"] = min(1.0, retrieval_confidence * 0.6 + citation_coverage * 0.4)
        elif "根据提供的资料无法回答" in answer or "无法回答" in answer:
            # Honest "don't know" - moderate confidence
            state["confidence"] = 0.3
        else:
            # No citations but has answer - lower confidence
            state["confidence"] = retrieval_confidence * 0.5

        return state


def clear_generator_cache() -> None:
    """Clear the generator gateway cache."""
    global _GENERATOR_GATEWAY_CACHE
    _GENERATOR_GATEWAY_CACHE.clear()
