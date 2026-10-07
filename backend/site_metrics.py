"""Private ROVIX home-page analytics, separate from instrument data."""
import os
import secrets
import json
from threading import Lock
from urllib.request import urlopen, Request as URLRequest
from urllib.error import HTTPError, URLError
from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from urllib.parse import urlsplit
from ipaddress import ip_address
from sqlalchemy import text

ORIGINS = {"https://rovixautomation.com.br", "https://www.rovixautomation.com.br", "https://rovix-automation.onrender.com"}
TZ = ZoneInfo("America/Sao_Paulo")
OSINT_LOCK = Lock()

def lookup_public_ip(ip):
    request = URLRequest("https://api.ipapi.is/?q=" + ip, headers={"User-Agent": "ROVIX-Metrics/1.0"})
    with urlopen(request, timeout=8) as upstream:
        raw = json.loads(upstream.read(65536))
    if raw.get("error") or raw.get("is_bogon"):
        raise ValueError("IP sem dados públicos disponíveis")
    return {key: str(raw.get(key) or "")[:255] for key in ("company", "asn", "city", "region", "country", "timezone")}


class Visit(BaseModel):
    visit_id: UUID
    referrer: str = Field(default="", max_length=2048)
    language: str = Field(default="", max_length=40)
    screen: str = Field(default="", max_length=40)
    timezone: str = Field(default="", max_length=100)

def period_starts(now=None):
    today = (now or datetime.now(timezone.utc)).astimezone(TZ).date()
    return today, today - timedelta(days=today.weekday()), today.replace(day=1)

