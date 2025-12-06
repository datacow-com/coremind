# OmniRAG 分支策略与特性映射

## 1. 命名规范

- 主分支：`main`
- 开发分支：`develop`
- 特性分支：`feature/<phase>-<module>-<slug>`
- 发布分支：`release/<version>`
- 修复分支：`hotfix/<issue>`

## 2. 提交规范

- 使用 Conventional Commits：`feat: ...`、`fix: ...`、`perf: ...`、`refactor: ...`、`docs: ...`、`test: ...`、`chore: ...`
- 每次提交关联特性ID与任务ID：例如 `feat(c2-pdf-render): PDF转图片渲染引擎 #C2.1 #S2`

## 3. PR 规范

- 标题：`feat(<slug>): <feature name>`
- 关联：链接到特性文档与任务卡（dev-plan 与 features-roadmap）
- 校验：DoD 勾选、性能SLA、测试覆盖率与日志截图

## 4. Feature ↔ Branch 映射（Sprint 2）

- C2.1 PDF转图片渲染引擎 → `feature/c2-pdf-render`
- C2.2 Gemini Vision模型集成 → `feature/c2-vision-integration`
- C2.3 表格识别与还原 → `feature/c2-table-recovery`
- C2.5 ParsingRule开关设计 → `feature/c2-parsing-rule`
- C2.6 解析质量测试集 → `feature/c2-quality-tests`
- A2.2.1 文档上传API → `feature/a2-upload-api`

## 5. 里程碑与合流

- Sprint 2 完成后将 `feature/*` 合并至 `develop`，通过质量门 G1/G2，并打 `v0.2.0-rc`
- 发布前从 `develop` 切 `release/v0.2.0`，完成 G3/G4，合入 `main`

## 6. 日志与变更记录

- 每个 PR 必须附带：
  - 变更摘要与影响范围
  - 指标截图：解析耗时、准确率、TTFT、QPS
  - 回归测试报告链接
- 发布后更新 `CHANGELOG.md`：按特性组归档变更与指标
