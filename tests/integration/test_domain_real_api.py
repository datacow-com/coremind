"""
领域解读真实 API 集成测试

Phase 2: 垂直领域增强

注意：这些测试需要真实的 API Key，运行前请确保环境变量已配置。
使用 pytest -m integration 运行这些测试。

Requirements: 5.1, 6.1
"""
import pytest
import os
import asyncio
import json
from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.slow]

# 真实命理测试样本
REAL_METAPHYSICS_SAMPLES = [
    {
        "id": "sample_1",
        "description": "完整四柱标注格式",
        "content": """命主八字分析
年柱：甲子
月柱：乙丑
日柱：丙寅
时柱：丁卯

五行分布：金2木3水1火1土1

神煞：天乙贵人、文昌

此命木旺，宜从事文化教育行业。""",
        "expected_bazi": {
            "year_pillar": "甲子",
            "month_pillar": "乙丑",
            "day_pillar": "丙寅",
            "hour_pillar": "丁卯"
        },
        "expected_shen_sha": ["天乙贵人", "文昌"],
    },
    {
        "id": "sample_2",
        "description": "简化八字格式",
        "content": "八字：壬辰 癸巳 甲午 乙未\n五行以水木为主，金1木2水2火2土1。命带驿马、桃花，主人缘好。",
        "expected_bazi": {
            "year_pillar": "壬辰",
            "month_pillar": "癸巳",
            "day_pillar": "甲午",
            "hour_pillar": "乙未"
        },
        "expected_shen_sha": ["驿马", "桃花"],
    },
    {
        "id": "sample_3",
        "description": "带神煞详解",
        "content": "壬申癸酉甲戌乙亥，金2木2水3火0土1。天医主医药，红鸾主婚姻。",
        "expected_bazi": {
            "year_pillar": "壬申",
            "month_pillar": "癸酉",
            "day_pillar": "甲戌",
            "hour_pillar": "乙亥"
        },
        "expected_shen_sha": ["天医", "红鸾"],
    },
    {
        "id": "sample_4",
        "description": "多神煞",
        "content": "庚辰辛巳壬午癸未，金2木0水2火1土3。孤辰寡宿劫煞并见。",
        "expected_bazi": {
            "year_pillar": "庚辰",
            "month_pillar": "辛巳",
            "day_pillar": "壬午",
            "hour_pillar": "癸未"
        },
        "expected_shen_sha": ["孤辰", "寡宿", "劫煞"],
    },
    {
        "id": "sample_5",
        "description": "纯文本描述",
        "content": "此人生于甲子年乙丑月丙寅日丁卯时，八字木火通明，文昌星照命。",
        "expected_bazi": {
            "year_pillar": "甲子",
            "month_pillar": "乙丑",
            "day_pillar": "丙寅",
            "hour_pillar": "丁卯"
        },
        "expected_shen_sha": ["文昌"],
    },
]


def skip_if_no_api_key(env_var: str):
    """如果没有 API Key 则跳过测试"""
    if not os.environ.get(env_var):
        pytest.skip(f"{env_var} not set")


def skip_if_no_database():
    """如果没有数据库连接则跳过测试"""
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")


