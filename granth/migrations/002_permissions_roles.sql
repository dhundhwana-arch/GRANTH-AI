-- 002: permission vocabulary APPROVED / RESTRICTED / UNKNOWN / DENIED (+ PERSONAL for a student's own notes),
--      edition roles (textbook | supplementary | personal) and an owner for personal material.
-- SQLite cannot alter a CHECK constraint, so the two affected tables are rebuilt (the documented SQLite procedure;
-- the migration runner disables foreign-key enforcement while migrations run). On PostgreSQL the same result is
-- reached with ALTER TABLE ... DROP/ADD CONSTRAINT and ADD COLUMN.

CREATE TABLE source_permissions_new (
  id INTEGER PRIMARY KEY,
  source_id INTEGER NOT NULL REFERENCES textbook_sources(id),
  status TEXT NOT NULL CHECK (status IN ('APPROVED','RESTRICTED','UNKNOWN','DENIED','PERSONAL')),
  license TEXT,
  evidence_url TEXT,
  notes TEXT,
  reviewed_by TEXT,
  reviewed_at TEXT
);
INSERT INTO source_permissions_new (id, source_id, status, license, evidence_url, notes, reviewed_by, reviewed_at)
  SELECT id, source_id,
         CASE status WHEN 'AUTHORIZED' THEN 'APPROVED' WHEN 'PROHIBITED' THEN 'DENIED' WHEN 'PENDING' THEN 'UNKNOWN' ELSE status END,
         license, evidence_url, notes, reviewed_by, reviewed_at FROM source_permissions;
DROP TABLE source_permissions;
ALTER TABLE source_permissions_new RENAME TO source_permissions;

CREATE TABLE textbook_editions_new (
  id INTEGER PRIMARY KEY,
  textbook_id INTEGER NOT NULL REFERENCES textbooks(id),
  slug TEXT NOT NULL UNIQUE,
  edition_label TEXT NOT NULL,
  academic_year TEXT,
  source_url TEXT NOT NULL,
  file_sha256 TEXT,
  permission_status TEXT NOT NULL CHECK (permission_status IN ('APPROVED','RESTRICTED','UNKNOWN','DENIED','PERSONAL')),
  license TEXT,
  review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
  reviewed_by TEXT,
  reviewed_at TEXT,
  discovery_status TEXT NOT NULL DEFAULT 'VERIFIED',
  corpus_version INTEGER NOT NULL DEFAULT 0,
  content_sha256 TEXT,
  page_count INTEGER NOT NULL DEFAULT 0,
  ingested_at TEXT,
  role TEXT NOT NULL DEFAULT 'textbook' CHECK (role IN ('textbook','supplementary','personal')),
  owner_session TEXT,                 -- set only for role = 'personal'; such editions are visible to that session alone
  attribution TEXT,                   -- attribution line required by the licence (e.g. CC BY-SA sources)
  last_verified_at TEXT,              -- when the source terms were last checked
  UNIQUE (textbook_id, edition_label)
);
INSERT INTO textbook_editions_new (id, textbook_id, slug, edition_label, academic_year, source_url, file_sha256, permission_status,
    license, review_status, reviewed_by, reviewed_at, discovery_status, corpus_version, content_sha256, page_count, ingested_at)
  SELECT id, textbook_id, slug, edition_label, academic_year, source_url, file_sha256,
         CASE permission_status WHEN 'AUTHORIZED' THEN 'APPROVED' WHEN 'PROHIBITED' THEN 'DENIED' WHEN 'PENDING' THEN 'UNKNOWN' ELSE permission_status END,
         license, review_status, reviewed_by, reviewed_at, discovery_status, corpus_version, content_sha256, page_count, ingested_at
  FROM textbook_editions;
DROP TABLE textbook_editions;
ALTER TABLE textbook_editions_new RENAME TO textbook_editions;
CREATE INDEX idx_editions_role ON textbook_editions(role, owner_session);

UPDATE text_chunks SET permission_status = 'APPROVED' WHERE permission_status = 'AUTHORIZED';
DELETE FROM answer_cache;

CREATE TABLE saved_answers (
  id INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL,
  answer_id INTEGER NOT NULL REFERENCES generated_answers(id),
  created_at TEXT NOT NULL,
  UNIQUE (session_id, answer_id)
);
