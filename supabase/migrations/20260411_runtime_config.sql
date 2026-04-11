-- Runtime config key-value store for settings that persist across service restarts
CREATE TABLE IF NOT EXISTS wp_runtime_config (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed with default YOLO level
INSERT INTO wp_runtime_config (key, value) VALUES ('yolo_level', '4')
ON CONFLICT (key) DO NOTHING;