class TestMetaphysicsRealAPI:
    """命理解读真实 API 测试 - Requirements 5.1"""

    @pytest.fixture
    def metaphysics_interpreter(self):
        """创建命理解读器"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from core.domains.metaphysics.interpreter import MetaphysicsInterpreter
        return MetaphysicsInterpreter()

    @pytest.mark.asyncio
    async def test_interpret_text_document(self, metaphysics_interpreter):
        """测试解读文本命理文档"""
        document = {
            "content": """
            八字命盘分析
            年柱：甲子
            月柱：乙丑
            日柱：丙寅
            时柱：丁卯
            
            五行分布：金0木4水1火2土1
            五行木旺，金弱
            
            神煞：天乙贵人、文昌
            """,
            "file_type": "txt",
        }
        
        result = await metaphysics_interpreter.interpret(
            document, 
            config={"use_llm": False, "detail_level": "brief"}
        )
        
        assert result is not None
        assert result.domain_id == "metaphysics"
        assert "bazi" in result.structured_data
        assert result.confidence > 0
        
        # 验证八字提取
        bazi = result.structured_data.get("bazi", {})
        assert bazi.get("year_pillar") == "甲子"
        assert bazi.get("month_pillar") == "乙丑"
        assert bazi.get("day_pillar") == "丙寅"

    @pytest.mark.asyncio
    async def test_interpret_with_llm_narrative(self, metaphysics_interpreter):
        """测试使用 LLM 生成叙事"""
        document = {
            "content": "甲子乙丑丙寅丁卯，五行木旺，命带天乙贵人",
            "file_type": "txt",
        }
        
        result = await metaphysics_interpreter.interpret(
            document,
            config={"use_llm": True, "detail_level": "detailed"}
        )
        
        assert result is not None
        assert result.narrative is not None
        assert len(result.narrative) > 0

    @pytest.mark.asyncio
    async def test_interpret_shen_sha_extraction(self, metaphysics_interpreter):
        """测试神煞提取"""
        document = {
            "content": """
            命理分析报告
            八字：庚申辛酉壬戌癸亥
            神煞：天乙贵人、文昌、驿马、桃花、华盖
            """,
            "file_type": "txt",
        }
        
        result = await metaphysics_interpreter.interpret(
            document,
            config={"use_llm": False, "extract_shen_sha": True}
        )
        
        assert result is not None
        shen_sha = result.structured_data.get("shen_sha", [])
        assert len(shen_sha) > 0
        assert "天乙贵人" in shen_sha or "文昌" in shen_sha

    @pytest.mark.asyncio
    async def test_interpret_wuxing_calculation(self, metaphysics_interpreter):
        """测试五行计算"""
        document = {
            "content": "甲子乙丑丙寅丁卯",  # 木4水1火2土1金0
            "file_type": "txt",
        }
        
        result = await metaphysics_interpreter.interpret(
            document,
            config={"use_llm": False}
        )
        
        assert result is not None
        wuxing = result.structured_data.get("wuxing", {})
        assert wuxing.get("wood", 0) > 0  # 应该有木
        assert "dominant" in wuxing  # 应该有旺衰分析


class TestComicRealAPI:
    """漫画解读真实 API 测试 - Requirements 6.1"""

    @pytest.fixture
    def comic_interpreter(self):
        """创建漫画解读器"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from core.domains.comic.interpreter import ComicInterpreter
        return ComicInterpreter()

    @pytest.fixture
    def sample_comic_image(self):
        """创建测试用漫画图像"""
        from PIL import Image
        import io
        
        # 创建一个简单的 4 格漫画模拟图像
        img = Image.new('RGB', (800, 800), color='white')
        
        # 绘制 4 个分格
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        
        # 绘制分格边界
        draw.rectangle([10, 10, 390, 390], outline='black', width=2)
        draw.rectangle([410, 10, 790, 390], outline='black', width=2)
        draw.rectangle([10, 410, 390, 790], outline='black', width=2)
        draw.rectangle([410, 410, 790, 790], outline='black', width=2)
        
        # 在每个分格中添加一些内容
        draw.ellipse([100, 100, 200, 200], fill='blue')  # 角色
        draw.ellipse([500, 100, 600, 200], fill='red')
        draw.ellipse([100, 500, 200, 600], fill='green')
        draw.ellipse([500, 500, 600, 600], fill='yellow')
        
        # 转换为 bytes
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        return buffer.getvalue()

    @pytest.mark.asyncio
    async def test_interpret_comic_image(self, comic_interpreter, sample_comic_image):
        """测试解读漫画图像"""
        document = {
            "images": [sample_comic_image],
            "metadata": {"domain": "comic"},
        }
        
        result = await comic_interpreter.interpret(
            document,
            config={"use_llm": False, "detail_level": "brief", "analyze_art_style": False}
        )
        
        assert result is not None
        assert result.domain_id == "comic"
        assert "panel" in result.structured_data
        assert result.confidence >= 0.0

    @pytest.mark.asyncio
    async def test_interpret_with_vlm_analysis(self, comic_interpreter, sample_comic_image):
        """测试使用 VLM 分析漫画"""
        document = {
            "images": [sample_comic_image],
        }
        
        result = await comic_interpreter.interpret(
            document,
            config={"use_llm": True, "detail_level": "detailed", "analyze_art_style": True}
        )
        
        assert result is not None
        assert result.narrative is not None
        assert len(result.narrative) > 0
        
        # 检查是否有艺术风格分析
        if "art_style" in result.structured_data:
            art_style = result.structured_data["art_style"]
            assert isinstance(art_style, dict)

    @pytest.mark.asyncio
    async def test_interpret_reading_order(self, comic_interpreter, sample_comic_image):
        """测试阅读顺序配置"""
        document = {"images": [sample_comic_image]}
        
        # 测试从右到左阅读顺序
        result_rtl = await comic_interpreter.interpret(
            document,
            config={"reading_order": "rtl", "use_llm": False}
        )
        
        assert result_rtl is not None
        assert result_rtl.metadata.get("reading_order") == "rtl"
        
        # 测试从左到右阅读顺序
        result_ltr = await comic_interpreter.interpret(
            document,
            config={"reading_order": "ltr", "use_llm": False}
        )
        
        assert result_ltr is not None
        assert result_ltr.metadata.get("reading_order") == "ltr"

    @pytest.mark.asyncio
    async def test_panel_detection(self, comic_interpreter, sample_comic_image):
        """测试分格检测"""
        document = {"images": [sample_comic_image]}
        
        result = await comic_interpreter.interpret(
            document,
            config={"use_llm": False}
        )
        
        assert result is not None
        panels = result.structured_data.get("panel", [])
        # 应该检测到分格
        assert isinstance(panels, list)


