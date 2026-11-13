-- GRANTH-AI schema v1. Written in portable SQL (works on SQLite and PostgreSQL):
--   * surrogate keys are INTEGER PRIMARY KEY (on PostgreSQL: replace with BIGINT GENERATED ALWAYS AS IDENTITY,
--     see docs/DATABASE_SCHEMA.md "PostgreSQL migration").
--   * timestamps are ISO-8601 TEXT in UTC; JSON payloads are TEXT.
--   * no SQLite-only features (no FTS virtual tables, no WITHOUT ROWID).

CREATE TABLE textbook_sources (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  base_url TEXT NOT NULL,
  kind TEXT NOT NULL,                 -- official_portal | project_sample
  robots_status TEXT,                 -- ALLOWED | DISALLOWED | UNREACHABLE | NOT_CHECKED
  last_checked_at TEXT,
  notes TEXT
);

CREATE TABLE source_permissions (
  id INTEGER PRIMARY KEY,
  source_id INTEGER NOT NULL REFERENCES textbook_sources(id),
  status TEXT NOT NULL CHECK (status IN ('AUTHORIZED','UNKNOWN','PROHIBITED','PENDING')),
  license TEXT,
  evidence_url TEXT,
  notes TEXT,
  reviewed_by TEXT,
  reviewed_at TEXT
);

CREATE TABLE subjects (
  id INTEGER PRIMARY KEY,
  name_gu TEXT NOT NULL UNIQUE,
  name_en TEXT
);

CREATE TABLE textbooks (
  id INTEGER PRIMARY KEY,
  source_id INTEGER NOT NULL REFERENCES textbook_sources(id),
  board TEXT NOT NULL,
  medium TEXT NOT NULL,
  standard INTEGER NOT NULL,
  subject_id INTEGER NOT NULL REFERENCES subjects(id),
  title TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'gu',
  UNIQUE (board, medium, standard, subject_id, title)
);

CREATE TABLE textbook_editions (
  id INTEGER PRIMARY KEY,
  textbook_id INTEGER NOT NULL REFERENCES textbooks(id),
  slug TEXT NOT NULL UNIQUE,
  edition_label TEXT NOT NULL,
  academic_year TEXT,
  source_url TEXT NOT NULL,
  file_sha256 TEXT,
  permission_status TEXT NOT NULL CHECK (permission_status IN ('AUTHORIZED','UNKNOWN','PROHIBITED','PENDING')),
  license TEXT,
  review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
  reviewed_by TEXT,
  reviewed_at TEXT,
  discovery_status TEXT NOT NULL DEFAULT 'VERIFIED',  -- VERIFIED | NOT_VERIFIED (catalogue placeholder)
  corpus_version INTEGER NOT NULL DEFAULT 0,          -- bumped on every (re-)ingestion; part of the cache key
  content_sha256 TEXT,                                -- hash of all chunk texts
  page_count INTEGER NOT NULL DEFAULT 0,
  ingested_at TEXT,
  UNIQUE (textbook_id, edition_label)
);

CREATE TABLE chapters (
  id INTEGER PRIMARY KEY,
  edition_id INTEGER NOT NULL REFERENCES textbook_editions(id),
  number INTEGER NOT NULL,
  title TEXT NOT NULL,
  page_start INTEGER NOT NULL,
  page_end INTEGER NOT NULL,
  UNIQUE (edition_id, number)
);

CREATE TABLE sections (
  id INTEGER PRIMARY KEY,
  chapter_id INTEGER NOT NULL REFERENCES chapters(id),
  number TEXT NOT NULL,
  title TEXT NOT NULL,
  page_start INTEGER NOT NULL
);

CREATE TABLE pages (
  id INTEGER PRIMARY KEY,
  edition_id INTEGER NOT NULL REFERENCES textbook_editions(id),
  page_number INTEGER NOT NULL,
  text TEXT NOT NULL,
  extraction_method TEXT NOT NULL,     -- source-text | pdf-text-layer | ocr:tesseract.js
  confidence REAL NOT NULL,
  UNIQUE (edition_id, page_number)
);

CREATE TABLE text_chunks (
  id INTEGER PRIMARY KEY,
  edition_id INTEGER NOT NULL REFERENCES textbook_editions(id),
  chapter_id INTEGER REFERENCES chapters(id),
  section_id INTEGER REFERENCES sections(id),
  page_number INTEGER NOT NULL,
  chunk_index INTEGER NOT NULL,
  kind TEXT NOT NULL,                  -- paragraph | table | formula | figure | glossary | example
  text TEXT NOT NULL,
  text_sha256 TEXT NOT NULL,
  extraction_confidence REAL NOT NULL,
  -- denormalised provenance: every chunk is self-describing
  board TEXT NOT NULL,
  medium TEXT NOT NULL,
  standard INTEGER NOT NULL,
  subject TEXT NOT NULL,
  book_title TEXT NOT NULL,
  edition TEXT NOT NULL,
  chapter_number INTEGER,
  chapter_title TEXT,
  section_title TEXT,
  source_url TEXT NOT NULL,
  permission_status TEXT NOT NULL
);
CREATE INDEX idx_chunks_edition ON text_chunks(edition_id, chapter_id, page_number);
CREATE INDEX idx_chunks_kind ON text_chunks(edition_id, kind);

