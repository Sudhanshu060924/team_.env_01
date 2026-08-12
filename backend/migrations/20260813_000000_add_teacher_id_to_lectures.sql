-- Migration: Add teacher_id column to lectures table
-- Description: Adds teacher_id (VARCHAR, nullable) with FK to users.id.
--              Existing lectures keep teacher_id = NULL — they predate auth.

-- Step 1: add column as nullable (no default) so existing rows get NULL
ALTER TABLE lectures
    ADD COLUMN IF NOT EXISTS teacher_id VARCHAR;

-- Step 2: add the foreign key constraint only if it does not yet exist
--         (idempotent guard via DO block)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM   information_schema.table_constraints
        WHERE  table_name       = 'lectures'
          AND  constraint_name  = 'fk_lectures_teacher_id'
    ) THEN
        ALTER TABLE lectures
            ADD CONSTRAINT fk_lectures_teacher_id
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE SET NULL;
    END IF;
END;
$$;

-- Verification query (informational — not executed by the runner):
-- SELECT column_name, data_type
-- FROM   information_schema.columns
-- WHERE  table_name = 'lectures'
-- ORDER  BY ordinal_position;
