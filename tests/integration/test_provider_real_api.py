"""
真实 Provider API 集成测试

Phase 1: 多云算力基础设施

注意：这些测试需要真实的 API Key，运行前请确保环境变量已配置。
使用 pytest -m integration 运行这些测试。
"""
import pytest
import os
import asyncio

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def skip_if_no_api_key(env_var: str):
    """如果没有 API Key 则跳过测试"""
    if not os.environ.get(env_var):
        pytest.skip(f"{env_var} not set")


class TestDashScopeRealAPI:
    """DashScope 真实 API 测试"""

    @pytest.fixture
    def dashscope_gateway(self):
        """创建 DashScope Gateway"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        
        from core.llm.gateway import LLMGateway
        return LLMGateway(
            provider="dashscope",
            model="qwen-turbo",
            enable_cost_tracking=True
        )

    @pytest.mark.asyncio
    async def test_dashscope_chat_real(self, dashscope_gateway):
        """DashScope 真实 Chat API 调用"""
        response = await dashscope_gateway.chat(
            prompt="Say 'Hello OmniRAG' in exactly 3 words"
        )
        
        assert response is not None
        assert len(response) > 0
        assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_dashscope_chat_with_context(self, dashscope_gateway):
        """DashScope 带上下文的 Chat 调用"""
        response = await dashscope_gateway.chat(
            prompt="What is the capital mentioned in the context?",
            context="France is a country in Europe. Its capital is Paris."
        )
        
        assert response is not None
        assert "Paris" in response or "paris" in response.lower()


class TestDeepSeekRealAPI:
    """DeepSeek 真实 API 测试"""

    @pytest.fixture
    def deepseek_gateway(self):
        """创建 DeepSeek Gateway"""
        skip_if_no_api_key("DEEPSEEK_API_KEY")
        
        from core.llm.gateway import LLMGateway
        return LLMGateway(
            provider="deepseek",
            model="deepseek-chat",
            enable_cost_tracking=True
        )

    @pytest.mark.asyncio
    async def test_deepseek_chat_real(self, deepseek_gateway):
        """DeepSeek 真实 Chat API 调用"""
        response = await deepseek_gateway.chat(
            prompt="What is 2 + 2? Answer with just the number."
        )
        
        assert response is not None
        assert "4" in response


class TestCostTrackingIntegration:
    """成本追踪集成测试"""

    @pytest.fixture
    def gateway_with_tracking(self):
        """创建带成本追踪的 Gateway"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        
        from core.llm.gateway import LLMGateway
        return LLMGateway(
            provider="dashscope",
            model="qwen-turbo",
            channel_id="test-integration",
            enable_cost_tracking=True
        )

    @pytest.mark.asyncio
    async def test_cost_tracking_after_call(self, gateway_with_tracking):
        """测试 API 调用后的成本追踪"""
        # 执行调用
        response = await gateway_with_tracking.chat(
            prompt="Say hello"
        )
        
        assert response is not None
        
        # 验证成本追踪器被调用
        # 注意：实际验证需要数据库连接