def visitor_info(agent):
    browser = next((name for marker, name in [("Edg/", "Edge"), ("OPR/", "Opera"), ("SamsungBrowser/", "Samsung Internet"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari")] if marker in agent), "Outro")
    system = next((name for marker, name in [("Android", "Android"), ("iPhone", "iOS"), ("iPad", "iPadOS"), ("Windows", "Windows"), ("Macintosh", "macOS"), ("Linux", "Linux")] if marker in agent), "Outro")
    device = "Tablet" if "iPad" in agent or ("Android" in agent and "Mobile" not in agent) else "Celular" if "Mobile" in agent or "iPhone" in agent else "Computador"
    return browser, system, device

def build_metrics_router(engine):
    router = APIRouter(prefix="/rovix-metrics", tags=["ROVIX metrics"])
    def ensure_tables():
        with engine.begin() as db:
            db.execute(text("CREATE TABLE IF NOT EXISTS rovix_visit_days (day VARCHAR(10) PRIMARY KEY, visits BIGINT NOT NULL DEFAULT 0)"))
            db.execute(text("CREATE TABLE IF NOT EXISTS rovix_visit_receipts (visit_id VARCHAR(36) PRIMARY KEY, day VARCHAR(10) NOT NULL)"))

            db.execute(text("CREATE TABLE IF NOT EXISTS rovix_visit_details (visit_id VARCHAR(36) PRIMARY KEY, day VARCHAR(10) NOT NULL, visited_at VARCHAR(40) NOT NULL, ip VARCHAR(64) NOT NULL, browser VARCHAR(80) NOT NULL, system VARCHAR(80) NOT NULL, device VARCHAR(40) NOT NULL, referrer VARCHAR(255) NOT NULL, language VARCHAR(40) NOT NULL, screen VARCHAR(40) NOT NULL, timezone VARCHAR(100) NOT NULL)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS rovix_visit_details_time ON rovix_visit_details (visited_at)"))

            db.execute(text("CREATE INDEX IF NOT EXISTS rovix_visit_details_ip_day ON rovix_visit_details (ip, day)"))
            db.execute(text("CREATE TABLE IF NOT EXISTS rovix_ip_osint (ip VARCHAR(64) PRIMARY KEY, fetched_at VARCHAR(40) NOT NULL, payload TEXT NOT NULL)"))
            db.execute(text("CREATE TABLE IF NOT EXISTS rovix_osint_budget (day VARCHAR(10) PRIMARY KEY, used INTEGER NOT NULL DEFAULT 0)"))

    def authorize(authorization):
        token = os.getenv("ADMIN_TOKEN", "")
        if not token or token == "tagcheck-admin-token":
            raise HTTPException(503, "Configure o token administrativo privado para consultar métricas")
        if not secrets.compare_digest(authorization, "Bearer " + token):
            raise HTTPException(401, "Não autorizado")

    @router.get("/ip-osint")
    def ip_osint(ip: str, response: Response, authorization: str = Header(default="")):
        authorize(authorization)
        response.headers["Cache-Control"] = "no-store, private"
        try:
            address = ip_address(ip)
        except ValueError:
            raise HTTPException(422, "IP inválido")
        if not address.is_global:
            raise HTTPException(422, "Consulta disponível somente para IPs públicos")
        ip = str(address)
        ensure_tables()
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=7)).isoformat()
        with OSINT_LOCK:
            with engine.begin() as db:
                known = db.execute(text("SELECT 1 FROM rovix_visit_details WHERE ip = :ip LIMIT 1"), {"ip": ip}).first()
                if not known:
                    raise HTTPException(404, "IP não encontrado no histórico de visitas")
                cached = db.execute(text("SELECT payload, fetched_at FROM rovix_ip_osint WHERE ip = :ip AND fetched_at >= :cutoff"), {"ip": ip, "cutoff": cutoff}).first()
                if cached:
                    return {"ip": ip, "source": "ipapi.is", "fetched_at": cached[1], "cached": True, **json.loads(cached[0])}
                reserved = db.execute(text("INSERT INTO rovix_osint_budget (day, used) VALUES (:day, 1) ON CONFLICT (day) DO UPDATE SET used = rovix_osint_budget.used + 1 WHERE rovix_osint_budget.used < 20 RETURNING used"), {"day": now.date().isoformat()}).first()
                if not reserved:
                    raise HTTPException(429, "Limite diário de consultas gratuitas atingido. Tente amanhã.")
            try:
                result = lookup_public_ip(ip)
            except HTTPError as error:
                if error.code == 429:
                    with engine.begin() as db:
                        db.execute(text("UPDATE rovix_osint_budget SET used = 20 WHERE day = :day"), {"day": now.date().isoformat()})
                    raise HTTPException(429, "Fonte pública atingiu o limite gratuito. Tente amanhã.")
                raise HTTPException(502, "Fonte pública indisponível")
            except (URLError, TimeoutError, OSError, ValueError, TypeError):
                raise HTTPException(502, "Não foi possível consultar a fonte pública. Tente mais tarde.")
            with engine.begin() as db:
                db.execute(text("INSERT INTO rovix_ip_osint (ip, fetched_at, payload) VALUES (:ip, :at, :payload) ON CONFLICT (ip) DO UPDATE SET fetched_at = excluded.fetched_at, payload = excluded.payload"), {"ip": ip, "at": now.isoformat(), "payload": json.dumps(result)})
            return {"ip": ip, "source": "ipapi.is", "fetched_at": now.isoformat(), "cached": False, **result}

    @router.post("/visit", status_code=204)
    def visit(payload: Visit, request: Request):
        if request.headers.get("origin") not in ORIGINS:
            raise HTTPException(403, "Origem não autorizada")
        raw_agent = request.headers.get("user-agent", "")[:1024]
        agent = raw_agent.lower()
        if any(word in agent for word in ("bot", "crawler", "spider", "headless")):
            return Response(status_code=204)
        today, _, _ = period_starts()
        browser, system, device = visitor_info(raw_agent)
        try:
            client_ip = str(ip_address(request.client.host)) if request.client else "Indisponível"
        except ValueError:
            client_ip = "Indisponível"
        try:
            origin = urlsplit(payload.referrer)
            referrer = (origin.hostname or "")[:255] if origin.scheme in ("http", "https") else ""
        except ValueError:
            referrer = ""
        ensure_tables()
        with engine.begin() as db:
            inserted = db.execute(text("INSERT INTO rovix_visit_receipts (visit_id, day) VALUES (:id, :day) ON CONFLICT (visit_id) DO NOTHING RETURNING visit_id"), {"id": str(payload.visit_id), "day": today.isoformat()}).first()
            if inserted:
                db.execute(text("INSERT INTO rovix_visit_details (visit_id, day, visited_at, ip, browser, system, device, referrer, language, screen, timezone) VALUES (:id, :day, :visited_at, :ip, :browser, :system, :device, :referrer, :language, :screen, :timezone)"), {"id": str(payload.visit_id), "day": today.isoformat(), "visited_at": datetime.now(timezone.utc).isoformat(), "ip": client_ip, "browser": browser, "system": system, "device": device, "referrer": referrer, "language": payload.language, "screen": payload.screen, "timezone": payload.timezone})
                db.execute(text("INSERT INTO rovix_visit_days (day, visits) VALUES (:day, 1) ON CONFLICT (day) DO UPDATE SET visits = rovix_visit_days.visits + 1"), {"day": today.isoformat()})
            db.execute(text("DELETE FROM rovix_visit_receipts WHERE day < :cutoff"), {"cutoff": (today-timedelta(days=2)).isoformat()})
            db.execute(text("DELETE FROM rovix_visit_details WHERE day < :cutoff"), {"cutoff": (today-timedelta(days=90)).isoformat()})
            db.execute(text("DELETE FROM rovix_ip_osint WHERE fetched_at < :cutoff"), {"cutoff": (datetime.now(timezone.utc)-timedelta(days=90)).isoformat()})
        return Response(status_code=204)

    @router.get("/summary")
    def summary(response: Response, authorization: str = Header(default="")):
        authorize(authorization)
        ensure_tables()
        today, week, month = period_starts()
        with engine.connect() as db:
            rows = db.execute(text("SELECT day, visits FROM rovix_visit_days WHERE day >= :start AND day <= :end"), {"start": min(week,month).isoformat(), "end": today.isoformat()}).all()
            recent = [dict(row) for row in db.execute(text("SELECT visited_at, ip, browser, system, device, referrer, language, screen, timezone FROM rovix_visit_details ORDER BY visited_at DESC LIMIT 100")).mappings()]
            unique_ips = db.execute(text("SELECT COUNT(DISTINCT ip) FROM rovix_visit_details WHERE day = :day AND ip != 'Indisponível'"), {"day": today.isoformat()}).scalar()
            ip_counts = [dict(row) for row in db.execute(text("SELECT ip, COUNT(*) AS total, SUM(CASE WHEN day = :today THEN 1 ELSE 0 END) AS daily, SUM(CASE WHEN day >= :week THEN 1 ELSE 0 END) AS weekly, SUM(CASE WHEN day >= :month THEN 1 ELSE 0 END) AS monthly, MIN(visited_at) AS first_seen, MAX(visited_at) AS last_seen FROM rovix_visit_details WHERE day >= :cutoff AND day <= :today AND ip != 'Indisponível' GROUP BY ip ORDER BY total DESC, ip LIMIT 500"), {"today": today.isoformat(), "week": week.isoformat(), "month": month.isoformat(), "cutoff": (today-timedelta(days=90)).isoformat()}).mappings()]
            osint = {row["ip"]: {"fetched_at": row["fetched_at"], **json.loads(row["payload"])} for row in db.execute(text("SELECT ip, fetched_at, payload FROM rovix_ip_osint WHERE fetched_at >= :cutoff"), {"cutoff": (datetime.now(timezone.utc)-timedelta(days=7)).isoformat()}).mappings()}
            for row in ip_counts:
                row["osint"] = osint.get(row["ip"])
        response.headers["Cache-Control"] = "no-store, private"
        return {"ip_counts": ip_counts, "recent": recent, "unique_ips_today": unique_ips, "daily": sum(n for d,n in rows if d == today.isoformat()), "weekly": sum(n for d,n in rows if d >= week.isoformat()), "monthly": sum(n for d,n in rows if d >= month.isoformat()), "timezone": "America/Sao_Paulo", "week_start": week.isoformat(), "month_start": month.isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()}
    return router
