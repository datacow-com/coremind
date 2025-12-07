import time

from core.llm.registry import get_llm_gateway
from core.state import RAGState, RetrievedChunk, Source
from core.utils.trace import set_span_attrs

_GEN_SYSTEM_PROMPT = (
    "你是一个严格依赖引用的助手。"
    "必须仅使用提供的“上下文”作答；若上下文缺失答案，回复“未找到相关信息”。"
    "回答需输出 JSON，对象包含：answer(string)、citations(array of string chunk_id)。"
    "不要虚构、不要添加上下文之外的信息。"
)


async def generate(state: RAGState) -> dict:
    """LangGraph 生成节点：强引用回答，要求 JSON 输出 answer/citations。"""
    query = state.get("query", "")
    chunks: list[RetrievedChunk] = state.get("retrieved_chunks", [])
    context = "\n\n".join([c.get("content", "") for c in chunks])

    sources: list[Source] = []
    for c in chunks:
        src: Source = {
            "chunk_id": c.get("id"),
            "content": c.get("content"),
            "score": c.get("score"),
            "document_name": c.get("doc_id"),
            "page_number": c.get("page_num"),
        }
        sources.append(src)

    guarded_prompt = (
        f"{_GEN_SYSTEM_PROMPT}\n\n"
        f"用户问题：{query}\n\n"
        "要求：输出 JSON，包含字段 answer（简洁中文）与 citations（引用 chunk_id 列表）。"
        '若没有依据，请返回：{"answer":"未找到相关信息","citations":[]}'
    )

    meta = state.get("metadata", {}) or {}
    llm_provider = meta.get("llm_provider")
    llm_model = meta.get("llm_model")
    gw = get_llm_gateway(provider=llm_provider, model=llm_model)
    t0 = time.perf_counter()
    llm_answer = await gw.chat(prompt=guarded_prompt, context=context)
    parsed_answer = None
    if llm_answer:
        try:
            import json as _json

            parsed = _json.loads(llm_answer)
            if isinstance(parsed, dict) and "answer" in parsed and "citations" in parsed:
                parsed_answer = parsed
        except Exception:
            parsed_answer = None
    if not parsed_answer:
        parsed_answer = {
            "answer": f"未找到相关信息（无可用上下文，问题：{query}）",
            "citations": [],
        }
    answer = parsed_answer.get("answer") or ""
    # 尝试将 citations 回填到 sources（按 chunk_id 对齐）
    citations_ids = set([str(c) for c in parsed_answer.get("citations", []) if c])
    if citations_ids:
        sources = [s for s in sources if str(s.get("chunk_id")) in citations_ids]
    dur = int((time.perf_counter() - t0) * 1000)
    set_span_attrs(
        {
            "llm.provider": llm_provider or gw.provider,
            "llm.model": llm_model or (gw.model or ""),
            "llm.context_len": len(context),
            "llm.duration_ms": dur,
        }
    )
    return {
        "context": context,
        "answer": answer,
        "sources": sources,
        "step": "generation",
        "metrics": {"generate": {"duration_ms": dur, "context_len": len(context)}},
    }