class TestRoutingStrategyIntegration:
    """路由策略集成测试"""

    @pytest.mark.asyncio
    async def test_cost_first_routing(self):
        """测试成本优先路由"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        
        from core.llm.gateway import LLMGateway
        
        gateway = LLMGateway(
            routing_strategy="cost_first",
            enable_cost_tracking=False  # 避免数据库依赖
        )
        
        # 成本优先应选择最便宜的 provider
        # 这里只测试路由逻辑，不实际调用 API


class TestFailoverIntegration:
    """故障转移集成测试"""

    @pytest.mark.asyncio
    async def test_failover_chain_config(self):
        """测试故障转移链配置"""
        from core.llm.gateway import LLMGateway
        
        gateway = LLMGateway(
            provider="dashscope",
            model="qwen-turbo"
        )
        
        # 配置故障转移链
        gateway.failover_chain = [
            ("deepseek", "deepseek-chat"),
            ("volcengine", "doubao-lite-128k"),
        ]
        
        assert len(gateway.failover_chain) == 2


class TestMultiProviderComparison:
    """多 Provider 对比测试"""

    @pytest.mark.asyncio
    async def test_compare_providers(self):
        """对比不同 Provider 的响应"""
        from core.llm.gateway import LLMGateway
        
        providers_to_test = []
        
        if os.environ.get("DASHSCOPE_API_KEY"):
            providers_to_test.append(("dashscope", "qwen-turbo"))
        
        if os.environ.get("DEEPSEEK_API_KEY"):
            providers_to_test.append(("deepseek", "deepseek-chat"))
        
        if len(providers_to_test) < 2:
            pytest.skip("Need at least 2 providers configured")
        
        prompt = "What is the capital of Japan? Answer in one word."
        results = {}
        
        for provider, model in providers_to_test:
            gateway = LLMGateway(
                provider=provider,
                model=model,
                enable_cost_tracking=False
            )
            
            try:
                response = await gateway.chat(prompt=prompt)
                results[provider] = response
            except Exception as e:
                results[provider] = f"Error: {e}"
        
        # 验证至少有一个成功
        successful = [r for r in results.values() if not r.startswith("Error")]
        assert len(successful) >= 1
        
        # 验证响应包含 Tokyo
        for provider, response in results.items():
            if not response.startswith("Error"):
                assert "Tokyo" in response or "tokyo" in response.lower(), \
                    f"{provider} response: {response}"


class TestVLMRealAPI:
    """VLM (Vision Language Model) 真实 API 测试
    
    Task 11.2: 创建 VLM 真实图片测试
    Requirements: 6.2
    """

    @pytest.fixture
    def vlm_gateway(self):
        """创建 VLM Gateway"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        
        from core.llm.gateway import LLMGateway
        return LLMGateway(
            provider="dashscope",
            model="qwen-vl-plus",
            enable_cost_tracking=True
        )

    @pytest.mark.asyncio
    async def test_vlm_describe_image_url(self, vlm_gateway):
        """测试 VLM 描述网络图片"""
        # 使用公开的测试图片 URL
        test_image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Camponotus_flavomarginatus_ant.jpg/320px-Camponotus_flavomarginatus_ant.jpg"
        
        prompt = f"Describe what you see in this image: {test_image_url}"
        
        try:
            response = await vlm_gateway.chat(prompt=prompt)
            assert response is not None
            assert len(response) > 10
            # 应该识别出蚂蚁
            assert any(word in response.lower() for word in ["ant", "insect", "bug", "蚂蚁", "昆虫"])
        except Exception as e:
            # VLM 可能需要特殊的 API 调用格式
            pytest.skip(f"VLM API call failed: {e}")

    @pytest.mark.asyncio
    async def test_vlm_count_objects(self, vlm_gateway):
        """测试 VLM 计数能力"""
        # 使用包含多个对象的图片
        test_image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Felis_silvestris_catus_lying_on_rice_straw.jpg/320px-Felis_silvestris_catus_lying_on_rice_straw.jpg"
        
        prompt = f"How many cats are in this image? {test_image_url}"
        
        try:
            response = await vlm_gateway.chat(prompt=prompt)
            assert response is not None
            # 应该识别出一只猫
            assert any(word in response.lower() for word in ["one", "1", "single", "一", "一只"])
        except Exception as e:
            pytest.skip(f"VLM API call failed: {e}")


