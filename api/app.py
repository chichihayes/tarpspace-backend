import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

from db.database import get_db
from core.matcher import TarpSpaceMatcher
from core.auth import verify_token, get_user_id

app = FastAPI(title="TarpSpace Phase 1", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

matcher_instance = None


def get_matcher(db: Session = Depends(get_db)):
    global matcher_instance
    if matcher_instance is None:
        matcher_instance = TarpSpaceMatcher(db)
    else:
        matcher_instance.db = db
    return matcher_instance


class MatchRequest(BaseModel):
    query: str
    top_k: int = 8
    mandate_id: Optional[str] = None
    owner_id: Optional[str] = None
    mandate: Optional[dict] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/match")
def match(
    req: MatchRequest,
    matcher: TarpSpaceMatcher = Depends(get_matcher),
    payload: dict = Depends(verify_token)
):
    user_id = get_user_id(payload)
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    return matcher.match(req.query, req.top_k, req.mandate_id, req.mandate, user_id)


@app.get("/agents")
def list_agents(
    db: Session = Depends(get_db),
    payload: dict = Depends(verify_token)
):
    rows = db.execute(text(
        "SELECT id, name, category, mandate, is_active FROM inventory ORDER BY created_at"
    )).fetchall()
    return [
        {"id": str(r[0]), "name": r[1], "category": r[2], "mandate": r[3], "is_active": r[4]}
        for r in rows
    ]


@app.get("/agents/{agent_id}")
def get_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    payload: dict = Depends(verify_token)
):
    row = db.execute(text(
        "SELECT id, name, category, mandate, is_active FROM inventory WHERE id = :id"
    ), {"id": agent_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"id": str(row[0]), "name": row[1], "category": row[2], "mandate": row[3], "is_active": row[4]}


@app.get("/logs")
def get_logs(
    db: Session = Depends(get_db),
    payload: dict = Depends(verify_token)
):
    user_id = get_user_id(payload)
    rows = db.execute(text("""
        SELECT id, query, result_count, latency_ms, created_at
        FROM search_runs
        WHERE user_id = :user_id
        ORDER BY created_at DESC
        LIMIT 50
    """), {"user_id": user_id}).fetchall()
    return [
        {"id": str(r[0]), "query": r[1], "result_count": r[2], "latency_ms": r[3], "created_at": str(r[4])}
        for r in rows
    ]


@app.get("/me")
def get_me(payload: dict = Depends(verify_token)):
    return {
        "user_id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role")
    }
