import asyncio
import networkx as nx
import community as community_louvain # python-louvain
from core.storage.blob_store import get_blob_store
from core.llm.gateway import LLMGateway
from typing import Dict, Any

class GraphRAGProcessor:
    def __init__(self, kb_name: str, config: Dict[str, Any] = None):
        self.kb_name = kb_name
        self.config = config or {}
        self.blob_store = get_blob_store()
        
        llm_model = self.config.get("llm_model")
        self.llm = LLMGateway(model=llm_model)
        
    async def build_graph(self, entities: list, relations: list):
        G = nx.Graph()
        for e in entities:
            G.add_node(e['name'], type=e['type'], desc=e.get('desc'))
        for r in relations:
            G.add_edge(r['src'], r['tgt'], desc=r.get('desc'))
            
        # Community Detection (Leiden or Louvain)
        try:
            partition = community_louvain.best_partition(G)
        except ImportError:
            # Fallback if louvain not available or graph empty
            partition = {n: 0 for n in G.nodes()}
        
        # Summarize Communities
        summaries = {}
        for com_id in set(partition.values()):
            nodes = [n for n, c in partition.items() if c == com_id]
            # Summarize nodes in community
            summary = await self._summarize_community(nodes)
            summaries[com_id] = summary
            
        # Store
        data = {
            "graph": nx.node_link_data(G),
            "communities": summaries,
            "partition": partition
        }
        import json
        await self.blob_store.put(f"graphrag/{self.kb_name}.json", json.dumps(data).encode('utf-8'))
        
    async def _summarize_community(self, nodes: list) -> str:
        # Real summary using LLM
        node_names = ", ".join(nodes[:50]) # Limit context
        prompt = f"Summarize the common theme and relationships among these entities: {node_names}"
        return await self.llm.chat(prompt)
