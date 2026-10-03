-- ==============================================================================
-- GourmetAI: Bangalore Restaurant Catalog Schema (Neon Serverless PostgreSQL)
-- Optimized for serverless queries with pgbouncer connection pooling
-- ==============================================================================

-- Enable trgm extension for fuzzy restaurant name searches
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Core restaurants table
CREATE TABLE IF NOT EXISTS restaurants (
    restaurant_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    location VARCHAR(255) NOT NULL,
    location_cluster VARCHAR(100) NOT NULL,
    cuisines TEXT[] NOT NULL,
    price_for_two INTEGER NOT NULL,
    rating NUMERIC(2, 1),
    votes INTEGER DEFAULT 0,
    rest_type VARCHAR(255),
    popular_dishes TEXT[] DEFAULT ARRAY[]::TEXT[],
    online_order BOOLEAN DEFAULT FALSE,
    book_table BOOLEAN DEFAULT FALSE,
    url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- B-Tree index for micro-locality filtering
CREATE INDEX IF NOT EXISTS idx_restaurants_location ON restaurants(location);

-- B-Tree index for macro neighborhood cluster retrieval
CREATE INDEX IF NOT EXISTS idx_restaurants_cluster ON restaurants(location_cluster);

-- Composite B-Tree index for budget ceiling and rating ranking
CREATE INDEX IF NOT EXISTS idx_restaurants_price_rating ON restaurants(price_for_two, rating DESC NULLS LAST);

-- Single B-Tree index for rating queries
CREATE INDEX IF NOT EXISTS idx_restaurants_rating ON restaurants(rating DESC NULLS LAST);

-- GIN Index for rapid array containment searches on cuisines (e.g. cuisines && ARRAY['Italian', 'Pizza'])
CREATE INDEX IF NOT EXISTS idx_restaurants_cuisines ON restaurants USING GIN (cuisines);

-- GIN Trigram index for fuzzy text matching on venue names
CREATE INDEX IF NOT EXISTS idx_restaurants_name_trgm ON restaurants USING GIN (name gin_trgm_ops);

-- Helpful summary query
-- SELECT location_cluster, count(*), round(avg(rating), 2) as avg_rating FROM restaurants GROUP BY location_cluster ORDER BY count(*) DESC;
