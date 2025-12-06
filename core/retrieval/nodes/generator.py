import re
from typing import List, Dict
from core.state import RetrievalState
from core.llm.gateway import LLMGateway

class CitationGenerator:
    def __init__(self):
        self.gateway = LLMGateway()

    async def __call__(self, state: RetrievalState) -> RetrievalState:
        cfg = state['strategy_config']
        query = state['input_query']
        docs = state['reranked_results'][:cfg.get('top_k', 5)]
        
        if not state.get('is_relevant', False) or not docs:
            state['final_answer'] = "抱歉，未找到相关信息回答您的问题。"
            state['citations'] = []
            state['confidence'] = 0.0
            return state
            
        # Build Context
        context = ""
        for i, doc in enumerate(docs):
            metadata = doc.get('metadata', {})
            context += f"\n[{i}] 来源: {metadata.get('doc_id', 'unknown')}, 页码: {metadata.get('page_num', 'N/A')}\n"
            context += f"内容: {doc.get('content', '')}\n"
            
        system_prompt = """
        你是一个严谨的助手，必须基于提供的上下文回答问题。
        
        规则：
        1. 每个事实必须标注引用来源，格式：<cite id="[索引]">事实内容</cite>
        2. 若上下文无法回答，明确告知"根据提供的资料无法回答"
        3. 不要编造信息
        4. 保持专业、准确、简洁
        """
        
        user_prompt = f"""
        上下文：
        {context}
        
        问题：{query}
        
        请回答并标注引用。
        """
        
        answer = await self.gateway.chat(prompt=user_prompt, context=None) # context already in prompt if gateway supports prompt only
        
        # Parse Citations
        citations = []
        cite_pattern = r'<cite id="\[(\d+)\]">(.*?)</cite>'
        
        # We need to extract the citation content and map it back to the doc
        # But usually citation is just marker. 
        # Let's assume simple marker <cite id="[0]">...</cite> wraps the text.
        # Or maybe just [0] at end of sentence? 
        # The prompt asks for XML-like tag.
        
        matches = re.finditer(cite_pattern, answer, re.DOTALL)
        for match in matches:
            idx = int(match.group(1))
            if idx < len(docs):
                doc = docs[idx]
                citations.append({
                    "doc_id": doc.get('metadata', {}).get('doc_id'),
                    "page": doc.get('metadata', {}).get('page_num'),
                    "bbox": doc.get('metadata', {}).get('bbox'),
                    "content": match.group(2), # The text that was cited
                    "chunk_id": doc.get('id')
                })
        
        state['final_answer'] = answer
        state['citations'] = citations
        state['confidence'] = len(citations) / max(1, answer.count('<cite'))
        
        return state

