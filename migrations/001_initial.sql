-- migrations/001_initial.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT UNIQUE NOT NULL,
    url_hash VARCHAR(64) NOT NULL,
    source VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB,
    correlation_id UUID NOT NULL
);

CREATE INDEX idx_articles_url_hash ON articles(url_hash);
CREATE INDEX idx_articles_source ON articles(source);
CREATE INDEX idx_articles_scraped_at ON articles(scraped_at);
CREATE INDEX idx_articles_correlation_id ON articles(correlation_id);

CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID UNIQUE NOT NULL REFERENCES articles(id),
    correlation_id UUID NOT NULL,
    tags TEXT[] NOT NULL,
    pain_points TEXT,
    insights TEXT,
    innovations TEXT,
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    model_used VARCHAR(100) NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER
);

CREATE INDEX idx_analyses_article_id ON analyses(article_id);
CREATE INDEX idx_analyses_analyzed_at ON analyses(analyzed_at);

CREATE TABLE failed_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_type VARCHAR(50) NOT NULL,
    article_url TEXT,
    article_id UUID REFERENCES articles(id),
    exception_type VARCHAR(200),
    exception_message TEXT,
    failed_at TIMESTAMPTZ DEFAULT NOW(),
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_failed_tasks_resolved ON failed_tasks(resolved);
CREATE INDEX idx_failed_tasks_failed_at ON failed_tasks(failed_at);
