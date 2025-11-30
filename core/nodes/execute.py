from typing import Dict, List
from core.state import RAGState, RetrievedChunk


def _markdown_table_to_csv(md: str) -> str:
    lines = [l.strip() for l in (md or "").splitlines() if l.strip()]
    rows: List[List[str]] = []
    for l in lines:
        if l.startswith("|") and l.endswith("|"):
            parts = [p.strip() for p in l.split("|")][1:-1]
            # skip separator row like | --- |
            if all(set(p) <= set("-: ") for p in parts):
                continue
            rows.append(parts)
    out_lines: List[str] = []
    for r in rows:
        out_lines.append(",".join([p.replace(",", " ") for p in r]))
    return "\n".join(out_lines)


async def execute(state: RAGState) -> Dict:
    intent = (state.get("intent") or "").lower()
    chunks: List[RetrievedChunk] = state.get("retrieved_chunks") or []
    if not chunks:
        return {"step": "execute", "answer": "暂无可执行内容，请先检索或指定具体文档。"}
    csv_outputs: List[str] = []
    for ch in chunks[:5]:
        meta = ch.get("metadata") or {}
        if (meta.get("type") == "table") and ch.get("content"):
            csv_outputs.append(_markdown_table_to_csv(ch.get("content") or ""))
    if not csv_outputs:
        return {"step": "execute", "answer": "未发现可导出的表格，已跳过。"}
    csv_text = "\n\n".join(csv_outputs)
    return {"step": "execute", "answer": csv_text}

