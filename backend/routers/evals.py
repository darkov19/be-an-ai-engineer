import uuid
import json
import structlog
from typing import Literal, Optional
from fastapi import APIRouter, Depends, Request, Response, BackgroundTasks, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import psycopg
from psycopg.rows import dict_row

from backend.db.connection import get_db
from backend.utils.tasks import task_manager, active_task_id
from backend.services.evaluator import run_evaluation, DEFAULT_SUMMARY_DIR

router = APIRouter()
logger = structlog.get_logger()

class EvalRunRequest(BaseModel):
    split: Literal["train", "held_out"] = "held_out"
    prompt_version: str = Field("extraction_v1", min_length=1)
    dry_run: bool = False

async def run_evaluation_task(task_id: str, pool, split: str, prompt_version: str, dry_run: bool):
    active_task_id.set(task_id)
    logger.info("Background evaluation task started", task_id=task_id, split=split, prompt_version=prompt_version, dry_run=dry_run)
    try:
        async with pool.connection() as conn:
            result = await run_evaluation(
                conn=conn,
                split=split,
                prompt_version=prompt_version,
                dry_run=dry_run,
            )
            logger.info("Background evaluation task completed successfully", task_id=task_id)
            task_manager.enqueue_log(task_id, {
                "control_type": "completed",
                "summary": result
            })
    except Exception as exc:
        logger.error("Background evaluation task failed with exception", task_id=task_id, error=str(exc))
        task_manager.enqueue_log(task_id, {
            "control_type": "failed",
            "error": str(exc)
        })
    finally:
        task_manager.finish_task(task_id)

@router.get("/evals")
async def get_evals_history(response: Response, conn: psycopg.AsyncConnection = Depends(get_db)):
    """
    Queries the evaluation_runs table and returns all runs ordered by run_timestamp DESC.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    try:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, run_timestamp, prompt_version, extraction_schema_version,
                       overall_accuracy, overall_precision, overall_recall, overall_f1,
                       accuracy_regression, metrics, created_at
                FROM evaluation_runs
                ORDER BY run_timestamp DESC
                """
            )
            rows = await cur.fetchall()
            return {"data": rows}
    except Exception as e:
        logger.error("Failed to fetch evaluation runs history", error=str(e))
        raise e

@router.get("/evals/latest")
async def get_latest_eval_summary(response: Response):
    """
    Loads the most recently created run-summary-*.json file and returns its complete JSON content.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    try:
        summary_files = list(DEFAULT_SUMMARY_DIR.glob("run-summary-*.json"))
        if not summary_files:
            return JSONResponse(
                status_code=404,
                content={
                    "error": True,
                    "code": "NOT_FOUND",
                    "detail": "No evaluation summary file exists."
                }
            )
        
        # Sort by file modification time (most recent first)
        summary_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest_file = summary_files[0]
        
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        return {"data": data}
    except Exception as e:
        logger.error("Failed to fetch latest evaluation summary", error=str(e))
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "code": "INTERNAL_SERVER_ERROR",
                "detail": str(e)
            }
        )

@router.post("/evals/run", status_code=status.HTTP_202_ACCEPTED)
async def start_evaluation(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: Optional[EvalRunRequest] = None
):
    """
    Registers an evaluation task in task_manager and triggers it in the background.
    """
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        logger.error("Database connection pool not found in app state")
        raise RuntimeError("Database pool not initialized")

    payload = payload or EvalRunRequest()
    task_id = str(uuid.uuid4())
    task_manager.register_task(task_id)

    background_tasks.add_task(
        run_evaluation_task,
        task_id=task_id,
        pool=pool,
        split=payload.split,
        prompt_version=payload.prompt_version,
        dry_run=payload.dry_run
    )

    return {"task_id": task_id}
