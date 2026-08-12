-- Migration: add_chat_tables
-- Adds chat_threads and chat_messages for the Student ↔ Teacher live doubt feature.

CREATE TABLE IF NOT EXISTS chat_threads (
    id          VARCHAR PRIMARY KEY,
    lecture_id  VARCHAR NOT NULL REFERENCES lectures(id) ON DELETE CASCADE,
    student_id  VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_chat_thread_lecture_student UNIQUE (lecture_id, student_id)
);

CREATE INDEX IF NOT EXISTS ix_chat_threads_lecture_id ON chat_threads (lecture_id);
CREATE INDEX IF NOT EXISTS ix_chat_threads_student_id ON chat_threads (student_id);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          VARCHAR PRIMARY KEY,
    thread_id   VARCHAR NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
    sender_id   VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sender_role VARCHAR NOT NULL,
    content     TEXT    NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_chat_messages_thread_id  ON chat_messages (thread_id);
CREATE INDEX IF NOT EXISTS ix_chat_messages_created_at ON chat_messages (created_at);
