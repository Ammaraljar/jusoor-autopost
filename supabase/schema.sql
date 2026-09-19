-- Jusoor AutoPost — Supabase (PostgreSQL) schema
-- Run once in Supabase → SQL Editor. The backend also creates missing tables automatically on start.
-- Tables are only accessed by the backend (direct Postgres connection), so RLS is enabled with no
-- policies: the public anon key cannot read or write them through the Supabase REST API.

CREATE TABLE IF NOT EXISTS app_settings (
	key VARCHAR(60) NOT NULL, 
	value JSON NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (key)
);
ALTER TABLE app_settings ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS brands (
	id SERIAL NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	handle VARCHAR(120) NOT NULL, 
	website VARCHAR(255) NOT NULL, 
	voice TEXT NOT NULL, 
	colors JSON NOT NULL, 
	font_family VARCHAR(60) NOT NULL, 
	logo_path VARCHAR(500), 
	logo_placement VARCHAR(20) NOT NULL, 
	card_style VARCHAR(20) NOT NULL, 
	cta_text TEXT NOT NULL, 
	publish_config JSON NOT NULL, 
	is_default BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);
ALTER TABLE brands ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS campaigns (
	id SERIAL NOT NULL, 
	brand_id INTEGER, 
	name VARCHAR(160) NOT NULL, 
	objective TEXT NOT NULL, 
	color VARCHAR(20) NOT NULL, 
	start_date DATE, 
	end_date DATE, 
	notes TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(brand_id) REFERENCES brands (id) ON DELETE SET NULL
);
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS sources (
	id SERIAL NOT NULL, 
	brand_id INTEGER, 
	name VARCHAR(160) NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	base_url VARCHAR(500) NOT NULL, 
	feed_url VARCHAR(500), 
	listing_urls JSON NOT NULL, 
	link_selector VARCHAR(300), 
	link_pattern VARCHAR(300), 
	body_selector VARCHAR(300), 
	category VARCHAR(60) NOT NULL, 
	country VARCHAR(60) NOT NULL, 
	language VARCHAR(10) NOT NULL, 
	priority INTEGER NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	check_interval_minutes INTEGER NOT NULL, 
	max_items_per_run INTEGER NOT NULL, 
	health VARCHAR(20) NOT NULL, 
	last_checked_at TIMESTAMP WITH TIME ZONE, 
	last_success_at TIMESTAMP WITH TIME ZONE, 
	last_http_status INTEGER, 
	last_error TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(brand_id) REFERENCES brands (id) ON DELETE SET NULL
);
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS articles (
	id SERIAL NOT NULL, 
	source_id INTEGER, 
	url VARCHAR(800) NOT NULL, 
	title TEXT NOT NULL, 
	body TEXT NOT NULL, 
	image_url VARCHAR(800), 
	published_at TIMESTAMP WITH TIME ZONE, 
	fingerprint VARCHAR(64) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	note TEXT, 
	fetched_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_articles_url UNIQUE (url), 
	FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_articles_fingerprint ON articles (fingerprint);
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS calendar_items (
	id SERIAL NOT NULL, 
	brand_id INTEGER, 
	campaign_id INTEGER, 
	date DATE NOT NULL, 
	time VARCHAR(5) NOT NULL, 
	topic TEXT NOT NULL, 
	notes TEXT NOT NULL, 
	content_type VARCHAR(30) NOT NULL, 
	platform VARCHAR(30) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	draft_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(brand_id) REFERENCES brands (id) ON DELETE SET NULL, 
	FOREIGN KEY(campaign_id) REFERENCES campaigns (id) ON DELETE SET NULL
);
ALTER TABLE calendar_items ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS drafts (
	id SERIAL NOT NULL, 
	brand_id INTEGER, 
	source_id INTEGER, 
	article_id INTEGER, 
	campaign_id INTEGER, 
	calendar_item_id INTEGER, 
	origin VARCHAR(20) NOT NULL, 
	source_name VARCHAR(160) NOT NULL, 
	source_url VARCHAR(800), 
	original_title TEXT NOT NULL, 
	original_body TEXT NOT NULL, 
	original_image_url VARCHAR(800), 
	original_published_at TIMESTAMP WITH TIME ZONE, 
	language VARCHAR(5) NOT NULL, 
	tone VARCHAR(30) NOT NULL, 
	content_type VARCHAR(30) NOT NULL, 
	platform VARCHAR(30) NOT NULL, 
	hook TEXT NOT NULL, 
	subtitle TEXT NOT NULL, 
	caption TEXT NOT NULL, 
	hashtags TEXT NOT NULL, 
	first_comment TEXT NOT NULL, 
	cta TEXT NOT NULL, 
	image_keywords TEXT NOT NULL, 
	relevance INTEGER, 
	badge VARCHAR(30) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	scheduled_at TIMESTAMP WITH TIME ZONE, 
	publish_targets JSON NOT NULL, 
	error TEXT, 
	reject_reason TEXT, 
	published_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(brand_id) REFERENCES brands (id) ON DELETE SET NULL, 
	FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE SET NULL, 
	FOREIGN KEY(article_id) REFERENCES articles (id) ON DELETE SET NULL, 
	FOREIGN KEY(campaign_id) REFERENCES campaigns (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_drafts_created_at ON drafts (created_at);
CREATE INDEX IF NOT EXISTS ix_drafts_status ON drafts (status);
ALTER TABLE drafts ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS publish_logs (
	id SERIAL NOT NULL, 
	draft_id INTEGER NOT NULL, 
	provider VARCHAR(30) NOT NULL, 
	platform VARCHAR(30) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	external_id VARCHAR(200), 
	response JSON NOT NULL, 
	error TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(draft_id) REFERENCES drafts (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_publish_logs_draft_id ON publish_logs (draft_id);
ALTER TABLE publish_logs ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS slides (
	id SERIAL NOT NULL, 
	draft_id INTEGER NOT NULL, 
	position INTEGER NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	heading TEXT NOT NULL, 
	body TEXT NOT NULL, 
	background_url VARCHAR(800), 
	image_key VARCHAR(500), 
	image_url VARCHAR(800), 
	image_hash VARCHAR(64), 
	width INTEGER, 
	height INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(draft_id) REFERENCES drafts (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_slides_draft_id ON slides (draft_id);
ALTER TABLE slides ENABLE ROW LEVEL SECURITY;

-- Public bucket for rendered slides and logos (Meta/Buffer must be able to download them)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('autopost-media', 'autopost-media', true, 10485760,
        ARRAY['image/jpeg', 'image/png', 'image/webp', 'image/svg+xml'])
ON CONFLICT (id) DO NOTHING;
