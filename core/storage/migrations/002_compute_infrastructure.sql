-- Migration: 002_compute_infrastructure
-- Description: Phase 1 多云算力基础设施
-- Date: 2024-12-14

-- ============================================================================
-- 1. 扩展 providers 表
-- ============================================================================

ALTER TABLE providers ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 10;
ALTER TABLE providers ADD COLUMN IF NOT EXISTS endpoints JSONB DEFAULT '{}';
ALTER TABLE providers ADD COLUMN IF NOT EXISTS rate_limits JSONB DEFAULT '{}';
ALTER TABLE providers ADD COLUMN IF NOT EXISTS is_healthy BOOLEAN DEFAULT TRUE;
ALTER TABLE providers ADD COLUMN IF NOT EXISTS last_health_check TIMESTAMP WITH TIME ZONE;
ALTER TABLE providers ADD COLUMN IF NOT EXISTS circuit_breaker_failures INTEGER DEFAULT 0;
ALTER TABLE providers ADD COLUMN IF NOT EXISTS circuit_breaker_open_until TIMESTAMP WITH TIME ZONE;

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_providers_priority ON providers(priority) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_providers_healthy ON providers(is_healthy) WHERE is_active = TRUE;

-- ============================================================================
-- 2. 创建 compute_cost_records 表
-- ============================================================================

CREATE TABLE IF NOT EXISTS compute_cost_records (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(100) NOT NULL,
    channel_id VARCHAR(100),
    user_id VARCHAR(100),
    provider_id VARCHAR(100) NOT NULL,
    model_id VARCHAR(100) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    image_count INTEGER DEFAULT 0,
    cost_usd NUMERIC(10, 6) NOT NULL,
    latency_ms INTEGER,
    cached BOOLEAN DEFAULT FALSE,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_cost_records_created_at ON compute_cost_records(created_at);
CREATE INDEX IF NOT EXISTS idx_cost_records_channel ON compute_cost_records(channel_id, created_at);
CREATE INDEX IF NOT EXISTS idx_cost_records_provider ON compute_cost_records(provider_id, created_at);
CREATE INDEX IF NOT EXISTS idx_cost_records_date ON compute_cost_records(DATE(created_at));

-- ============================================================================
-- 3. 创建 budget_configs 表
-- ============================================================================

CREATE TABLE IF NOT EXISTS budget_configs (
    id SERIAL PRIMARY KEY,
    scope VARCHAR(50) NOT NULL,
    scope_id VARCHAR(100),
    daily_limit NUMERIC(10, 2),
    monthly_limit NUMERIC(10, 2),
    alert_threshold NUMERIC(3, 2) DEFAULT 0.80,
    hard_stop_threshold NUMERIC(3, 2) DEFAULT 0.95,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT uq_budget_scope UNIQUE (scope, scope_id)
);

-- 插入默认全局预算配置
INSERT INTO budget_configs (scope, scope_id, daily_limit, monthly_limit, alert_threshold, hard_stop_threshold)
VALUES ('global', NULL, 100.00, 2000.00, 0.80, 0.95)
ON CONFLICT (scope, scope_id) DO NOTHING;

-- ============================================================================
-- 4. 创建 domain_configs 表（Phase 2+ 预留）
-- ============================================================================

CREATE TABLE IF NOT EXISTS domain_configs (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    name_en VARCHAR(200),
    ontology JSONB NOT NULL,
    visual_schema JSONB,
    narrative_schema JSONB,
    interpretation_rules JSONB,
    gpu_requirements JSONB,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- ============================================================================
-- 5. 创建视图
-- ============================================================================

-- 每日成本汇总视图
CREATE OR REPLACE VIEW daily_cost_summary AS
SELECT 
    DATE(created_at) as date,
    provider_id,
    model_id,
    task_type,
    COUNT(*) as request_count,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(image_count) as total_images,
    SUM(cost_usd) as total_cost_usd,
    AVG(latency_ms) as avg_latency_ms,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
    SUM(CASE WHEN cached THEN 1 ELSE 0 END) as cached_count
FROM compute_cost_records
GROUP BY DATE(created_at), provider_id, model_id, task_type;

-- Channel 成本汇总视图
CREATE OR REPLACE VIEW channel_cost_summary AS
SELECT 
    DATE(created_at) as date,
    channel_id,
    COUNT(*) as request_count,
    SUM(cost_usd) as total_cost_usd,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens
FROM compute_cost_records
WHERE channel_id IS NOT NULL
GROUP BY DATE(created_at), channel_id;

-- ============================================================================
-- 6. 更新现有 Provider 数据（如果存在）
-- ============================================================================

-- 设置 DashScope 优先级
UPDATE providers SET priority = 1 WHERE name ILIKE '%dashscope%';

-- 设置 DeepSeek 优先级
UPDATE providers SET priority = 2 WHERE name ILIKE '%deepseek%';

-- 设置 OpenAI 优先级
UPDATE providers SET priority = 5 WHERE name ILIKE '%openai%';
