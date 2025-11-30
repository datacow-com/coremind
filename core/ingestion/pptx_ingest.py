import os
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, List
from typing_extensions import TypedDict
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver


class PptxIngestState(TypedDict):
    file_path: str
    md: Optional[str]
    meta: Dict[str, Any]


def _slide_text(xml_bytes: bytes) -> List[str]:
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return []
    texts: List[str] = []
    ns_a = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
    for t in root.findall(f'.//{ns_a}t'):
        if t.text:
            texts.append(t.text)
    return texts


async def read_pptx_to_md(state: PptxIngestState) -> PptxIngestState:
    fp = state.get('file_path')
    md_lines: List[str] = []
    try:
        with zipfile.ZipFile(fp, 'r') as z:
            slide_names = sorted([n for n in z.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')])
            for idx, name in enumerate(slide_names, start=1):
                with z.open(name) as f:
                    lines = _slide_text(f.read())
                md_lines.append(f'# Slide {idx}')
                for ln in lines:
                    if ln.strip():
                        md_lines.append(f'- {ln.strip()}')
                md_lines.append('')
    except Exception:
        pass
    md = '\n'.join(md_lines) if md_lines else '# Slides\n\n(No content)'
    state['md'] = md
    return state


async def store_md(state: PptxIngestState) -> PptxIngestState:
    base_dir = os.environ.get('UPLOADS_DIR', '/app/uploads')
    out_dir = os.path.join(base_dir, 'ingest')
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(state.get('file_path') or 'deck.pptx'))[0]
    out_md = os.path.join(out_dir, f'{stem}.md')
    with open(out_md, 'w', encoding='utf-8') as f:
        f.write(state.get('md') or '')
    m = state.get('meta', {})
    m['md_path'] = out_md
    state['meta'] = m
    # write to index
    try:
        from core.embedding.provider_embedder import Embedder
        from core.storage.index_router import add as index_add
        from core.storage.keyword_index import get_keyword_index
        md_text = state.get('md') or ''
        paras = [p.strip() for p in md_text.split('\n\n') if p.strip()]
        emb = Embedder(dim=256)
        kw = get_keyword_index()
        for i, chunk in enumerate(paras):
            vec = emb.embed(chunk)
            meta = {
                'id': f'{state.get("file_path")}-chunk-{i}',
                'content': chunk,
                'page_num': 1,
                'doc_id': state.get('file_path') or 'pptx',
                'chunk_index': i,
                'metadata': {'type': 'pptx', 'bbox': None, 'confidence': 0.0},
            }
            index_add(vec, meta)
            kw.add(chunk, meta)
    except Exception:
        pass
    return state


def create_pptx_ingest_graph():
    g = StateGraph(PptxIngestState)
    g.add_node('read_pptx_to_md', read_pptx_to_md)
    g.add_node('store_md', store_md)
    g.set_entry_point('read_pptx_to_md')
    g.add_edge('read_pptx_to_md', 'store_md')
    memory = MemorySaver()
    return g.compile(checkpointer=memory)

