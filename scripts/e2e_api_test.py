"""
端到端 API 冒烟脚本：
- 校验健康检查
- 上传并索引示例 PDF
- 基于指定文档发起 Chat 并校验响应
- 清理上传的文档

用法示例：
  python scripts/e2e_api_test.py --base-url http://localhost:3500/api \
      --secret-key your-secret-key \
      --sample data/samples/pdf/arxiv_sample.pdf
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

# 复用服务端的 JWT 生成逻辑，保证权限一致
try:
    from server.auth import create_token
except Exception:
    create_token = None  # type: ignore


def make_token(secret_key: str, ttl: int = 1800) -> str:
    if not secret_key or len(secret_key) < 16:
        raise RuntimeError("SECRET_KEY 不合法，长度需 >=16")
    os.environ["SECRET_KEY"] = secret_key
    if create_token is None:
        raise RuntimeError("无法导入 server.auth.create_token，确认当前工作目录在项目根目录")
    return create_token("e2e-tester", ttl_seconds=ttl)


def assert_ok(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="OmniRAG API 端到端测试")
    parser.add_argument(
        "--base-url",
        default="http://localhost:3500/api",
        help="网关/后端基地址，形如 http://localhost:3500/api",
    )
    parser.add_argument(
        "--secret-key",
        default=os.environ.get("SECRET_KEY", "dev-secret-1234567890123"),
        help="与后端一致的 SECRET_KEY，用于生成测试 Token",
    )
    parser.add_argument(
        "--sample",
        default="data/samples/pdf/arxiv_sample.pdf",
        help="用于上传的本地 PDF 路径",
    )
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    sample_path = Path(args.sample).resolve()
    assert_ok(sample_path.exists(), f"样例文件不存在: {sample_path}")

    token = make_token(args.secret_key)
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(timeout=30.0) as client:
        # 1) 健康检查
        resp = client.get(f"{base}/health")
        assert_ok(resp.status_code == 200, f"health 接口异常: {resp.status_code}")
        print("[OK] /health")

        # 2) 上传 & 索引 PDF
        with sample_path.open("rb") as f:
            files = {"file": (sample_path.name, f, "application/pdf")}
            data = {"index": "true"}
            resp = client.post(f"{base}/documents/upload", headers=headers, files=files, data=data)
        assert_ok(resp.status_code == 200, f"上传失败: {resp.status_code}, {resp.text}")
        payload = resp.json()
        doc_id = payload.get("document_id")
        assert_ok(doc_id, "返回的 document_id 为空")
        print(f"[OK] 上传完成，document_id={doc_id}")

        # 等待索引完成（简单轮询）
        for _ in range(10):
            time.sleep(1.5)
            st = client.get(f"{base}/documents/{doc_id}/status", headers=headers)
            if st.status_code == 200 and (st.json() or {}).get("processing_status") == "completed":
                break
        print("[OK] 索引完成/已就绪")

        # 3) Chat 端到端
        chat_body = {
            "query": "请用一句话总结上传文档的核心内容。",
            "document_ids": [doc_id],
            "top_k": 3,
            "candidate_k": 20,
        }
        resp = client.post(f"{base}/chat", headers=headers, json=chat_body)
        assert_ok(resp.status_code == 200, f"chat 接口失败: {resp.status_code}, {resp.text}")
        result = resp.json()
        answer = result.get("answer", "")
        sources = result.get("sources") or []
        assert_ok(answer, "chat 返回的 answer 为空")
        assert_ok(len(sources) > 0, "chat 返回的 sources 为空")
        print("[OK] Chat 成功，引用数量:", len(sources))

        # 4) 清理文档
        client.delete(f"{base}/documents/{doc_id}", headers=headers)
        print("[OK] 清理文档完成")

    print(
        json.dumps(
            {"status": "pass", "doc_id": doc_id, "sources": len(sources)}, ensure_ascii=False
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover - CLI 快速失败
        print(f"[FAILED] {exc}", file=sys.stderr)
        sys.exit(1)