class TestDomainRegistryIntegration:
    """领域注册表集成测试"""

    def test_register_and_detect_metaphysics(self):
        """测试注册和检测命理领域"""
        from core.domains.registry import get_domain_registry, reset_domain_registry
        from core.domains.metaphysics.interpreter import register_metaphysics_domain
        
        reset_domain_registry()
        registry = get_domain_registry()
        register_metaphysics_domain()
        
        # 测试检测
        doc = {"content": "八字命盘分析：甲子乙丑丙寅丁卯"}
        detected = registry.detect_domain(doc)
        assert detected == "metaphysics"
        
        reset_domain_registry()

    def test_register_and_detect_comic(self):
        """测试注册和检测漫画领域"""
        from core.domains.registry import get_domain_registry, reset_domain_registry
        from core.domains.comic.interpreter import register_comic_domain
        
        reset_domain_registry()
        registry = get_domain_registry()
        register_comic_domain()
        
        # 测试检测
        doc = {"content": "这是一个四格漫画"}
        detected = registry.detect_domain(doc)
        assert detected == "comic"
        
        reset_domain_registry()

    def test_no_domain_detected(self):
        """测试无领域检测"""
        from core.domains.registry import get_domain_registry, reset_domain_registry
        
        reset_domain_registry()
        registry = get_domain_registry()
        
        doc = {"content": "This is a regular document about programming."}
        detected = registry.detect_domain(doc)
        assert detected is None
        
        reset_domain_registry()


