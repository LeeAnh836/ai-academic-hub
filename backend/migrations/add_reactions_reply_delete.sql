-- Migration: Add reactions, reply_to, and is_deleted support
-- Run against jvb_postgres

-- Add reply_to_id and is_deleted to direct_messages
ALTER TABLE direct_messages ADD COLUMN IF NOT EXISTS reply_to_id UUID REFERENCES direct_messages(id) ON DELETE SET NULL;
ALTER TABLE direct_messages ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;

-- Add reply_to_id and is_deleted to group_messages
ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS reply_to_id UUID REFERENCES group_messages(id) ON DELETE SET NULL;
ALTER TABLE group_messages ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;

-- Create message_reactions table
CREATE TABLE IF NOT EXISTS message_reactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    direct_message_id UUID REFERENCES direct_messages(id) ON DELETE CASCADE,
    group_message_id UUID REFERENCES group_messages(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reaction VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_dm_reaction_user UNIQUE (direct_message_id, user_id),
    CONSTRAINT uq_gm_reaction_user UNIQUE (group_message_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_message_reactions_dm ON message_reactions(direct_message_id);
CREATE INDEX IF NOT EXISTS idx_message_reactions_gm ON message_reactions(group_message_id);
CREATE INDEX IF NOT EXISTS idx_message_reactions_user ON message_reactions(user_id);
