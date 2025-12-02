from core.state import RAGState, RetrievedChunk
from server.config import settings


async def hallucination(state: RAGState) -> dict:
    answer = state.get("answer", "")
    chunks: list[RetrievedChunk] = state.get("retrieved_chunks", [])
    context = "\n\n".join([c.get("content", "") for c in chunks])
    score = 0.5
    try:
        from core.llm.gateway import LLMGateway

        gw = LLMGateway()
        prompt = (
            "根据提供的参考上下文，评估回答的一致性，输出一个0到1之间的数字，"
            "越接近1表示越一致，无需解释。"
        )
        val = await gw.chat(prompt=f"{prompt}\n\n回答:\n{answer}\n\n上下文:\n{context}")
        try:
            score = float((val or "").strip().split()[0])
        except Exception:
            score = 0.5
    except Exception:
        score = 0.5
    thr = float(settings.hallucination_threshold)
    hallucination_detected = bool(score < thr)
    return {
        "hallucination_score": float(score),
        "hallucination_detected": hallucination_detected,
        "step": "hallucination",
        "metrics": {"hallucination": {"score": float(score), "threshold": thr}},
    }
