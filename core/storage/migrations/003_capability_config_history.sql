-- Migration: 003_capability_config_history
-- Description: Add tables for KB capability configuration persistence and version history
-- Requirements: 12.1, 12.2, 12.3

-- KB Capability Configuration table
-- Stores the current capability configuration for each KB
CREATE TABLE IF NOT EXISTS kb_capability_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_name VARCHAR(200) NOT NULL UNIQUE,
    config JSONB NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for faster lookups by kb_name
CREATE INDEX IF NOT EXISTS idx_kb_capability_configs_kb_name ON kb_capability_configs(kb_name);

-- KB Capability Configuration History table
-- Stores version history for audit purposes (Requirements 12.3)
CREATE TABLE IF NOT EXISTS kb_capability_config_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_name VARCHAR(200) NOT NULL,
    version INTEGER NOT NULL,
    config JSONB NOT NULL,
    changed_by VARCHAR(200),
    change_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for history queries
CREATE INDEX IF NOT EXISTS idx_kb_capability_config_history_kb_name ON kb_capability_config_history(kb_name);
CREATE INDEX IF NOT EXISTS idx_kb_capability_config_history_version ON kb_capability_config_history(kb_name, version);

-- Add comment for documentation
COMMENT ON TABLE kb_capability_configs IS 'Stores current KB capability configurations';
COMMENT ON TABLE kb_capability_config_history IS 'Stores version history of KB capability configurations for audit';
COMMENT ON COLUMN kb_capability_config_history.changed_by IS 'User or system identifier that made the change';
COMMENT ON COLUMN kb_capability_config_history.change_reason IS 'Optional reason for the configuration change';
