#!/usr/bin/env bash
set -euo pipefail
BASE=${BASE:-http://localhost:3503}

echo "[env] BASE=$BASE"
curl -s "$BASE/api/system/status" | jq -c . || true

echo "[1] list models" && curl -s "$BASE/api/embedding/models" | jq -c .
echo "[2] create kb" && curl -s -X POST "$BASE/api/kb/create" -H 'Content-Type: application/json' -d '{"name":"kb_test_api","stack":"cn","vector_backend":"local"}' | jq -c .
echo "[3] get kb config" && curl -s "$BASE/api/kb/kb_test_api/config" | jq -c .
echo "[4] update kb params" && curl -s -X POST "$BASE/api/kb/kb_test_api/config" -H 'Content-Type: application/json' -d '{"embedding_model":"BAAI/bge-m3","top_k_default":7,"candidate_k":40,"vector_weight":0.7,"keyword_weight":0.3,"reranker_filter_threshold":0.25,"rrf_k":70,"web_search_enabled":false}' | jq -c .
echo "[5] debug embed default" && curl -s -X POST "$BASE/api/debug/embed" -H 'Content-Type: application/json' -d '{"text":"测试默认嵌入","dim":256}' | jq -c .
echo "[6] debug embed by kb" && curl -s -X POST "$BASE/api/debug/embed/kb" -H 'Content-Type: application/json' -d '{"kb_name":"kb_test_api","text":"测试 KB 嵌入","dim":256}' | jq -c .
echo "[7] change kb embedding" && curl -s -X POST "$BASE/api/kb/kb_test_api/config" -H 'Content-Type: application/json' -d '{"embedding_model":"intfloat/e5-base-v2"}' | jq -c .
echo "[8] debug embed by kb (changed)" && curl -s -X POST "$BASE/api/debug/embed/kb" -H 'Content-Type: application/json' -d '{"kb_name":"kb_test_api","text":"再次测试 KB 嵌入","dim":256}' | jq -c .
echo "[9] vector search by kb" && curl -s -X POST "$BASE/api/vector-store/search" -H 'Content-Type: application/json' -d '{"query":"测试","top_k":3,"kb_name":"kb_test_api"}' | jq -c .
echo "[10] reset kb" && curl -s -X POST "$BASE/api/kb/kb_test_api/config/reset" | jq -c .
echo "[11] kb config after reset" && curl -s "$BASE/api/kb/kb_test_api/config" | jq -c .
