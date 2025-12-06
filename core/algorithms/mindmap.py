import json
from typing import Dict, Any
from core.storage.blob_store import get_blob_store
from core.llm.gateway import LLMGateway

class MindmapProcessor:
    def __init__(self, kb_name: str, config: Dict[str, Any] = None):
        self.kb_name = kb_name
        self.config = config or {}
        self.blob_store = get_blob_store()
        
        llm_model = self.config.get("llm_model")
        self.llm = LLMGateway(model=llm_model)

    async def generate(self, root_topic: str):
        # Recursive generation
        outline = {"title": root_topic, "children": []}
        
        prompt = f"Generate 5 key subtopics for the subject: {root_topic}. Output as a list of items."
        resp = await self.llm.chat(prompt)
        
        # Parse resp
        for line in resp.split('\n'):
            clean_line = line.strip().lstrip('-').lstrip('1234567890.').strip()
            if clean_line:
                outline['children'].append({"title": clean_line, "children": []})
                
        # Store
        await self.blob_store.put(f"mindmap/{self.kb_name}.json", json.dumps(outline).encode('utf-8'))
