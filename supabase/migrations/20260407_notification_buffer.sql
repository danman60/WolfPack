CREATE TABLE IF NOT EXISTS wp_notification_buffer (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    notification JSONB NOT NULL,
    flushed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notif_buffer_unflushed
    ON wp_notification_buffer(flushed) WHERE flushed = FALSE;
