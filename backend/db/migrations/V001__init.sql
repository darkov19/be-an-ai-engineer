CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY DEFAULT 1,
    skills TEXT[] NOT NULL DEFAULT '{}',
    seniority TEXT,
    tech_stack TEXT[] NOT NULL DEFAULT '{}',
    years_of_experience INTEGER DEFAULT 0 CHECK (years_of_experience >= 0),
    geo_preference TEXT,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT single_profile CHECK (id = 1)
);

INSERT INTO profiles (id, skills, seniority, tech_stack, years_of_experience, geo_preference, updated_at)
VALUES (1, '{}', NULL, '{}', 0, NULL, CURRENT_TIMESTAMP)
ON CONFLICT (id) DO NOTHING;
