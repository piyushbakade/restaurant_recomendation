"""
Database Migration and Schema Generator for Phase 8.
Supports Neon Serverless PostgreSQL and Supabase migration from the clean parquet catalog.
"""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def generate_ddl_sql() -> str:
    """
    Generates production-grade PostgreSQL DDL for Neon / Supabase with GIN and B-Tree indexes.
    """
    return """-- ==============================================================================
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
"""


def export_sql_file(output_path: Optional[Path] = None) -> Path:
    """
    Exports the generated DDL to a .sql file ready for execution in Neon / Supabase SQL Editor.
    """
    target = output_path or Path(__file__).resolve().parent / "schema.sql"
    ddl = generate_ddl_sql()
    target.write_text(ddl, encoding="utf-8")
    return target


def verify_database_connection(database_url: str) -> Dict[str, Any]:
    """
    Tests connectivity to Neon PostgreSQL if psycopg2 or similar driver is available.
    """
    if not database_url or not database_url.startswith("postgresql://"):
        return {"connected": False, "error": "Invalid or missing DATABASE_URL format."}

    try:
        import urllib.parse
        parsed = urllib.parse.urlparse(database_url)
        host = parsed.hostname
        port = parsed.port or 5432

        # Basic socket connection test without requiring heavy psycopg2 binaries
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(4.0)
        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            return {"connected": True, "host": host, "port": port}
        else:
            return {"connected": False, "error": f"Socket connect to {host}:{port} failed (code {result})"}
    except Exception as e:
        return {"connected": False, "error": str(e)}