CREATE TABLE ingestion_jobs (
  id INTEGER PRIMARY KEY,
  edition_id INTEGER REFERENCES textbook_editions(id),
  source_path TEXT NOT NULL,
  sha256 TEXT,
  method TEXT,
  status TEXT NOT NULL,                -- running | completed | failed | duplicate | refused
  started_at TEXT NOT NULL,
  finished_at TEXT,
  stats_json TEXT,
  error TEXT
);

CREATE TABLE extraction_quality (
  id INTEGER PRIMARY KEY,
  job_id INTEGER REFERENCES ingestion_jobs(id),
  edition_id INTEGER REFERENCES textbook_editions(id),
  page_number INTEGER NOT NULL,
  method TEXT NOT NULL,
  chars INTEGER NOT NULL,
  gujarati_ratio REAL NOT NULL,
  suspicious_ratio REAL NOT NULL,
  orphan_ratio REAL NOT NULL,
  engine_confidence REAL,
  score REAL NOT NULL,
  passed INTEGER NOT NULL,
  notes TEXT
);

CREATE TABLE questions (
  id INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL,
  text TEXT NOT NULL,
  normalized TEXT NOT NULL,
  input_method TEXT NOT NULL DEFAULT 'typed',   -- typed | voice | camera
  scope_json TEXT NOT NULL,
  mode TEXT NOT NULL,
  marks INTEGER,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_questions_session ON questions(session_id, id);

CREATE TABLE retrieved_evidence (
  id INTEGER PRIMARY KEY,
  question_id INTEGER NOT NULL REFERENCES questions(id),
  chunk_id INTEGER NOT NULL,
  rank INTEGER NOT NULL,
  score REAL NOT NULL,
  keyword_score REAL NOT NULL,
  semantic_score REAL NOT NULL,
  coverage REAL NOT NULL
);
CREATE INDEX idx_evidence_question ON retrieved_evidence(question_id);

CREATE TABLE generated_answers (
  id INTEGER PRIMARY KEY,
  question_id INTEGER NOT NULL REFERENCES questions(id),
  status TEXT NOT NULL,                -- answered | abstained | edition_conflict
  answer_json TEXT NOT NULL,
  engine TEXT NOT NULL,
  engine_version TEXT NOT NULL,
  from_cache INTEGER NOT NULL DEFAULT 0,
  external_api_calls INTEGER NOT NULL DEFAULT 0,
  latency_ms REAL NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_answers_question ON generated_answers(question_id);

CREATE TABLE verification_results (
  id INTEGER PRIMARY KEY,
  answer_id INTEGER NOT NULL REFERENCES generated_answers(id),
  verified INTEGER NOT NULL,
  support_ratio REAL NOT NULL,
  citations_valid INTEGER NOT NULL,
  details_json TEXT
);

CREATE TABLE answer_cache (
  cache_key TEXT PRIMARY KEY,
  normalized_question TEXT NOT NULL,
  scope_json TEXT NOT NULL,
  edition_ids TEXT NOT NULL,           -- comma separated, e.g. ",3,"
  corpus_versions TEXT NOT NULL,
  engine_version TEXT NOT NULL,
  payload_json TEXT NOT NULL,          -- answer, evidence references, pages, source ids
  evidence_hashes_json TEXT NOT NULL,  -- {chunk_id: text_sha256} re-checked on every hit
  verified INTEGER NOT NULL CHECK (verified = 1),
  created_at TEXT NOT NULL,
  last_hit_at TEXT,
  hits INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE usage_events (
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  kind TEXT NOT NULL,                  -- cache_hit | cache_miss | local_retrieval | external_api_call | external_api_error | ocr_local | ingestion
  provider TEXT,
  tokens_in INTEGER NOT NULL DEFAULT 0,
  tokens_out INTEGER NOT NULL DEFAULT 0,
  detail TEXT
);
CREATE INDEX idx_usage_kind ON usage_events(kind, ts);

CREATE TABLE feedback (
  id INTEGER PRIMARY KEY,
  question_id INTEGER,
  answer_id INTEGER,
  kind TEXT NOT NULL CHECK (kind IN ('incorrect_answer','incorrect_page','missing_content','ocr_error','other')),
  comment TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL
);

CREATE TABLE vocabulary (
  id INTEGER PRIMARY KEY,
  edition_id INTEGER NOT NULL REFERENCES textbook_editions(id),
  chapter_id INTEGER REFERENCES chapters(id),
  word TEXT NOT NULL,
  word_key TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('textbook_definition','textbook_glossary','context_only')),
  explanation TEXT,                    -- verbatim textbook sentence / glossary gloss; NULL for context_only
  context TEXT NOT NULL,               -- verbatim sentence in which the word occurs
  chunk_id INTEGER NOT NULL,
  page_number INTEGER NOT NULL
);
CREATE INDEX idx_vocab_key ON vocabulary(edition_id, word_key);

CREATE TABLE saved_words (
  id INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL,
  vocabulary_id INTEGER NOT NULL REFERENCES vocabulary(id),
  created_at TEXT NOT NULL,
  UNIQUE (session_id, vocabulary_id)
);
