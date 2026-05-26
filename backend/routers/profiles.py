from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
import psycopg
from psycopg.rows import dict_row
import structlog

from backend.db.connection import get_db

router = APIRouter()
logger = structlog.get_logger()

class ProfileSchema(BaseModel):
    id: int
    skills: List[str] = Field(default_factory=list)
    seniority: Optional[str] = None
    tech_stack: List[str] = Field(default_factory=list)
    years_of_experience: int = 0
    geo_preference: Optional[str] = None
    updated_at: datetime

class ProfileUpdateSchema(BaseModel):
    skills: List[str] = Field(default_factory=list)
    seniority: Optional[str] = None
    tech_stack: List[str] = Field(default_factory=list)
    years_of_experience: int = Field(default=0, ge=0)
    geo_preference: Optional[str] = None

@router.get("/profiles/current", response_model=ProfileSchema)
async def get_current_profile(response: Response, conn: psycopg.AsyncConnection = Depends(get_db)):
    # Attach Cache-Control header to prevent browser caching of live data
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    
    try:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, skills, seniority, tech_stack, years_of_experience, geo_preference, updated_at 
                FROM profiles 
                WHERE id = 1
                """
            )
            row = await cur.fetchone()
            
            if not row:
                logger.info("Current profile not found. Creating a default profile record.")
                await cur.execute(
                    """
                    INSERT INTO profiles (id, skills, seniority, tech_stack, years_of_experience, geo_preference, updated_at)
                    VALUES (1, '{}', NULL, '{}', 0, NULL, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO NOTHING
                    """
                )
                await cur.execute(
                    """
                    SELECT id, skills, seniority, tech_stack, years_of_experience, geo_preference, updated_at 
                    FROM profiles 
                    WHERE id = 1
                    """
                )
                row = await cur.fetchone()
                
            return row
    except Exception as e:
        logger.error("Failed to fetch current profile", error=str(e))
        raise e

@router.put("/profiles/current", response_model=ProfileSchema)
async def update_current_profile(profile_data: ProfileUpdateSchema, conn: psycopg.AsyncConnection = Depends(get_db)):
    try:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                UPDATE profiles 
                SET skills = %s, seniority = %s, tech_stack = %s, years_of_experience = %s, geo_preference = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE id = 1
                """,
                (
                    profile_data.skills,
                    profile_data.seniority,
                    profile_data.tech_stack,
                    profile_data.years_of_experience,
                    profile_data.geo_preference,
                )
            )
            
            # Fetch and return the updated profile
            await cur.execute(
                """
                SELECT id, skills, seniority, tech_stack, years_of_experience, geo_preference, updated_at 
                FROM profiles 
                WHERE id = 1
                """
            )
            row = await cur.fetchone()
            
            if not row:
                # Fallback: if record was deleted, recreate it
                logger.warning("Profile did not exist during update. Recreating.")
                await cur.execute(
                    """
                    INSERT INTO profiles (id, skills, seniority, tech_stack, years_of_experience, geo_preference, updated_at)
                    VALUES (1, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET 
                        skills = EXCLUDED.skills,
                        seniority = EXCLUDED.seniority,
                        tech_stack = EXCLUDED.tech_stack,
                        years_of_experience = EXCLUDED.years_of_experience,
                        geo_preference = EXCLUDED.geo_preference,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        profile_data.skills,
                        profile_data.seniority,
                        profile_data.tech_stack,
                        profile_data.years_of_experience,
                        profile_data.geo_preference,
                    )
                )
                await cur.execute(
                    """
                    SELECT id, skills, seniority, tech_stack, years_of_experience, geo_preference, updated_at 
                    FROM profiles 
                    WHERE id = 1
                    """
                )
                row = await cur.fetchone()
                
            return row
    except Exception as e:
        logger.error("Failed to update profile", error=str(e))
        raise e
