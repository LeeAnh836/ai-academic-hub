-- Migration: Add last_read_at to group_members for tracking group unread messages
ALTER TABLE group_members ADD COLUMN IF NOT EXISTS last_read_at TIMESTAMP;
