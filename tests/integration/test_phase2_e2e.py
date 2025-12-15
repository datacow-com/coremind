"""
Phase 2 端到端集成测试

Phase 2: 垂直领域增强

测试完整的领域解读流程，包括：
- 领域路由
- 领域解读
- 成本追踪
- GPU 回退

Requirements: 8.1, 8.2, 8.3
"""
import pytest
import os
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def skip_if_no_api_key(env_var: str):
    """如果没有 API Key 则跳过测试"""
    if not os.environ.get(env_var):
        pytest.skip(f"{env_var} not set")


def skip_if_no_database():
    """如果没有数据库连接则跳过测试"""
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")


class TestDomainRouterE2E:
    """领域路由端到端测试 - Requirements 8.1"""

    @pytest.fixture
    def domain_router(self):
        """创建领域路由节点"""
        from core.ingestion.nodes.domain_router import DomainRouterNode
        return DomainRouterNode()

    @pytest.fixture
    def metaphysics_state(self):
        """创建命理文档状态"""
        return {
            "file_path": "test_metaphysics.txt",
            "file_type": "txt",
            "extracted_text": """
            八字命盘分析
            年柱：甲子
            月柱：乙丑
            日柱：丙寅
            时柱：丁卯
            五行木旺
            """,
            "parsed_blocks": [],
            "images": [],
            "strategy_config": {
                "enable_domain_interpretation": True,
            },
            "channel_id": "test-channel",
        }

    @pytest.fixture
    def comic_state(self):
        """创建漫画文档状态"""
        from PIL import Image
        import io
        
        # 创建测试图像
        img = Image.new('RGB', (400, 400), color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        image_data = buffer.getvalue()
        
        return {
            "file_path": "test_comic.jpg",
            "file_type": "jpg",
            "extracted_text": "四格漫画",
            "parsed_blocks": [],
            "images": [image_data],
            "strategy_config": {
                "enable_domain_interpretation": True,
                "domain_config": {
                    "comic": {"use_llm": False, "analyze_art_style": False}
                }
            },
            "channel_id": "test-channel",
        }

    @pytest.fixture
    def generic_state(self):
        """创建普通文档状态"""
        return {
            "file_path": "test_generic.txt",
            "file_type": "txt",
            "extracted_text": "This is a regular document about programming.",
            "parsed_blocks": [],
            "images": [],
            "strategy_config": {
                "enable_domain_interpretation": True,
            },
            "channel_id": "test-channel",
        }

    @pytest.mark.asyncio
    async def test_route_metaphysics_document(self, domain_router, metaphysics_state):
        """测试路由命理文档"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        # 注册命理领域
        from core.domains.registry import get_domain_registry, reset_domain_registry
        from core.domains.metaphysics.interpreter import register_metaphysics_domain
        
        reset_domain_registry()
        register_metaphysics_domain()
        
        try:
            result_state = await domain_router(metaphysics_state)
            
            # 验证领域解读结果被添加到 parsed_blocks
            parsed_blocks = result_state.get("parsed_blocks", [])
            interpretation_blocks = [
                b for b in parsed_blocks 
                if b.get("type") == "domain_interpretation"
            ]
            
            assert len(interpretation_blocks) >= 1
            assert interpretation_blocks[0]["domain_id"] == "metaphysics"
            
            # 验证质量指标
            quality_metrics = result_state.get("quality_metrics", {})
            assert "domain_interpretation_confidence" in quality_metrics
        finally:
            reset_domain_registry()

    @pytest.mark.asyncio
    async def test_route_generic_document(self, domain_router, generic_state):
        """测试路由普通文档（无领域匹配）"""
        from core.domains.registry import reset_domain_registry
        
        reset_domain_registry()
        
        result_state = await domain_router(generic_state)
        
        # 普通文档不应该有领域解读
        parsed_blocks = result_state.get("parsed_blocks", [])
        interpretation_blocks = [
            b for b in parsed_blocks 
            if b.get("type") == "domain_interpretation"
        ]
        
        assert len(interpretation_blocks) == 0

    @pytest.mark.asyncio
    async def test_route_disabled_interpretation(self, domain_router, metaphysics_state):
        """测试禁用领域解读"""
        metaphysics_state["strategy_config"]["enable_domain_interpretation"] = False
        
        result_state = await domain_router(metaphysics_state)
        
        # 禁用时不应该有领域解读
        parsed_blocks = result_state.get("parsed_blocks", [])
        interpretation_blocks = [
            b for b in parsed_blocks 
            if b.get("type") == "domain_interpretation"
        ]
        
        assert len(interpretation_blocks) == 0


class TestInterpretationResultStorage:
    """解读结果存储测试 - Requirements 8.2"""

    @pytest.fixture
    def domain_router(self):
        """创建领域路由节点"""
        from core.ingestion.nodes.domain_router import DomainRouterNode
        return DomainRouterNode()

    @pytest.mark.asyncio
    async def test_store_structured_data(self, domain_router):
        """测试存储结构化数据"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from core.domains.registry import reset_domain_registry
        from core.domains.metaphysics.interpreter import register_metaphysics_domain
        
        reset_domain_registry()
        register_metaphysics_domain()
        
        state = {
            "file_path": "test.txt",
            "file_type": "txt",
            "extracted_text": "甲子乙丑丙寅丁卯",
            "parsed_blocks": [],
            "images": [],
            "strategy_config": {"enable_domain_interpretation": True},
            "channel_id": "test",
        }
        
        try:
            result_state = await domain_router(state)
            
            # 检查结构化数据存储
            parsed_blocks = result_state.get("parsed_blocks", [])
            interpretation_blocks = [
                b for b in parsed_blocks 
                if b.get("type") == "domain_interpretation"
            ]
            
            if interpretation_blocks:
                block = interpretation_blocks[0]
                assert "structured_data" in block
                assert "confidence" in block
                assert "metadata" in block
        finally:
            reset_domain_registry()

    @pytest.mark.asyncio
    async def test_store_narrative_in_extracted_text(self, domain_router):
        """测试叙事文本追加到 extracted_text"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from core.domains.registry import reset_domain_registry
        from core.domains.metaphysics.interpreter import register_metaphysics_domain
        
        reset_domain_registry()
        register_metaphysics_domain()
        
        original_text = "原始文本内容"
        state = {
            "file_path": "test.txt",
            "file_type": "txt",
            "extracted_text": f"{original_text}\n甲子乙丑丙寅丁卯",
            "parsed_blocks": [],
            "images": [],
            "strategy_config": {"enable_domain_interpretation": True},
            "channel_id": "test",
        }
        
        try:
            result_state = await domain_router(state)
            
            # 检查叙事文本是否被追加
            extracted_text = result_state.get("extracted_text", "")
            assert original_text in extracted_text
            
            # 如果有领域解读，应该有分隔符
            parsed_blocks = result_state.get("parsed_blocks", [])
            has_interpretation = any(
                b.get("type") == "domain_interpretation" 
                for b in parsed_blocks
            )
            
            if has_interpretation:
                assert "Domain Interpretation" in extracted_text or len(extracted_text) > len(original_text)
        finally:
            reset_domain_registry()


class TestCostTrackingE2E:
    """成本追踪端到端测试 - Requirements 8.3"""

    @pytest.fixture
    def interpreter(self):
        """创建解读器"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from core.domains.metaphysics.interpreter import MetaphysicsInterpreter
        return MetaphysicsInterpreter()

    @pytest.mark.asyncio
    async def test_cost_estimation_before_llm_call(self, interpreter):
        """测试 LLM 调用前的成本估算"""
        # 测试成本估算
        estimated_cost = await interpreter._estimate_cost(
            input_tokens=1000,
            output_tokens=500,
            image_count=0,
            task_type="chat"
        )
        
        assert estimated_cost >= 0
        assert estimated_cost < 1.0  # 应该是合理的成本

    @pytest.mark.asyncio
    async def test_cost_estimation_with_images(self, interpreter):
        """测试带图像的成本估算"""
        estimated_cost = await interpreter._estimate_cost(
            input_tokens=500,
            output_tokens=500,
            image_count=1,
            task_type="vision"
        )
        
        assert estimated_cost >= 0

    @pytest.mark.asyncio
    async def test_budget_check_integration(self, interpreter):
        """测试预算检查集成"""
        allowed, remaining = await interpreter._check_budget_before_call(
            task_type="chat",
            estimated_input_tokens=100,
            estimated_output_tokens=100
        )
        
        assert isinstance(allowed, bool)
        assert isinstance(remaining, float)
        assert remaining >= 0


class TestGPUFallbackE2E:
    """GPU 回退端到端测试 - Requirements 7.1, 7.2"""

    @pytest.fixture
    def interpreter(self):
        """创建解读器"""
        from core.domains.metaphysics.interpreter import MetaphysicsInterpreter
        return MetaphysicsInterpreter()

    def test_gpu_availability_check(self, interpreter):
        """测试 GPU 可用性检查"""
        # 强制重新检查
        gpu_available = interpreter._check_gpu_available(force_recheck=True)
        
        assert isinstance(gpu_available, bool)

    def test_should_use_cloud_vlm(self, interpreter):
        """测试云端 VLM 判断"""
        should_use_cloud = interpreter._should_use_cloud_vlm()
        
        assert isinstance(should_use_cloud, bool)

    def test_gpu_fallback_when_unavailable(self, interpreter):
        """测试 GPU 不可用时的回退"""
        # 模拟 GPU 不可用
        interpreter._gpu_available = False
        
        should_use_cloud = interpreter._should_use_cloud_vlm()
        
        # 应该使用云端
        assert should_use_cloud is True

    def test_gpu_used_when_available(self, interpreter):
        """测试 GPU 可用时的行为"""
        # 模拟 GPU 可用
        interpreter._gpu_available = True
        
        should_use_cloud = interpreter._should_use_cloud_vlm()
        
        # 不应该使用云端（如果 requires_gpu 为 True）
        if interpreter.requires_gpu:
            assert should_use_cloud is False


class TestPipelineResilienceE2E:
    """管道弹性端到端测试 - Requirements 8.5"""

    @pytest.fixture
    def domain_router(self):
        """创建领域路由节点"""
        from core.ingestion.nodes.domain_router import DomainRouterNode
        return DomainRouterNode()

    @pytest.mark.asyncio
    async def test_continue_on_interpretation_error(self, domain_router):
        """测试解读错误时继续处理"""
        from core.domains.registry import get_domain_registry, reset_domain_registry
        from core.domains.base_interpreter import BaseDomainInterpreter, InterpretationResult
        from core.domains.ontology_schema import OntologySchema
        from core.domains.exceptions import DomainInterpretationError
        
        reset_domain_registry()
        registry = get_domain_registry()
        
        # 创建一个会失败的解读器
        class FailingInterpreter(BaseDomainInterpreter):
            domain_id = "failing"
            requires_gpu = False
            
            async def interpret(self, document, config=None):
                raise DomainInterpretationError(
                    "Intentional failure",
                    domain_id="failing",
                    stage="test"
                )
            
            def get_ontology(self):
                return OntologySchema.from_dict({
                    "domain_id": "failing",
                    "version": "1.0",
                    "entity_types": {},
                    "relationships": []
                })
            
            def validate_output(self, result):
                return True, []
        
        # 注册失败的解读器
        registry.register(
            domain_id="failing",
            interpreter_class=FailingInterpreter,
            ontology=FailingInterpreter().get_ontology(),
            detection_patterns=["failing_test"]
        )
        
        state = {
            "file_path": "test.txt",
            "file_type": "txt",
            "extracted_text": "failing_test content",
            "parsed_blocks": [],
            "images": [],
            "strategy_config": {"enable_domain_interpretation": True},
            "channel_id": "test",
        }
        
        try:
            # 应该不抛出异常
            result_state = await domain_router(state)
            
            # 应该记录错误
            error_log = result_state.get("error_log", [])
            assert len(error_log) > 0
            assert any("domain_router" in e.get("stage", "") for e in error_log)
        finally:
            reset_domain_registry()

    @pytest.mark.asyncio
    async def test_continue_on_unexpected_error(self, domain_router):
        """测试未预期错误时继续处理"""
        from core.domains.registry import get_domain_registry, reset_domain_registry
        from core.domains.base_interpreter import BaseDomainInterpreter
        from core.domains.ontology_schema import OntologySchema
        
        reset_domain_registry()
        registry = get_domain_registry()
        
        # 创建一个会抛出未预期错误的解读器
        class UnexpectedErrorInterpreter(BaseDomainInterpreter):
            domain_id = "unexpected"
            requires_gpu = False
            
            async def interpret(self, document, config=None):
                raise RuntimeError("Unexpected error")
            
            def get_ontology(self):
                return OntologySchema.from_dict({
                    "domain_id": "unexpected",
                    "version": "1.0",
                    "entity_types": {},
                    "relationships": []
                })
            
            def validate_output(self, result):
                return True, []
        
        registry.register(
            domain_id="unexpected",
            interpreter_class=UnexpectedErrorInterpreter,
            ontology=UnexpectedErrorInterpreter().get_ontology(),
            detection_patterns=["unexpected_test"]
        )
        
        state = {
            "file_path": "test.txt",
            "file_type": "txt",
            "extracted_text": "unexpected_test content",
            "parsed_blocks": [],
            "images": [],
            "strategy_config": {"enable_domain_interpretation": True},
            "channel_id": "test",
        }
        
        try:
            # 应该不抛出异常
            result_state = await domain_router(state)
            
            # 应该记录错误
            error_log = result_state.get("error_log", [])
            assert len(error_log) > 0
        finally:
            reset_domain_registry()


class TestFullPipelineE2E:
    """完整管道端到端测试"""

    @pytest.mark.asyncio
    async def test_metaphysics_full_pipeline(self):
        """测试命理完整管道"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from core.domains.registry import reset_domain_registry
        from core.domains.metaphysics.interpreter import (
            MetaphysicsInterpreter, 
            register_metaphysics_domain
        )
        from core.ingestion.nodes.domain_router import DomainRouterNode
        
        reset_domain_registry()
        register_metaphysics_domain()
        
        try:
            # 1. 创建文档状态
            state = {
                "file_path": "metaphysics_test.txt",
                "file_type": "txt",
                "extracted_text": """
                命理分析报告
                年柱：甲子  月柱：乙丑
                日柱：丙寅  时柱：丁卯
                五行：金0木4水1火2土1
                神煞：天乙贵人、文昌
                """,
                "parsed_blocks": [],
                "images": [],
                "strategy_config": {
                    "enable_domain_interpretation": True,
                    "domain_config": {
                        "metaphysics": {"use_llm": False, "detail_level": "brief"}
                    }
                },
                "channel_id": "test-e2e",
            }
            
            # 2. 执行领域路由
            router = DomainRouterNode()
            result_state = await router(state)
            
            # 3. 验证结果
            parsed_blocks = result_state.get("parsed_blocks", [])
            interpretation_blocks = [
                b for b in parsed_blocks 
                if b.get("type") == "domain_interpretation"
            ]
            
            assert len(interpretation_blocks) >= 1
            
            block = interpretation_blocks[0]
            assert block["domain_id"] == "metaphysics"
            assert "bazi" in block.get("structured_data", {})
            assert block["confidence"] > 0
            
            # 4. 验证质量指标
            quality_metrics = result_state.get("quality_metrics", {})
            assert quality_metrics.get("domain_id") == "metaphysics"
            
        finally:
            reset_domain_registry()

    @pytest.mark.asyncio
    async def test_comic_full_pipeline(self):
        """测试漫画完整管道"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from PIL import Image
        import io
        from core.domains.registry import reset_domain_registry
        from core.domains.comic.interpreter import register_comic_domain
        from core.ingestion.nodes.domain_router import DomainRouterNode
        
        reset_domain_registry()
        register_comic_domain()
        
        try:
            # 创建测试图像
            img = Image.new('RGB', (400, 400), color='white')
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG')
            image_data = buffer.getvalue()
            
            # 1. 创建文档状态
            state = {
                "file_path": "comic_test.jpg",
                "file_type": "jpg",
                "extracted_text": "四格漫画测试",
                "parsed_blocks": [],
                "images": [image_data],
                "strategy_config": {
                    "enable_domain_interpretation": True,
                    "domain_config": {
                        "comic": {
                            "use_llm": False, 
                            "detail_level": "brief",
                            "analyze_art_style": False
                        }
                    }
                },
                "channel_id": "test-e2e",
            }
            
            # 2. 执行领域路由
            router = DomainRouterNode()
            result_state = await router(state)
            
            # 3. 验证结果
            parsed_blocks = result_state.get("parsed_blocks", [])
            interpretation_blocks = [
                b for b in parsed_blocks 
                if b.get("type") == "domain_interpretation"
            ]
            
            assert len(interpretation_blocks) >= 1
            
            block = interpretation_blocks[0]
            assert block["domain_id"] == "comic"
            
        finally:
            reset_domain_registry()


class TestRealAPIFullPipeline:
    """使用真实 API 的完整管道测试"""

    @pytest.mark.asyncio
    async def test_metaphysics_with_llm_narrative(self):
        """测试命理管道 - 使用 LLM 生成叙事"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from core.domains.registry import reset_domain_registry
        from core.domains.metaphysics.interpreter import register_metaphysics_domain
        from core.ingestion.nodes.domain_router import DomainRouterNode
        
        reset_domain_registry()
        register_metaphysics_domain()
        
        try:
            # 真实命理文档
            state = {
                "file_path": "real_metaphysics.txt",
                "file_type": "txt",
                "extracted_text": """
                【命主信息】
                出生时间：农历甲子年乙丑月丙寅日丁卯时
                
                【八字排盘】
                年柱：甲子（海中金）
                月柱：乙丑（海中金）
                日柱：丙寅（炉中火）
                时柱：丁卯（炉中火）
                
                【五行分析】
                金：0个  木：4个  水：1个  火：2个  土：1个
                五行木旺，缺金
                
                【神煞】
                天乙贵人：丑、未
                文昌：巳
                驿马：寅
                桃花：卯
                华盖：辰
                
                【命理解读】
                此命木火通明，聪明伶俐，适合从事文化、教育、艺术等行业。
                """,
                "parsed_blocks": [],
                "images": [],
                "strategy_config": {
                    "enable_domain_interpretation": True,
                    "domain_config": {
                        "metaphysics": {
                            "use_llm": True,
                            "detail_level": "comprehensive",
                            "extract_shen_sha": True
                        }
                    }
                },
                "channel_id": "test-real-api",
            }
            
            router = DomainRouterNode()
            result_state = await router(state)
            
            # 验证结果
            parsed_blocks = result_state.get("parsed_blocks", [])
            interpretation_blocks = [
                b for b in parsed_blocks 
                if b.get("type") == "domain_interpretation"
            ]
            
            assert len(interpretation_blocks) >= 1
            
            block = interpretation_blocks[0]
            assert block["domain_id"] == "metaphysics"
            
            # 验证八字提取
            bazi = block.get("structured_data", {}).get("bazi", {})
            assert bazi.get("year_pillar") == "甲子"
            assert bazi.get("month_pillar") == "乙丑"
            assert bazi.get("day_pillar") == "丙寅"
            assert bazi.get("hour_pillar") == "丁卯"
            
            # 验证神煞提取
            shen_sha = block.get("structured_data", {}).get("shen_sha", [])
            assert len(shen_sha) >= 3
            
            # 验证叙事文本
            assert block.get("content") is not None
            assert len(block.get("content", "")) > 50
            
        finally:
            reset_domain_registry()

    @pytest.mark.asyncio
    async def test_comic_with_vlm_analysis(self):
        """测试漫画管道 - 使用 VLM 分析"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from PIL import Image, ImageDraw
        import io
        from core.domains.registry import reset_domain_registry
        from core.domains.comic.interpreter import register_comic_domain
        from core.ingestion.nodes.domain_router import DomainRouterNode
        
        reset_domain_registry()
        register_comic_domain()
        
        try:
            # 创建更真实的漫画图像
            img = Image.new('RGB', (800, 800), color='white')
            draw = ImageDraw.Draw(img)
            
            # 绘制 4 个分格
            panels = [
                (10, 10, 390, 390),
                (410, 10, 790, 390),
                (10, 410, 390, 790),
                (410, 410, 790, 790),
            ]
            
            for i, (x1, y1, x2, y2) in enumerate(panels):
                draw.rectangle([x1, y1, x2, y2], outline='black', width=3)
                
                # 绘制角色
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                draw.ellipse([cx-40, cy-80, cx+40, cy], fill='peachpuff', outline='black')
                draw.rectangle([cx-30, cy, cx+30, cy+80], fill='lightblue', outline='black')
                
                # 绘制对话气泡
                draw.ellipse([cx+50, cy-100, cx+150, cy-50], fill='white', outline='black')
            
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=90)
            image_data = buffer.getvalue()
            
            state = {
                "file_path": "real_comic.jpg",
                "file_type": "jpg",
                "extracted_text": "四格漫画",
                "parsed_blocks": [],
                "images": [image_data],
                "strategy_config": {
                    "enable_domain_interpretation": True,
                    "domain_config": {
                        "comic": {
                            "use_llm": True,
                            "detail_level": "detailed",
                            "reading_order": "ltr",
                            "analyze_art_style": True
                        }
                    }
                },
                "channel_id": "test-real-api",
            }
            
            router = DomainRouterNode()
            result_state = await router(state)
            
            # 验证结果
            parsed_blocks = result_state.get("parsed_blocks", [])
            interpretation_blocks = [
                b for b in parsed_blocks 
                if b.get("type") == "domain_interpretation"
            ]
            
            assert len(interpretation_blocks) >= 1
            
            block = interpretation_blocks[0]
            assert block["domain_id"] == "comic"
            
            # 验证分格检测
            panels = block.get("structured_data", {}).get("panel", [])
            assert isinstance(panels, list)
            
        finally:
            reset_domain_registry()

    @pytest.mark.asyncio
    async def test_multiple_documents_pipeline(self):
        """测试多文档管道处理"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from core.domains.registry import reset_domain_registry
        from core.domains.metaphysics.interpreter import register_metaphysics_domain
        from core.ingestion.nodes.domain_router import DomainRouterNode
        
        reset_domain_registry()
        register_metaphysics_domain()
        
        try:
            # 多个命理文档
            documents = [
                {
                    "content": "甲子乙丑丙寅丁卯，五行木旺，天乙贵人照命",
                    "expected_year": "甲子",
                },
                {
                    "content": "壬辰癸巳甲午乙未，五行水木为主，驿马桃花并见",
                    "expected_year": "壬辰",
                },
                {
                    "content": "庚申辛酉壬戌癸亥，五行金水旺，华盖临身",
                    "expected_year": "庚申",
                },
            ]
            
            router = DomainRouterNode()
            
            for doc in documents:
                state = {
                    "file_path": "test.txt",
                    "file_type": "txt",
                    "extracted_text": doc["content"],
                    "parsed_blocks": [],
                    "images": [],
                    "strategy_config": {
                        "enable_domain_interpretation": True,
                        "domain_config": {
                            "metaphysics": {"use_llm": False}
                        }
                    },
                    "channel_id": "test-multi",
                }
                
                result_state = await router(state)
                
                # 验证每个文档都被正确处理
                parsed_blocks = result_state.get("parsed_blocks", [])
                interpretation_blocks = [
                    b for b in parsed_blocks 
                    if b.get("type") == "domain_interpretation"
                ]
                
                assert len(interpretation_blocks) >= 1
                
                bazi = interpretation_blocks[0].get("structured_data", {}).get("bazi", {})
                assert bazi.get("year_pillar") == doc["expected_year"]
                
        finally:
            reset_domain_registry()


class TestConfigurationVariations:
    """配置变体测试"""

    @pytest.mark.asyncio
    async def test_detail_level_variations(self):
        """测试不同 detail_level 配置"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from core.domains.metaphysics.interpreter import MetaphysicsInterpreter
        
        interpreter = MetaphysicsInterpreter()
        document = {
            "content": "甲子乙丑丙寅丁卯，五行木旺，天乙贵人",
            "file_type": "txt",
        }
        
        detail_levels = ["brief", "detailed", "comprehensive"]
        results = {}
        
        for level in detail_levels:
            result = await interpreter.interpret(
                document,
                config={"use_llm": False, "detail_level": level}
            )
            results[level] = result
            
            assert result is not None
            assert result.metadata.get("detail_level") == level

    @pytest.mark.asyncio
    async def test_shen_sha_extraction_toggle(self):
        """测试神煞提取开关"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from core.domains.metaphysics.interpreter import MetaphysicsInterpreter
        
        interpreter = MetaphysicsInterpreter()
        document = {
            "content": "甲子乙丑丙寅丁卯，天乙贵人、文昌、驿马",
            "file_type": "txt",
        }
        
        # 启用神煞提取
        result_with = await interpreter.interpret(
            document,
            config={"use_llm": False, "extract_shen_sha": True}
        )
        
        # 禁用神煞提取
        result_without = await interpreter.interpret(
            document,
            config={"use_llm": False, "extract_shen_sha": False}
        )
        
        # 启用时应该有神煞
        assert len(result_with.structured_data.get("shen_sha", [])) > 0
        
        # 禁用时不应该有神煞
        assert len(result_without.structured_data.get("shen_sha", [])) == 0

    @pytest.mark.asyncio
    async def test_reading_order_variations(self):
        """测试不同阅读顺序配置"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from PIL import Image
        import io
        from core.domains.comic.interpreter import ComicInterpreter
        
        interpreter = ComicInterpreter()
        
        # 创建测试图像
        img = Image.new('RGB', (400, 400), color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        image_data = buffer.getvalue()
        
        document = {"images": [image_data]}
        
        for order in ["ltr", "rtl", "auto"]:
            result = await interpreter.interpret(
                document,
                config={
                    "use_llm": False,
                    "reading_order": order,
                    "analyze_art_style": False
                }
            )
            
            assert result is not None
            assert result.metadata.get("reading_order") == order

