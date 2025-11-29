import numpy as np
from core.storage.index_router import add, search


def test_index_router_add_and_search_local():
    vec = np.ones(256, dtype=np.float32) / np.sqrt(256)
    meta = {"id": "t1", "content": "hello world", "page_num": 1, "doc_id": "doc", "chunk_index": 0, "metadata": {}}
    add(vec, meta)
    res = search(vec, top_k=1)
    assert isinstance(res, list)
    assert len(res) >= 1
