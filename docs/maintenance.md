# 维护与一致性检查

## 上传目录清理
- 脚本：`python3 scripts/cleanup_uploads.py`
- 环境变量：
  - `UPLOADS_DIR`：清理目录（默认 `data/uploads/tmp`）
  - `CLEANUP_MAX_AGE_HOURS`：删除阈值，默认 72 小时
  - `CLEANUP_DRY_RUN=1`：仅打印不删除

## 索引-原文一致性检查
- 脚本：`python3 scripts/check_index_consistency.py`
- 行为：遍历本地索引的 chunk 元数据，检查 `doc_id` 路径是否存在，输出缺失文件。
- 说明：当前仅针对本地索引，未对远端向量库做检查；可作为定期巡检或运维自检。

## Makefile 便捷目标
- `make clean-uploads`：清理过期上传
- `make check-index`：检查本地索引与文件存在性
