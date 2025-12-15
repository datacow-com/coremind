"""
Panel Detector - 漫画分格检测器

Phase 2: 垂直领域增强
实现漫画分格边界检测和对话气泡检测。
"""
import logging
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class BoundingBox:
    """边界框"""
    x: int  # 左上角 x
    y: int  # 左上角 y
    width: int
    height: int
    
    @property
    def x2(self) -> int:
        """右下角 x"""
        return self.x + self.width
    
    @property
    def y2(self) -> int:
        """右下角 y"""
        return self.y + self.height
    
    @property
    def center(self) -> tuple[int, int]:
        """中心点"""
        return (self.x + self.width // 2, self.y + self.height // 2)
    
    @property
    def area(self) -> int:
        """面积"""
        return self.width * self.height
    
    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class Panel:
    """漫画分格"""
    index: int  # 阅读顺序索引
    bbox: BoundingBox
    confidence: float = 1.0
    
    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "bbox": self.bbox.to_dict(),
            "confidence": self.confidence,
        }


@dataclass
class SpeechBubble:
    """对话气泡"""
    bbox: BoundingBox
    panel_index: int  # 所属分格索引
    bubble_type: Literal["speech", "thought", "narration", "sfx"] = "speech"
    confidence: float = 1.0
    
    def to_dict(self) -> dict:
        return {
            "bbox": self.bbox.to_dict(),
            "panel_index": self.panel_index,
            "bubble_type": self.bubble_type,
            "confidence": self.confidence,
        }


@dataclass
class DetectionResult:
    """检测结果"""
    panels: list[Panel] = field(default_factory=list)
    bubbles: list[SpeechBubble] = field(default_factory=list)
    reading_order: Literal["ltr", "rtl"] = "ltr"
    image_width: int = 0
    image_height: int = 0
    
    def to_dict(self) -> dict:
        return {
            "panels": [p.to_dict() for p in self.panels],
            "bubbles": [b.to_dict() for b in self.bubbles],
            "reading_order": self.reading_order,
            "image_width": self.image_width,
            "image_height": self.image_height,
        }


ReadingOrder = Literal["ltr", "rtl", "auto"]


