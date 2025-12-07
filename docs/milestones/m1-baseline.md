# M1 基线梳理（D1-D2）

## 范围与目标
- 复核后端契约（/ingest/run, /ingest/events SSE, /chat 流式，StrategyConfig，Citation bbox/page）。
- 盘点 `frontend/` 主应用结构与依赖（路由、状态管理、API client、Strategy/Monitor/Chat）。
- 盘点 `apps/embedded-ui` 使用场景、构建/发布链路、依赖与环境变量。

## 任务表（含三级子任务）
| 任务ID | 三级任务描述 | 状态 | Owner | ETA | 风险 | 依赖/备注 |
| --- | --- | --- | --- | --- | --- | --- |
| 1.1 | 后端 API 契约复核：/ingest/run 请求体与 StrategyConfig 字段、/ingest/upload_run(/stream) 事件格式、/chat/run 流式响应与 `<cite>` 模板（bbox/page） | done | 架构 | D2 | 后端接口变更窗口未确认 | 已梳理：ingest 事件 node_start/node_end/complete/error；chat 事件 node_start/node_end/answer/complete |
| 1.2 | 前端结构与依赖盘点：路由/页面、状态管理（store/query client）、API client、组件 Strategy/Monitor/Chat 的现状与入口 | in-progress | 前端 | D2 | 依赖版本不一致或缺锁版 | 发现 ChatPage 仍用旧 `/api/chat/stream`/`/api/chat`；IngestPage 已用 `/api/ingest/upload_run/stream`；StrategyConfig 覆盖 chunk/ocr/embedding/index，但缺质量控制等字段 |
| 1.3 | apps/embedded-ui 盘点：场景、构建/发布方式、依赖/锁版、环境变量与配置注入方式 | in-progress | 前端 | D2 | 构建链路缺文档或未锁定 | 现以模型网关为主，调用 `/models/*`，未接入 ingest/chat；待确认部署/锁版/鉴权策略 |
| 1.4 | 初版风险清单与问题列表：接口、依赖、缺少类型/校验、潜在安全与性能隐患 | todo | TBD | D2 | 信息不全导致遗漏 | 依赖 1.1/1.2/1.3 完成 |

## 风险与缓解
- 接口文档缺失或版本不一致 → 向后端获取最新 Swagger/示例，必要时抓包对齐。
- 依赖未锁版 → 记录风险，建议补充 lockfile 与版本策略。
- 嵌入式 UI 构建链路不透明 → 要求补充 README/脚本说明。

## 检查清单
- 已收集后端接口示例/文档。
- 已完成前端与 embedded-ui 目录/依赖/入口梳理。
- 已输出问题与风险初版清单。
