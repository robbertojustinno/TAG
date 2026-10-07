"""Private ROVIX home-page analytics, separate from instrument data."""
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import text

ORIGINS = {"https://rovixautomation.com.br", "https://www.rovixautomation.com.br", "https://rovix-automation.onrender.com"}
TZ = ZoneInfo("America/Sao_Paulo")

class Visit(BaseModel):
    visit_id: UUID

def period_starts(now=None):
    today = (now or datetime.now(timezone.utc)).astimezone(TZ).date()
    return today, today - timedelta(days=today.weekday()), today.replace(day=1)

def build_metrics_router(engine):
    router = APIRouter(prefix="/rovix-metrics", tags=["ROVIX metrics"])
    def ensure_tables():
        with engine.begin() as db:
            db.execute(text("CREATE TABLE IF NOT EXISTS rovix_visit_days (day VARCHAR(10) PRIMARY KEY, visits BIGINT NOT NULL DEFAULT 0)"))
            db.execute(text("CREATE TABLE IF NOT EXISTS rovix_visit_receipts (visit_id VARCHAR(36) PRIMARY KEY, day VARCHAR(10) NOT NULL)"))

    @router.post("/visit", status_code=204)
    def visit(payload: Visit, request: Request):
        if request.headers.get("origin") not in ORIGINS:
            raise HTTPException(403, "Origem não autorizada")
        agent = request.headers.get("user-agent", "").lower()
        if any(word in agent for word in ("bot", "crawler", "spider", "headless")):
            return Response(status_code=204)
        today, _, _ = period_starts()
        ensure_tables()
        with engine.begin() as db:
            inserted = db.execute(text("INSERT INTO rovix_visit_receipts (visit_id, day) VALUES (:id, :day) ON CONFLICT (visit_id) DO NOTHING RETURNING visit_id"), {"id": str(payload.visit_id), "day": today.isoformat()}).first()
            if inserted:
                db.execute(text("INSERT INTO rovix_visit_days (day, visits) VALUES (:day, 1) ON CONFLICT (day) DO UPDATE SET visits = rovix_visit_days.visits + 1"), {"day": today.isoformat()})
            db.execute(text("DELETE FROM rovix_visit_receipts WHERE day < :cutoff"), {"cutoff": (today-timedelta(days=2)).isoformat()})
        return Response(status_code=204)

    @router.get("/summary")
    def summary(response: Response, authorization: str = Header(default="")):
        token = os.getenv("ADMIN_TOKEN", "")
        # Never accept the legacy public fallback token for private analytics.
        if not token or token == "tagcheck-admin-token":
            raise HTTPException(503, "Configure o token administrativo privado para consultar métricas")
        if not secrets.compare_digest(authorization, "Bearer " + token):
            raise HTTPException(401, "Não autorizado")
        ensure_tables()
        today, week, month = period_starts()
        with engine.connect() as db:
            rows = db.execute(text("SELECT day, visits FROM rovix_visit_days WHERE day >= :start AND day <= :end"), {"start": min(week,month).isoformat(), "end": today.isoformat()}).all()
        response.headers["Cache-Control"] = "no-store, private"
        return {"daily": sum(n for d,n in rows if d == today.isoformat()), "weekly": sum(n for d,n in rows if d >= week.isoformat()), "monthly": sum(n for d,n in rows if d >= month.isoformat()), "timezone": "America/Sao_Paulo", "week_start": week.isoformat(), "month_start": month.isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()}
    return router