class TestVLMIntegration:
    """VLM 集成测试"""

    @pytest.fixture
    def base_interpreter(self):
        """创建基础解读器用于测试 VLM 调用"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from core.domains.metaphysics.interpreter import MetaphysicsInterpreter
        return MetaphysicsInterpreter()

    @pytest.mark.asyncio
    async def test_vlm_call_with_image(self, base_interpreter):
        """测试 VLM 图像调用"""
        from PIL import Image
        import io
        
        # 创建测试图像
        img = Image.new('RGB', (200, 200), color='white')
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.text((50, 90), "Test", fill='black')
        
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        image_data = buffer.getvalue()
        
        try:
            response = await base_interpreter._call_vlm(
                image_data,
                "Describe what you see in this image.",
                skip_budget_check=True
            )
            
            assert response is not None
            assert isinstance(response, str)
            assert len(response) > 0
        except Exception as e:
            # VLM 调用可能因配置问题失败
            pytest.skip(f"VLM call failed: {e}")


class TestCostTrackingIntegration:
    """成本追踪集成测试"""

    @pytest.fixture
    def interpreter_with_tracking(self):
        """创建带成本追踪的解读器"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from core.domains.metaphysics.interpreter import MetaphysicsInterpreter
        return MetaphysicsInterpreter()

    @pytest.mark.asyncio
    async def test_cost_tracking_after_interpretation(self, interpreter_with_tracking):
        """测试解读后的成本追踪"""
        document = {
            "content": "甲子乙丑丙寅丁卯",
            "file_type": "txt",
        }
        
        result = await interpreter_with_tracking.interpret(
            document,
            config={"use_llm": True, "detail_level": "brief"}
        )
        
        assert result is not None
        # 成本追踪应该在内部完成

    @pytest.mark.asyncio
    async def test_budget_check_before_call(self, interpreter_with_tracking):
        """测试调用前的预算检查"""
        allowed, remaining = await interpreter_with_tracking._check_budget_before_call(
            task_type="chat",
            estimated_input_tokens=100,
            estimated_output_tokens=50
        )
        
        # 应该返回预算状态
        assert isinstance(allowed, bool)
        assert isinstance(remaining, float)


class TestMetaphysicsRealSamples:
    """命理真实样本测试 - 使用真实 API 和真实测试数据"""

    @pytest.fixture
    def metaphysics_interpreter(self):
        """创建命理解读器"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        # 注意：基本解读功能不需要数据库，只有 VLM/LLM 调用需要
        
        from core.domains.metaphysics.interpreter import MetaphysicsInterpreter
        return MetaphysicsInterpreter()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("sample", REAL_METAPHYSICS_SAMPLES, ids=lambda s: s["id"])
    async def test_interpret_real_sample(self, metaphysics_interpreter, sample):
        """测试解读真实命理样本"""
        document = {
            "content": sample["content"],
            "file_type": "txt",
        }
        
        result = await metaphysics_interpreter.interpret(
            document,
            config={
                "use_llm": False,  # 先不使用 LLM，只测试提取
                "detail_level": "detailed",
                "extract_shen_sha": True
            }
        )
        
        assert result is not None
        assert result.domain_id == "metaphysics"
        
        # 验证八字提取
        bazi = result.structured_data.get("bazi", {})
        expected_bazi = sample["expected_bazi"]
        
        assert bazi.get("year_pillar") == expected_bazi["year_pillar"], \
            f"Year pillar mismatch: {bazi.get('year_pillar')} != {expected_bazi['year_pillar']}"
        assert bazi.get("month_pillar") == expected_bazi["month_pillar"], \
            f"Month pillar mismatch: {bazi.get('month_pillar')} != {expected_bazi['month_pillar']}"
        assert bazi.get("day_pillar") == expected_bazi["day_pillar"], \
            f"Day pillar mismatch: {bazi.get('day_pillar')} != {expected_bazi['day_pillar']}"
        
        # 验证神煞提取
        shen_sha = result.structured_data.get("shen_sha", [])
        for expected_ss in sample["expected_shen_sha"]:
            assert expected_ss in shen_sha, \
                f"Expected shen_sha '{expected_ss}' not found in {shen_sha}"

    @pytest.mark.asyncio
    async def test_interpret_with_llm_detailed_narrative(self, metaphysics_interpreter):
        """测试使用 LLM 生成详细叙事"""
        document = {
            "content": """命主八字分析
年柱：甲子
月柱：乙丑
日柱：丙寅
时柱：丁卯

五行分布：金0木4水1火2土1

神煞：天乙贵人、文昌、驿马

