-- Baby Joy / PostgreSQL 16+ 初始 schema 草案
-- NOT RUN: 需移入 Alembic 并在真实 Postgres 运行迁移、回滚、隔离测试。
-- 所有用户高敏数据均存加密私有系统；不提交真实孩子媒体及微信凭据。
BEGIN;

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  openid_lookup_hmac CHAR(64) NOT NULL UNIQUE,
  openid_ciphertext BYTEA NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACTIVE'
    CHECK (status IN ('ACTIVE','SUSPENDED','DELETION_REQUESTED','DELETED')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE policies (
  policy_version TEXT PRIMARY KEY,
  scope TEXT NOT NULL,
  content_sha256 CHAR(64) NOT NULL,
  published_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE consents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  policy_version TEXT NOT NULL REFERENCES policies(policy_version),
  scope TEXT NOT NULL CHECK (scope = 'GUARDIAN_UPLOAD_AND_GENERATE'),
  purpose TEXT NOT NULL CHECK (purpose = 'FAMILY_GREETING'),
  guardian_declaration BOOLEAN NOT NULL CHECK (guardian_declaration = true),
  evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
  granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ,
  CHECK (revoked_at IS NULL OR revoked_at >= granted_at)
);
CREATE INDEX idx_consents_user_active ON consents(user_id, granted_at DESC)
  WHERE revoked_at IS NULL;

CREATE TABLE assets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  kind TEXT NOT NULL CHECK (kind IN ('SOURCE_IMAGE','NORMALIZED_IMAGE','TTS_AUDIO','RAW_VIDEO','FINAL_VIDEO')),
  bucket_key TEXT NOT NULL UNIQUE,
  mime_type TEXT NOT NULL,
  byte_size BIGINT NOT NULL CHECK (byte_size >= 0),
  sha256_hex CHAR(64) NOT NULL,
  status TEXT NOT NULL DEFAULT 'PENDING_SCAN'
    CHECK (status IN ('PENDING_SCAN','READY','REJECTED','DELETING','DELETED')),
  rejection_code TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  deleted_at TIMESTAMPTZ,
  UNIQUE (id, user_id),
  CHECK (deleted_at IS NULL OR status = 'DELETED')
);
CREATE INDEX idx_assets_owner_created ON assets(user_id, created_at DESC);
CREATE INDEX idx_assets_expiry ON assets(expires_at)
  WHERE status NOT IN ('DELETING','DELETED');

CREATE TABLE jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  consent_id UUID NOT NULL REFERENCES consents(id),
  input_asset_id UUID NOT NULL,
  template_id TEXT NOT NULL CHECK (template_id IN ('family_love_v1','birthday_v1','festival_v1')),
  template_vars JSONB NOT NULL,
  voice_style TEXT NOT NULL CHECK (voice_style IN ('warm_childlike','playful_childlike','storybook')),
  target_duration_seconds INTEGER NOT NULL CHECK (target_duration_seconds IN (6,8,12)),
  status TEXT NOT NULL DEFAULT 'QUEUED'
    CHECK (status IN ('QUEUED','PREPROCESSING','SYNTHESIZING','GENERATING','QUALITY_CHECK','RENDERING','COMPLETED','REJECTED','FAILED','CANCELLED','EXPIRED')),
  stage TEXT NOT NULL DEFAULT 'QUEUED',
  current_attempt_no INTEGER NOT NULL DEFAULT 0 CHECK (current_attempt_no >= 0),
  last_error_code TEXT,
  cancel_requested_at TIMESTAMPTZ,
  delete_requested_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  stage_started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ,
  UNIQUE (id, user_id),
  FOREIGN KEY (input_asset_id, user_id) REFERENCES assets (id, user_id)
);
CREATE INDEX idx_jobs_user_created ON jobs(user_id, created_at DESC);
CREATE INDEX idx_jobs_active_created ON jobs(status, created_at)
  WHERE status NOT IN ('COMPLETED','REJECTED','FAILED','CANCELLED','EXPIRED');
