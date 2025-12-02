def test_base_retriever_adapter_outputs(monkeypatch):
    from core.retriever.base_retriever import OmniIndexRetriever

    def fake_embed(self, text):
        return [0.0] * 256

    # ensure embedder works without external deps
    import core.embedding.provider_embedder as pe

    monkeypatch.setattr(pe.Embedder, "embed", fake_embed)
    retr = OmniIndexRetriever(top_k=2)
    docs = retr._get_relevant_documents("hello")
    assert isinstance(docs, list)