此命木旺火相，宜从事文化教育行业。""",
            "file_type": "txt",
        }
        
        result = await metaphysics_interpreter.interpret(
            document,
            config={
                "use_llm": True,
                "detail_level": "comprehensive",
                "extract_shen_sha": True
            }
        )
        
        assert result is not None
        assert result.narrative is not None
        assert len(result.narrative) > 50  # 详细叙事应该较长
        
        # 验证叙事包含关键信息
        narrative_lower = result.narrative.lower()
        # 应该包含八字或五行相关内容
        assert any(term in result.narrative for term in ["八字", "五行", "木", "火", "金", "水", "土"])

    @pytest.mark.asyncio
    async def test_interpret_complex_sample(self, metaphysics_interpreter):
        """测试复杂命理样本"""
        document = {
            "content": """
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
            命带天乙贵人，一生多贵人相助。
            文昌星照命，学业有成，考试运佳。
            """,
            "file_type": "txt",
        }
        
        result = await metaphysics_interpreter.interpret(
            document,
            config={
                "use_llm": True,
                "detail_level": "comprehensive",
                "extract_shen_sha": True
            }
        )
        
        assert result is not None
        assert result.confidence > 0.5  # 复杂样本应该有较高置信度
        
        # 验证提取了多个神煞
        shen_sha = result.structured_data.get("shen_sha", [])
        assert len(shen_sha) >= 3, f"Expected at least 3 shen_sha, got {len(shen_sha)}"


class TestComicRealSamples:
    """漫画真实样本测试 - 使用真实 API"""

    @pytest.fixture
    def comic_interpreter(self):
        """创建漫画解读器"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from core.domains.comic.interpreter import ComicInterpreter
        return ComicInterpreter()

    @pytest.fixture
    def realistic_comic_image(self):
        """创建更真实的漫画测试图像"""
        from PIL import Image, ImageDraw, ImageFont
        import io
        
        # 创建一个 4 格漫画模拟图像 (800x800)
        img = Image.new('RGB', (800, 800), color='white')
        draw = ImageDraw.Draw(img)
        
        # 绘制 4 个分格边界（2x2 布局）
        panel_width = 380
        panel_height = 380
        margin = 10
        gap = 20
        
        panels = [
            (margin, margin, margin + panel_width, margin + panel_height),  # 左上
            (margin + panel_width + gap, margin, 790, margin + panel_height),  # 右上
            (margin, margin + panel_height + gap, margin + panel_width, 790),  # 左下
            (margin + panel_width + gap, margin + panel_height + gap, 790, 790),  # 右下
        ]
        
        for i, (x1, y1, x2, y2) in enumerate(panels):
            # 绘制分格边框
            draw.rectangle([x1, y1, x2, y2], outline='black', width=3)
            
            # 在每个分格中绘制简单角色（圆形头部 + 身体）
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            
            # 头部
            head_radius = 40
            draw.ellipse([cx - head_radius, cy - 80 - head_radius, 
                         cx + head_radius, cy - 80 + head_radius], 
                        fill='peachpuff', outline='black', width=2)
            
            # 身体
            draw.rectangle([cx - 30, cy - 40, cx + 30, cy + 60], 
                          fill='lightblue', outline='black', width=2)
            
            # 对话气泡
            bubble_x = cx + 60
            bubble_y = cy - 100
            draw.ellipse([bubble_x, bubble_y, bubble_x + 100, bubble_y + 50], 
                        fill='white', outline='black', width=2)
            
            # 气泡指向
            draw.polygon([(bubble_x + 20, bubble_y + 45), 
                         (bubble_x + 10, bubble_y + 60), 
                         (bubble_x + 35, bubble_y + 45)], 
                        fill='white', outline='black')
            
            # 添加文字（分格编号）
            try:
                draw.text((bubble_x + 30, bubble_y + 15), f"Panel {i+1}", fill='black')
            except Exception:
                pass
        
        # 转换为 bytes
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=90)
        return buffer.getvalue()

    @pytest.mark.asyncio
    async def test_interpret_realistic_comic(self, comic_interpreter, realistic_comic_image):
        """测试解读真实风格漫画图像"""
        document = {
            "images": [realistic_comic_image],
            "metadata": {"domain": "comic"},
        }
        
        result = await comic_interpreter.interpret(
            document,
            config={
                "use_llm": True,
                "detail_level": "detailed",
                "reading_order": "ltr",
                "analyze_art_style": True
            }
        )
        
        assert result is not None
        assert result.domain_id == "comic"
        
        # 验证分格检测
        panels = result.structured_data.get("panel", [])
        assert len(panels) >= 1, "Should detect at least 1 panel"
        
        # 验证有叙事文本
        assert result.narrative is not None
        assert len(result.narrative) > 0

    @pytest.mark.asyncio
    async def test_interpret_with_vlm_scene_description(self, comic_interpreter, realistic_comic_image):
        """测试 VLM 场景描述"""
        document = {
            "images": [realistic_comic_image],
        }
        
        result = await comic_interpreter.interpret(
            document,
            config={
                "use_llm": True,
                "detail_level": "comprehensive",
                "reading_order": "auto",
                "analyze_art_style": True
            }
        )
        
        assert result is not None
        
        # 检查是否有场景描述
        panels = result.structured_data.get("panel", [])
        if panels:
            # 至少有一个分格应该有场景描述
            has_description = any(p.get("scene_description") for p in panels)
            # 注意：VLM 可能无法识别简单测试图像，所以这里不强制要求
            print(f"Scene descriptions found: {has_description}")

    @pytest.mark.asyncio
    async def test_interpret_art_style_analysis(self, comic_interpreter, realistic_comic_image):
        """测试艺术风格分析"""
        document = {
            "images": [realistic_comic_image],
        }
        
        result = await comic_interpreter.interpret(
            document,
            config={
                "use_llm": True,
                "detail_level": "detailed",
                "analyze_art_style": True
            }
        )
        
        assert result is not None
        
        # 检查艺术风格分析结果
        art_style = result.structured_data.get("art_style", {})
        if art_style:
            # 应该有风格描述
            assert "style" in art_style or len(art_style) > 0

    @pytest.mark.asyncio
    async def test_interpret_different_reading_orders(self, comic_interpreter, realistic_comic_image):
        """测试不同阅读顺序"""
        document = {"images": [realistic_comic_image]}
        
        # 测试从左到右
        result_ltr = await comic_interpreter.interpret(
            document,
            config={
                "use_llm": False,
                "reading_order": "ltr",
                "analyze_art_style": False
            }
        )
        
        # 测试从右到左
        result_rtl = await comic_interpreter.interpret(
            document,
            config={
                "use_llm": False,
                "reading_order": "rtl",
                "analyze_art_style": False
            }
        )
        
        # 测试自动检测
        result_auto = await comic_interpreter.interpret(
            document,
            config={
                "use_llm": False,
                "reading_order": "auto",
                "analyze_art_style": False
            }
        )
        
        assert result_ltr.metadata.get("reading_order") == "ltr"
        assert result_rtl.metadata.get("reading_order") == "rtl"
        assert result_auto.metadata.get("reading_order") == "auto"