class PanelDetector:
    """
    漫画分格检测器
    
    支持检测漫画分格边界和对话气泡，
    支持从左到右(LTR)和从右到左(RTL)的阅读顺序。
    """
    
    def __init__(
        self,
        reading_order: ReadingOrder = "auto",
        min_panel_area_ratio: float = 0.02,
        max_panel_area_ratio: float = 0.8,
    ):
        """
        初始化分格检测器
        
        Args:
            reading_order: 阅读顺序 (ltr/rtl/auto)
            min_panel_area_ratio: 最小分格面积比例（相对于图像）
            max_panel_area_ratio: 最大分格面积比例
        """
        self.reading_order = reading_order
        self.min_panel_area_ratio = min_panel_area_ratio
        self.max_panel_area_ratio = max_panel_area_ratio
    
    def detect(self, image_data: bytes) -> DetectionResult:
        """
        检测漫画分格和对话气泡
        
        Args:
            image_data: 图像二进制数据
            
        Returns:
            DetectionResult: 检测结果
        """
        try:
            import cv2
            import numpy as np
            
            # 解码图像
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                logger.warning("Failed to decode image")
                return DetectionResult()
            
            height, width = img.shape[:2]
            
            # 检测分格
            panels = self._detect_panels(img)
            
            # 确定阅读顺序
            detected_order = self._detect_reading_order(panels, width)
            reading_order = detected_order if self.reading_order == "auto" else self.reading_order
            
            # 按阅读顺序排序分格
            panels = self._sort_panels(panels, reading_order, width)
            
            # 更新分格索引
            for i, panel in enumerate(panels):
                panel.index = i
            
            # 检测对话气泡
            bubbles = self._detect_bubbles(img, panels)
            
            return DetectionResult(
                panels=panels,
                bubbles=bubbles,
                reading_order=reading_order if reading_order != "auto" else "ltr",
                image_width=width,
                image_height=height,
            )
            
        except ImportError:
            logger.warning("OpenCV not available, using fallback detection")
            return self._fallback_detect(image_data)
        except Exception as e:
            logger.error(f"Panel detection failed: {e}")
            return DetectionResult()
    
    def _detect_panels(self, img) -> list[Panel]:
        """检测分格边界"""
        import cv2
        import numpy as np
        
        height, width = img.shape[:2]
        min_area = int(width * height * self.min_panel_area_ratio)
        max_area = int(width * height * self.max_panel_area_ratio)
        
        # 转换为灰度图
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 边缘检测
        edges = cv2.Canny(gray, 50, 150)
        
        # 膨胀边缘以连接断开的线条
        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=2)
        
        # 查找轮廓
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        panels: list[Panel] = []
        
        for contour in contours:
            # 获取边界矩形
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            
            # 过滤太小或太大的区域
            if area < min_area or area > max_area:
                continue
            
            # 过滤长宽比异常的区域
            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.2 or aspect_ratio > 5:
                continue
            
            # 计算置信度（基于轮廓的规则程度）
            perimeter = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
            confidence = min(1.0, len(approx) / 4 * 0.5 + 0.5)
            
            panels.append(Panel(
                index=0,  # 稍后排序时更新
                bbox=BoundingBox(x=x, y=y, width=w, height=h),
                confidence=confidence,
            ))
        
        # 如果没有检测到分格，尝试使用网格分割
        if not panels:
            panels = self._grid_fallback(width, height)
        
        return panels
    
    def _grid_fallback(self, width: int, height: int) -> list[Panel]:
        """网格分割回退方案"""
        # 假设是四格漫画（2x2）
        panels: list[Panel] = []
        
        half_w = width // 2
        half_h = height // 2
        
        # 四格布局
        positions = [
            (0, 0),           # 左上
            (half_w, 0),      # 右上
            (0, half_h),      # 左下
            (half_w, half_h), # 右下
        ]
        
        for i, (x, y) in enumerate(positions):
            panels.append(Panel(
                index=i,
                bbox=BoundingBox(x=x, y=y, width=half_w, height=half_h),
                confidence=0.5,  # 回退方案置信度较低
            ))
        
        return panels
    
    def _detect_reading_order(self, panels: list[Panel], image_width: int) -> Literal["ltr", "rtl"]:
        """
        检测阅读顺序
        
        基于分格布局特征判断是 LTR 还是 RTL
        """
        if len(panels) < 2:
            return "ltr"
        
        # 计算分格中心点的水平分布
        centers = [p.bbox.center[0] for p in panels]
        
        # 如果大部分分格偏右，可能是 RTL（日本漫画）
        right_count = sum(1 for c in centers if c > image_width / 2)
        
        # 简单启发式：如果超过 60% 的分格在右侧，认为是 RTL
        if right_count / len(panels) > 0.6:
            return "rtl"
        
        return "ltr"
    
    def _sort_panels(
        self,
        panels: list[Panel],
        reading_order: str,
        image_width: int
    ) -> list[Panel]:
        """
        按阅读顺序排序分格
        
        Args:
            panels: 分格列表
            reading_order: 阅读顺序
            image_width: 图像宽度
        """
        if not panels:
            return panels
        
        # 按行分组（基于 y 坐标）
        row_threshold = min(p.bbox.height for p in panels) * 0.5 if panels else 50
        
        # 按 y 坐标排序
        sorted_by_y = sorted(panels, key=lambda p: p.bbox.y)
        
        rows: list[list[Panel]] = []
        current_row: list[Panel] = []
        current_y = sorted_by_y[0].bbox.y if sorted_by_y else 0
        
        for panel in sorted_by_y:
            if abs(panel.bbox.y - current_y) > row_threshold:
                if current_row:
                    rows.append(current_row)
                current_row = [panel]
                current_y = panel.bbox.y
            else:
                current_row.append(panel)
        
        if current_row:
            rows.append(current_row)
        
        # 每行内按 x 坐标排序
        result: list[Panel] = []
        for row in rows:
            if reading_order == "rtl":
                # 从右到左
                sorted_row = sorted(row, key=lambda p: -p.bbox.x)
            else:
                # 从左到右
                sorted_row = sorted(row, key=lambda p: p.bbox.x)
            result.extend(sorted_row)
        
        return result
    
    def _detect_bubbles(self, img, panels: list[Panel]) -> list[SpeechBubble]:
        """检测对话气泡"""
        import cv2
        import numpy as np
        
        bubbles: list[SpeechBubble] = []
        
        # 转换为灰度图
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 二值化（对话气泡通常是白色背景）
        _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        
        # 查找轮廓
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            # 获取边界矩形
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            
            # 过滤太小或太大的区域
            if area < 500 or area > 50000:
                continue
            
            # 检查是否接近椭圆形（对话气泡特征）
            if len(contour) >= 5:
                ellipse = cv2.fitEllipse(contour)
                ellipse_area = np.pi * ellipse[1][0] * ellipse[1][1] / 4
                if ellipse_area > 0:
                    circularity = area / ellipse_area
                    if circularity < 0.5 or circularity > 1.5:
                        continue
            
            # 确定所属分格
            bubble_center = (x + w // 2, y + h // 2)
            panel_index = self._find_containing_panel(bubble_center, panels)
            
            # 判断气泡类型
            bubble_type = self._classify_bubble_type(contour, w, h)
            
            bubbles.append(SpeechBubble(
                bbox=BoundingBox(x=x, y=y, width=w, height=h),
                panel_index=panel_index,
                bubble_type=bubble_type,
                confidence=0.7,
            ))
        
        return bubbles
    
    def _find_containing_panel(
        self,
        point: tuple[int, int],
        panels: list[Panel]
    ) -> int:
        """找到包含指定点的分格"""
        px, py = point
        
        for panel in panels:
            bbox = panel.bbox
            if (bbox.x <= px <= bbox.x2 and bbox.y <= py <= bbox.y2):
                return panel.index
        
        # 如果没有找到，返回最近的分格
        if panels:
            min_dist = float('inf')
            closest_index = 0
            for panel in panels:
                cx, cy = panel.bbox.center
                dist = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
                if dist < min_dist:
                    min_dist = dist
                    closest_index = panel.index
            return closest_index
        
        return 0
    
    def _classify_bubble_type(
        self,
        contour,
        width: int,
        height: int
    ) -> Literal["speech", "thought", "narration", "sfx"]:
        """分类气泡类型"""
        import cv2
        
        # 计算轮廓的凸包
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        contour_area = cv2.contourArea(contour)
        
        if hull_area > 0:
            solidity = contour_area / hull_area
        else:
            solidity = 1.0
        
        # 思考气泡通常有波浪边缘（solidity 较低）
        if solidity < 0.8:
            return "thought"
        
        # 旁白框通常是矩形
        aspect_ratio = width / height if height > 0 else 1
        if aspect_ratio > 2 or aspect_ratio < 0.5:
            return "narration"
        
        # 默认为对话气泡
        return "speech"
    
    def _fallback_detect(self, image_data: bytes) -> DetectionResult:
        """
        回退检测方案（不依赖 OpenCV）
        
        使用简单的图像分析或假设固定布局
        """
        try:
            from PIL import Image
            import io
            
            img = Image.open(io.BytesIO(image_data))
            width, height = img.size
            
            # 假设四格漫画布局
            panels = self._grid_fallback(width, height)
            
            return DetectionResult(
                panels=panels,
                bubbles=[],
                reading_order="ltr",
                image_width=width,
                image_height=height,
            )
        except Exception as e:
            logger.error(f"Fallback detection failed: {e}")
            return DetectionResult()