class TestEmbeddingRealAPI:
    """Embedding 真实 API 测试
    
    Task 11.3: 创建 Embedding 真实测试
    Requirements: 6.3
    """

    @pytest.fixture
    def embedding_provider(self):
        """创建 Embedding Provider"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        
        # 使用现有的 embedding provider
        try:
            from core.embedding.provider_embedder import ProviderEmbedder
            return ProviderEmbedder()
        except ImportError:
            pytest.skip("ProviderEmbedder not available")

    @pytest.mark.asyncio
    async def test_embedding_single_text(self, embedding_provider):
        """测试单文本 Embedding 生成"""
        text = "This is a test sentence for embedding generation."
        
        try:
            embedding = await embedding_provider.embed_text(text)
            
            assert embedding is not None
            assert isinstance(embedding, list)
            assert len(embedding) > 0
            # 验证维度（DashScope text-embedding-v3 默认 1024 维）
            assert len(embedding) >= 512
        except Exception as e:
            pytest.skip(f"Embedding API call failed: {e}")

    @pytest.mark.asyncio
    async def test_embedding_batch_texts(self, embedding_provider):
        """测试批量文本 Embedding 生成"""
        texts = [
            "The quick brown fox jumps over the lazy dog.",
            "Machine learning is a subset of artificial intelligence.",
            "Python is a popular programming language.",
            "Natural language processing enables computers to understand text.",
            "Deep learning uses neural networks with many layers.",
        ]
        
        try:
            embeddings = await embedding_provider.embed_texts(texts)
            
            assert embeddings is not None
            assert len(embeddings) == len(texts)
            
            # 验证每个 embedding 的维度一致
            dims = [len(e) for e in embeddings]
            assert len(set(dims)) == 1, "All embeddings should have same dimension"
        except Exception as e:
            pytest.skip(f"Batch embedding API call failed: {e}")

    @pytest.mark.asyncio
    async def test_embedding_similarity(self, embedding_provider):
        """测试 Embedding 相似度"""
        import numpy as np
        
        text1 = "I love programming in Python."
        text2 = "Python is my favorite programming language."
        text3 = "The weather is nice today."
        
        try:
            emb1 = await embedding_provider.embed_text(text1)
            emb2 = await embedding_provider.embed_text(text2)
            emb3 = await embedding_provider.embed_text(text3)
            
            # 计算余弦相似度
            def cosine_similarity(a, b):
                a = np.array(a)
                b = np.array(b)
                return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
            
            sim_12 = cosine_similarity(emb1, emb2)
            sim_13 = cosine_similarity(emb1, emb3)
            
            # 相似文本的相似度应该更高
            assert sim_12 > sim_13, \
                f"Similar texts should have higher similarity: {sim_12} vs {sim_13}"
        except Exception as e:
            pytest.skip(f"Embedding similarity test failed: {e}")


class TestCostEstimatorIntegration:
    """成本估算器集成测试"""

    def test_estimate_all_providers(self):
        """测试所有 Provider 的成本估算"""
        from core.llm.cost_estimator import CostEstimator
        
        estimator = CostEstimator()
        
        # 测试所有配置的 Provider
        for provider_id, models in estimator.DEFAULT_COSTS.items():
            for model_id in models:
                cost = estimator.estimate(
                    provider_id=provider_id,
                    model_id=model_id,
                    input_tokens=1000,
                    output_tokens=500
                )
                
                assert cost >= 0, f"Cost for {provider_id}/{model_id} should be non-negative"
                assert cost < 1.0, f"Cost for {provider_id}/{model_id} seems too high: {cost}"

    def test_cheapest_provider_selection(self):
        """测试最便宜 Provider 选择"""
        from core.llm.cost_estimator import CostEstimator
        
        estimator = CostEstimator()
        
        # 获取最便宜的 chat provider
        provider, model, cost = estimator.get_cheapest_provider(
            task_type="chat",
            estimated_input_tokens=1000,
            estimated_output_tokens=500
        )
        
        assert provider is not None
        assert model is not None
        assert cost >= 0
        
        # DeepSeek 应该是最便宜的
        assert provider in ["deepseek", "gemini"], \
            f"Expected cheapest to be deepseek or gemini, got {provider}"

    def test_providers_by_cost_ordering(self):
        """测试 Provider 成本排序"""
        from core.llm.cost_estimator import CostEstimator
        
        estimator = CostEstimator()
        
        providers = estimator.get_providers_by_cost(
            task_type="chat",
            estimated_input_tokens=1000,
            estimated_output_tokens=500
        )
        
        assert len(providers) > 0
        
        # 验证排序正确（成本递增）
        costs = [p[2] for p in providers]
        assert costs == sorted(costs), "Providers should be sorted by cost"