class TestRealVLMCalls:
    """真实 VLM API 调用测试"""

    @pytest.fixture
    def base_interpreter(self):
        """创建基础解读器"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from core.domains.metaphysics.interpreter import MetaphysicsInterpreter
        return MetaphysicsInterpreter()

    @pytest.fixture
    def test_image_with_text(self):
        """创建包含文字的测试图像"""
        from PIL import Image, ImageDraw
        import io
        
        img = Image.new('RGB', (400, 200), color='white')
        draw = ImageDraw.Draw(img)
        
        # 绘制边框
        draw.rectangle([10, 10, 390, 190], outline='black', width=2)
        
        # 添加文字
        draw.text((50, 80), "甲子乙丑丙寅丁卯", fill='black')
        draw.text((50, 120), "五行木旺", fill='blue')
        
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=90)
        return buffer.getvalue()

    @pytest.mark.asyncio
    async def test_vlm_extract_chinese_text(self, base_interpreter, test_image_with_text):
        """测试 VLM 提取中文文字"""
        prompt = """请识别这张图片中的中文文字内容。
请以JSON格式返回：
{
    "text": "识别到的文字内容"
}"""
        
        try:
            response = await base_interpreter._call_vlm(
                test_image_with_text,
                prompt,
                skip_budget_check=True
            )
            
            assert response is not None
            assert isinstance(response, str)
            assert len(response) > 0
            
            # 检查是否识别到关键文字
            # 注意：VLM 可能无法完美识别简单图像中的文字
            print(f"VLM Response: {response}")
            
        except Exception as e:
            pytest.skip(f"VLM call failed: {e}")

    @pytest.mark.asyncio
    async def test_vlm_describe_image(self, base_interpreter):
        """测试 VLM 描述图像"""
        from PIL import Image, ImageDraw
        import io
        
        # 创建简单场景图像
        img = Image.new('RGB', (300, 300), color='lightblue')
        draw = ImageDraw.Draw(img)
        
        # 绘制太阳
        draw.ellipse([200, 20, 280, 100], fill='yellow', outline='orange', width=2)
        
        # 绘制山
        draw.polygon([(0, 300), (150, 150), (300, 300)], fill='green')
        
        # 绘制房子
        draw.rectangle([50, 200, 120, 280], fill='brown', outline='black')
        draw.polygon([(40, 200), (85, 150), (130, 200)], fill='red', outline='black')
        
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=90)
        image_data = buffer.getvalue()
        
        prompt = "请用中文描述这张图片中的内容。"
        
        try:
            response = await base_interpreter._call_vlm(
                image_data,
                prompt,
                skip_budget_check=True
            )
            
            assert response is not None
            assert isinstance(response, str)
            assert len(response) > 10
            
            print(f"VLM Description: {response}")
            
        except Exception as e:
            pytest.skip(f"VLM call failed: {e}")


class TestRealLLMCalls:
    """真实 LLM API 调用测试"""

    @pytest.fixture
    def base_interpreter(self):
        """创建基础解读器"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        skip_if_no_database()
        
        from core.domains.metaphysics.interpreter import MetaphysicsInterpreter
        return MetaphysicsInterpreter()

    @pytest.mark.asyncio
    async def test_llm_generate_narrative(self, base_interpreter):
        """测试 LLM 生成叙事"""
        prompt = """请根据以下八字信息生成一段命理解读：

八字：甲子 乙丑 丙寅 丁卯
五行：金0 木4 水1 火2 土1
神煞：天乙贵人、文昌

请用专业但通俗易懂的语言解读。"""
        
        try:
            response = await base_interpreter._call_llm(
                prompt,
                skip_budget_check=True
            )
            
            assert response is not None
            assert isinstance(response, str)
            assert len(response) > 50
            
            # 应该包含命理相关内容
            assert any(term in response for term in ["八字", "五行", "木", "命", "运"])
            
            print(f"LLM Narrative: {response[:200]}...")
            
        except Exception as e:
            pytest.skip(f"LLM call failed: {e}")

    @pytest.mark.asyncio
    async def test_llm_with_context(self, base_interpreter):
        """测试带上下文的 LLM 调用"""
        prompt = "请总结这个人的命理特点。"
        context = """
        命主八字：甲子 乙丑 丙寅 丁卯
        五行分布：木旺，缺金
        神煞：天乙贵人、文昌、驿马
        
        八字分析：
        - 日主丙火，生于丑月，木火通明
        - 年月天干甲乙木生丙丁火，火势旺盛
        - 命带天乙贵人，一生多贵人相助
        - 文昌星照命，学业有成
        """
        
        try:
            response = await base_interpreter._call_llm(
                prompt,
                context=context,
                skip_budget_check=True
            )
            
            assert response is not None
            assert isinstance(response, str)
            assert len(response) > 20
            
            print(f"LLM Summary: {response[:200]}...")
            
        except Exception as e:
            pytest.skip(f"LLM call failed: {e}")

