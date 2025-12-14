# 🧪 摄取管道测试执行指南

## 🎯 **概述**

本指南提供了在不同环境中安全执行摄取管道测试的方法，避免因重量级依赖导致的卡顿问题。

---

## 🚀 **快速开始**

### 1. **验证测试质量（推荐首先执行）**

```bash
# 静态质量分析（无卡顿风险）
python tests/core/ingestion/analyze_test_quality.py

# 语法验证（无卡顿风险）
python tests/core/ingestion/validate_test_syntax.py

# 导入检查（无卡顿风险）
python tests/core/ingestion/test_imports_check.py
```

### 2. **轻量级测试执行**

```bash
# 执行最轻量的测试
python -m pytest tests/core/ingestion/test_error_handler.py -v
python -m pytest tests/core/ingestion/test_finalizer.py -v
python -m pytest tests/core/ingestion/test_graph_simple.py -v
```

---

## 🛡️ **安全执行策略**

### 方案 A: Docker 隔离执行（推荐）

```bash
# 创建隔离的测试环境
docker run --rm -it \
  -v $(pwd):/workspace \
  -w /workspace \
  python:3.11-slim \
  bash -c "
    pip install pytest pytest-asyncio pytest-mock numpy &&
    python -m pytest tests/core/ingestion/ -v --tb=short -x
  "
```

### 方案 B: 虚拟环境执行

```bash
# 创建专用测试环境
python -m venv test_env
source test_env/bin/activate  # Linux/Mac
# test_env\Scripts\activate  # Windows

# 安装最小依赖
pip install pytest pytest-asyncio pytest-mock

# 执行测试
python -m pytest tests/core/ingestion/ -v
```

### 方案 C: 进程隔离执行

```bash
# 使用pytest-forked插件
pip install pytest-forked

# 每个测试在独立进程中运行
python -m pytest tests/core/ingestion/ --forked -v
```

---

## 📊 **分层测试策略**

### 🥇 **第一层: 纯逻辑测试（无外部依赖）**

```bash
# 这些测试最安全，优先执行
python -m pytest tests/core/ingestion/test_error_handler.py -v
python -m pytest tests/core/ingestion/test_finalizer.py -v
```

**特点**: 纯 Python 逻辑，无重量级依赖，执行快速

### 🥈 **第二层: 轻量 Mock 测试**

```bash
# 这些测试有Mock但依赖较轻
python -m pytest tests/core/ingestion/test_graph_simple.py -v
python -m pytest tests/core/ingestion/test_chunker.py -v
```

**特点**: 使用 Mock 隔离，但可能有轻量级导入

### 🥉 **第三层: 重量级 Mock 测试**

```bash
# 这些测试可能有重量级依赖，建议隔离执行
python -m pytest tests/core/ingestion/test_loader.py -v
python -m pytest tests/core/ingestion/test_cpu_parser.py -v
python -m pytest tests/core/ingestion/test_gpu_parser.py -v
python -m pytest tests/core/ingestion/test_embedder.py -v
python -m pytest tests/core/ingestion/test_indexer.py -v
```

**特点**: 可能导入深度学习框架或数据库客户端

---

## 🔧 **故障排除**

### 问题 1: 导入卡顿

**症状**: `python -c "import xxx"` 卡住不动

**解决方案**:

```bash
# 1. 检查具体卡顿的模块
python tests/core/ingestion/test_imports_check.py

# 2. 使用超时机制
timeout 30s python -c "import core.ingestion.nodes.router"

# 3. 在隔离环境中测试
docker run --rm python:3.11 python -c "print('OK')"
```

### 问题 2: 测试执行卡顿

**症状**: pytest 执行后无响应

**解决方案**:

```bash
# 1. 使用进程隔离
python -m pytest --forked tests/core/ingestion/test_xxx.py

# 2. 单个测试执行
python -m pytest tests/core/ingestion/test_xxx.py::TestClass::test_method -v

# 3. 跳过重量级测试
python -m pytest -m "not heavy" tests/core/ingestion/
```

### 问题 3: Mock 失效

**症状**: 测试尝试连接真实服务

**解决方案**:

```bash
# 1. 验证Mock覆盖
python tests/core/ingestion/analyze_test_quality.py

# 2. 检查网络隔离
python -m pytest --disable-warnings -v tests/core/ingestion/test_xxx.py

# 3. 使用离线模式
export OFFLINE_MODE=1
python -m pytest tests/core/ingestion/
```

---

## 📈 **性能优化建议**

### 🚀 **加速测试执行**

```bash
# 1. 并行执行（小心资源竞争）
pip install pytest-xdist
python -m pytest -n 4 tests/core/ingestion/

# 2. 只运行失败的测试
python -m pytest --lf tests/core/ingestion/

# 3. 跳过慢速测试
python -m pytest -m "not slow" tests/core/ingestion/

# 4. 使用缓存
python -m pytest --cache-clear tests/core/ingestion/
```

### 🎯 **针对性测试**

```bash
# 只测试P0级别（关键安全测试）
python -m pytest -k "P0 or security or tenant" tests/core/ingestion/

# 只测试特定功能
python -m pytest -k "router or chunker" tests/core/ingestion/

# 跳过集成测试
python -m pytest -k "not integration" tests/core/ingestion/
```

---

## 🔍 **测试覆盖率检查**

```bash
# 安装覆盖率工具
pip install pytest-cov

# 生成覆盖率报告
python -m pytest --cov=core.ingestion --cov-report=html tests/core/ingestion/

# 查看覆盖率
open htmlcov/index.html  # Mac
# start htmlcov/index.html  # Windows
```

---

## 🎯 **CI/CD 集成建议**

### GitHub Actions 示例

```yaml
name: Ingestion Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        test-group: [lightweight, mock-heavy, integration]

    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install pytest pytest-asyncio pytest-mock pytest-forked

      - name: Run lightweight tests
        if: matrix.test-group == 'lightweight'
        run: |
          python -m pytest tests/core/ingestion/test_error_handler.py -v
          python -m pytest tests/core/ingestion/test_finalizer.py -v

      - name: Run mock-heavy tests
        if: matrix.test-group == 'mock-heavy'
        run: |
          python -m pytest --forked tests/core/ingestion/test_chunker.py -v
          python -m pytest --forked tests/core/ingestion/test_embedder.py -v

      - name: Run integration tests
        if: matrix.test-group == 'integration'
        timeout-minutes: 10
        run: |
          python -m pytest --forked tests/core/ingestion/test_graph.py -v
```

---

## 📋 **最佳实践总结**

### ✅ **推荐做法**

1. **先验证后执行**: 使用静态分析验证测试质量
2. **分层执行**: 从轻量级测试开始，逐步增加复杂度
3. **隔离环境**: 使用 Docker 或虚拟环境隔离测试
4. **超时保护**: 设置合理的超时时间
5. **进程隔离**: 使用`--forked`避免状态污染

### ❌ **避免做法**

1. **直接全量执行**: 避免一次性运行所有测试
2. **忽略卡顿**: 遇到卡顿应立即中断并分析
3. **跳过验证**: 不要跳过静态质量检查
4. **混合环境**: 避免在生产环境中运行测试
5. **忽略 Mock**: 确保外部依赖被正确 Mock

---

## 🎉 **总结**

通过本指南的分层策略和安全执行方案，可以有效避免测试执行中的卡顿问题，同时确保测试质量和系统稳定性。

**核心原则**: 先验证，后执行，分层测试，隔离环境。
