-- Fix: Change recommendation_id from uuid to text on wp_auto_trades
-- Strategy trades use string IDs like "strat-orb_session-BTC-202604061130"
-- which cannot be cast to uuid, causing silent insert failures.

ALTER TABLE wp_auto_trades ALTER COLUMN recommendation_id TYPE text;
