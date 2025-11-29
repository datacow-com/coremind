from core.embedding.provider_embedder import Embedder


def test_provider_embedder_shape_and_type():
    emb = Embedder(dim=256)
    v = emb.embed("hello world")
    assert v.shape == (256,)
    assert v.dtype.name == "float32"

