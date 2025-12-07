from core.state import RAGState


async def route(state: RAGState) -> dict:
    """LangGraph 路由节点：基于 query 关键词选择意图（qa/summarize/web_search/execute）。"""
    q = (state.get("query") or "").lower()
    intent = "qa"
    if any(k in q for k in ["总结", "总结一下", "概括", "overview", "summary"]):
        intent = "summarize"
    elif any(k in q for k in ["搜索", "联网", "查找", "search", "web"]):
        intent = "web_search"
    elif any(k in q for k in ["执行", "运行", "调用", "execute", "run", "task"]):
        intent = "execute"
    return {"step": "route", "intent": intent}