CREATE INDEX idx_jobs_expiry ON jobs(expires_at) WHERE expires_at IS NOT NULL;

CREATE TABLE job_attempts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID NOT NULL REFERENCES jobs(id),
  attempt_no INTEGER NOT NULL CHECK (attempt_no >= 1),
  lease_token UUID,
  worker_id TEXT,
  attempt_status TEXT NOT NULL DEFAULT 'CREATED'
    CHECK (attempt_status IN ('CREATED','RUNNING','SUCCEEDED','FAILED','STALE','CANCELLED')),
  model_id TEXT,
  model_revision TEXT,
  model_weights_sha256 CHAR(64),
  seed BIGINT,
  heartbeat_at TIMESTAMPTZ,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  error_code TEXT,
  gpu_milliseconds BIGINT CHECK (gpu_milliseconds >= 0),
  peak_vram_mib BIGINT CHECK (peak_vram_mib >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (job_id, attempt_no)
);
CREATE INDEX idx_attempts_lease ON job_attempts(heartbeat_at)
  WHERE attempt_status = 'RUNNING';

CREATE TABLE job_events (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  job_id UUID NOT NULL REFERENCES jobs(id),
  status TEXT NOT NULL,
  stage TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_job_events_job_time ON job_events(job_id, occurred_at);

CREATE TABLE outputs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  job_id UUID NOT NULL UNIQUE,
  asset_id UUID NOT NULL UNIQUE,
  duration_seconds NUMERIC(8,3) NOT NULL CHECK (duration_seconds > 0),
  width INTEGER NOT NULL CHECK (width > 0),
  height INTEGER NOT NULL CHECK (height > 0),
  fps NUMERIC(7,3) NOT NULL CHECK (fps > 0),
  audio_codec TEXT NOT NULL,
  video_codec TEXT NOT NULL,
  ai_label_version TEXT NOT NULL,
  ffprobe_passed BOOLEAN NOT NULL CHECK (ffprobe_passed = true),
  qc_passed BOOLEAN NOT NULL CHECK (qc_passed = true),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  FOREIGN KEY (job_id, user_id) REFERENCES jobs (id, user_id),
  FOREIGN KEY (asset_id, user_id) REFERENCES assets (id, user_id)
);

CREATE TABLE idempotency_keys (
  user_id UUID NOT NULL REFERENCES users(id),
  endpoint TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  request_hash CHAR(64) NOT NULL,
  response_job_id UUID REFERENCES jobs(id),
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, endpoint, idempotency_key)
);
CREATE INDEX idx_idempotency_expiry ON idempotency_keys(expires_at);

CREATE TABLE outbox_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  aggregate_id UUID NOT NULL,
  event_type TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  publish_attempts INTEGER NOT NULL DEFAULT 0 CHECK (publish_attempts >= 0),
  next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_outbox_unpublished ON outbox_events(next_attempt_at)
  WHERE published_at IS NULL;

CREATE TABLE usage_quotas (
  user_id UUID NOT NULL REFERENCES users(id),
  window_start TIMESTAMPTZ NOT NULL,
  reserved INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0),
  used INTEGER NOT NULL DEFAULT 0 CHECK (used >= 0),
  PRIMARY KEY (user_id, window_start)
);

CREATE TABLE deletion_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  target_type TEXT NOT NULL CHECK (target_type IN ('JOB','ASSET','USER')),
  target_id UUID NOT NULL,
  status TEXT NOT NULL DEFAULT 'QUEUED'
    CHECK (status IN ('QUEUED','PROCESSING','COMPLETED','FAILED')),
  error_code TEXT,
  requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_deletion_pending ON deletion_requests(requested_at)
  WHERE status IN ('QUEUED','PROCESSING','FAILED');

CREATE TABLE audit_events (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  actor_id UUID,
  action TEXT NOT NULL,
  object_type TEXT NOT NULL,
  object_id UUID,
  minimal_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_actor ON audit_events(actor_id, occurred_at DESC);

COMMIT;
