import os
from email import policy
from email.parser import BytesParser
from typing import Optional, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver


class EmlIngestState(TypedDict):
    file_path: str
    md: Optional[str]
    meta: Dict[str, Any]


def _email_to_markdown(msg) -> str:
    subject = msg.get('subject') or ''
    from_addr = msg.get('from') or ''
    to_addr = msg.get('to') or ''
    body = ''
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == 'text/plain':
                try:
                    body = part.get_content()
                    break
                except Exception:
                    continue
            elif ctype == 'text/html' and not body:
                try:
                    body = part.get_content()
                except Exception:
                    pass
    else:
        try:
            body = msg.get_content()
        except Exception:
            body = ''
    md_lines = [f"# {subject}", f"From: {from_addr}", f"To: {to_addr}", "", body or "(No content)"]
    return "\n\n".join(md_lines)


async def read_eml_to_md(state: EmlIngestState) -> EmlIngestState:
    fp = state.get('file_path')
    md = ''
    try:
        with open(fp, 'rb') as f:
            msg = BytesParser(policy=policy.default).parse(f)
        md = _email_to_markdown(msg)
    except Exception:
        md = state.get('md') or ''
    state['md'] = md
    return state


async def store_md(state: EmlIngestState) -> EmlIngestState:
    base_dir = os.environ.get('UPLOADS_DIR', '/app/uploads')
    out_dir = os.path.join(base_dir, 'ingest')
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(state.get('file_path') or 'mail.eml'))[0]
    out_md = os.path.join(out_dir, f'{stem}.md')
    with open(out_md, 'w', encoding='utf-8') as f:
        f.write(state.get('md') or '')
    m = state.get('meta', {})
    m['md_path'] = out_md
    state['meta'] = m
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
                'doc_id': state.get('file_path') or 'eml',
                'chunk_index': i,
                'metadata': {'type': 'eml', 'bbox': None, 'confidence': 0.0},
            }
            index_add(vec, meta)
            kw.add(chunk, meta)
    except Exception:
        pass
    return state


def create_eml_ingest_graph():
    g = StateGraph(EmlIngestState)
    g.add_node('read_eml_to_md', read_eml_to_md)
    g.add_node('store_md', store_md)
    g.set_entry_point('read_eml_to_md')
    g.add_edge('read_eml_to_md', 'store_md')
    memory = MemorySaver()
    return g.compile(checkpointer=memory)

