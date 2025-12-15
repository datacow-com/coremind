# Comic Test Samples - 漫画测试样本

Phase 2: 垂直领域增强 - 漫画领域测试样本清单

## 样本要求

根据 Requirements 6.1 和 6.5，需要准备：

- 最少 20 张真实漫画样例
- 包含四格漫画
- 覆盖不同风格和阅读顺序

## 样本分类

### 1. 四格漫画 (4-panel)

用于测试标准四格漫画的分格检测和叙事构建。

| 文件名         | 描述             | 阅读顺序 | 风格     |
| -------------- | ---------------- | -------- | -------- |
| 4panel_001.jpg | 日式四格漫画示例 | RTL      | manga    |
| 4panel_002.jpg | 西式四格漫画示例 | LTR      | western  |
| 4panel_003.jpg | 简笔四格漫画     | LTR      | cartoon  |
| 4panel_004.jpg | 彩色四格漫画     | LTR      | webcomic |
| 4panel_005.jpg | 黑白四格漫画     | RTL      | manga    |

### 2. 多格漫画 (multi-panel)

用于测试复杂布局的分格检测。

| 文件名        | 描述       | 分格数 | 阅读顺序 |
| ------------- | ---------- | ------ | -------- |
| multi_001.jpg | 6 格漫画页 | 6      | RTL      |
| multi_002.jpg | 8 格漫画页 | 8      | LTR      |
| multi_003.jpg | 不规则分格 | 5      | RTL      |
| multi_004.jpg | 跨页大格   | 4      | LTR      |
| multi_005.jpg | 密集小格   | 12     | RTL      |

### 3. 对话气泡测试 (dialogue)

用于测试对话提取和 OCR。

| 文件名           | 描述         | 气泡类型  | 语言 |
| ---------------- | ------------ | --------- | ---- |
| dialogue_001.jpg | 标准对话气泡 | speech    | 中文 |
| dialogue_002.jpg | 思考气泡     | thought   | 中文 |
| dialogue_003.jpg | 旁白框       | narration | 中文 |
| dialogue_004.jpg | 音效文字     | sfx       | 日文 |
| dialogue_005.jpg | 混合气泡     | mixed     | 中文 |

### 4. 艺术风格测试 (style)

用于测试艺术风格分析。

| 文件名                  | 描述         | 风格      | 配色 |
| ----------------------- | ------------ | --------- | ---- |
| style_manga_001.jpg     | 日式漫画风格 | manga     | 黑白 |
| style_western_001.jpg   | 美式漫画风格 | western   | 彩色 |
| style_euro_001.jpg      | 欧式漫画风格 | european  | 彩色 |
| style_chibi_001.jpg     | Q 版风格     | chibi     | 彩色 |
| style_realistic_001.jpg | 写实风格     | realistic | 灰度 |

## 样本来源说明

所有测试样本应满足以下条件：

1. 已获得使用授权或属于公共领域
2. 不包含敏感或不当内容
3. 已进行必要的脱敏处理

## 使用方法

```python
from pathlib import Path

# 获取样本目录
samples_dir = Path("data/samples/comic")

# 加载四格漫画样本
four_panel_samples = list(samples_dir.glob("4panel_*.jpg"))

# 加载所有样本
all_samples = list(samples_dir.glob("*.jpg")) + list(samples_dir.glob("*.png"))
```

## 测试覆盖

| 测试场景     | 样本数量 | 状态   |
| ------------ | -------- | ------ |
| 四格漫画检测 | 5        | 待添加 |
| 多格漫画检测 | 5        | 待添加 |
| 对话提取     | 5        | 待添加 |
| 艺术风格分析 | 5        | 待添加 |
| **总计**     | **20**   | 待添加 |

## 注意事项

1. 真实样本需要手动添加到此目录
2. 测试时如果样本不存在，会使用生成的测试图像
3. 建议使用 CC0 或类似许可的公开漫画作为测试样本
