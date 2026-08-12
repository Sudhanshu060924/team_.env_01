-- Migration: Add language column to notes table
-- Description: Adds the language column to support multi-language notes (english, hindi, hinglish)
-- and creates a unique constraint to prevent duplicate notes per lecture+language

-- Add the language column if it doesn't exist
ALTER TABLE notes
ADD COLUMN IF NOT EXISTS language VARCHAR(20) NOT NULL DEFAULT 'english';

-- Add unique constraint on (lecture_id, language)
-- If the constraint already exists, this will be a no-op
ALTER TABLE notes
ADD CONSTRAINT uk_notes_lecture_language UNIQUE (lecture_id, language);
