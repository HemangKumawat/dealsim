"""
DealSim FastAPI application factory.

Production-ready with:
- CORS configuration (configurable allowed origins)
- Per-endpoint-group rate limiting (token bucket, per IP)
- Static file serving (index.html at root)
- Health check endpoint
- Structured logging
"""

from __future__ import annotations

import os
import secrets
import logging
import traceback

from html import escape as html_escape
from pathlib import Path

import asyncio as _asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from dealsim_mvp import __version__
from dealsim_mvp.api.routes import router as api_router
from dealsim_mvp.monitoring import (
    ErrorTrackingMiddleware,
    RequestLoggingMiddleware,
    get_health_data,
)
from dealsim_mvp.rate_limiter import RateLimitMiddleware

# ---------------------------------------------------------------------------
# LLM configuration — read once at import time
# ---------------------------------------------------------------------------
_USE_LLM      = os.environ.get("DEALSIM_USE_LLM", "false").lower() in ("1", "true", "yes")
_LLM_API_KEY  = os.environ.get("LLM_API_KEY", "").strip()
_LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1").strip()
_LLM_MODEL    = os.environ.get("LLM_MODEL", "deepseek-chat").strip()
_LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
_LLM_MAX_TOKENS  = int(os.environ.get("LLM_MAX_TOKENS", "300"))
_LLM_TIMEOUT     = int(os.environ.get("LLM_TIMEOUT", "30"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("dealsim")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def _build_simulator():
    """
    Return the configured default simulator instance.

    Uses engine_factory to detect the best available engine from environment.
    Fallback chain: MiroFish → LLM → RuleBasedSimulator.
    """
    from dealsim_mvp.core.engine_factory import build_simulator
    return build_simulator(engine="auto")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Manage startup (background TTL cleanup) and shutdown (MiroFish cleanup)."""
    # Startup: launch periodic session cleanup
    async def _cleanup_loop():
        while True:
            await _asyncio.sleep(300)  # every 5 minutes
            try:
                from dealsim_mvp.core.session import cleanup_stale_sessions
                cleanup_stale_sessions()
            except Exception:
                logger.debug("Session cleanup task error", exc_info=True)

    cleanup_task = _asyncio.create_task(_cleanup_loop())
    yield
    # Shutdown: stop cleanup task, clean up MiroFish simulations
    cleanup_task.cancel()
    from dealsim_mvp.core.session import _SESSIONS
    for sid, session in list(_SESSIONS.items()):
        if hasattr(session.simulator, 'cleanup'):
            try:
                await session.simulator.cleanup()
            except Exception:
                pass
    logger.info("Shutdown: cleaned up %d sessions", len(_SESSIONS))


def create_app() -> FastAPI:
    # Disable API docs in production (set DEALSIM_ENV=production)
    is_production = os.environ.get("DEALSIM_ENV", "").lower() == "production"
    app = FastAPI(
        title="DealSim API",
        description="AI-powered negotiation training simulator",
        version=__version__,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        lifespan=_lifespan,
    )

    # -- CORS ---------------------------------------------------------------
    allowed_origins = os.environ.get("DEALSIM_CORS_ORIGINS", "").split(",")
    allowed_origins = [o.strip() for o in allowed_origins if o.strip()]
    if not allowed_origins:
        logger.warning("DEALSIM_CORS_ORIGINS not set — defaulting to localhost only")
        allowed_origins = ["http://localhost:3000", "http://localhost:8000"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,  # Only enable if cookies/auth headers needed
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Monitoring middlewares (outermost = first to run) ------------------
    # ErrorTrackingMiddleware wraps RequestLoggingMiddleware so that even
    # requests that raise are still counted and logged.
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(ErrorTrackingMiddleware)

    # -- Per-endpoint-group rate limiting (token bucket, per IP) -----------
    # Groups and limits are defined in rate_limiter.py.
    # Health endpoints are always unlimited.
    app.add_middleware(RateLimitMiddleware)

    # -- Request ID middleware -----------------------------------------------
    # Assigns a unique token to every request, attached to request.state and
    # returned as X-Request-ID in every response (including error responses).
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        req_id = secrets.token_hex(16)  # 32-char hex, cryptographically random
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

    # -- Global exception handler (catch-all, never leak internals) ---------
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "Unhandled exception on %s %s [request_id=%s]:\n%s",
            request.method,
            request.url.path,
            req_id,
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "code": "INTERNAL_ERROR", "request_id": req_id},
            headers={"X-Request-ID": req_id},
        )

    # -- Simulator selection ------------------------------------------------
    # Resolved once at startup; stored on app.state so the health endpoint
    # can inspect it without re-importing.
    _simulator = _build_simulator()
    app.state.simulator = _simulator
    app.state.use_llm = _USE_LLM and bool(_LLM_API_KEY)

    # -- API routes ---------------------------------------------------------
    app.include_router(api_router)

    # -- Health check (enhanced) --------------------------------------------
    from dealsim_mvp.core.session import _SESSIONS

    @app.get("/api/health", tags=["system"])
    @app.get("/health", tags=["system"])
    def health_check():
        data = get_health_data(active_sessions=len(_SESSIONS))
        if not is_production:
            data["version"] = __version__

        # Simulator status — report which engine is active
        sim = app.state.simulator
        sim_name = type(sim).__name__
        engine_map = {
            "LLMSimulator": "llm",
            "MiroFishSimulator": "mirofish",
            "RuleBasedSimulator": "rule_based",
        }
        engine_label = engine_map.get(sim_name, "rule_based")

        llm_available: bool = False
        if hasattr(sim, "is_available"):
            try:
                llm_available = sim.is_available()
            except Exception:
                llm_available = False

        data["simulator_engine"] = engine_label
        data["llm_available"] = llm_available

        # Report available engines
        try:
            from dealsim_mvp.core.engine_factory import get_available_engines
            data["available_engines"] = get_available_engines()
        except Exception:
            data["available_engines"] = ["rule_based"]

        return data

    # -- Static files & root HTML ------------------------------------------
    # Try multiple locations: env var, relative to source, Docker /app/static
    static_dir = None
    for candidate in [
        os.environ.get("STATIC_DIR", ""),
        str(Path(__file__).resolve().parent.parent.parent / "static"),
        "/app/static",
        str(Path.cwd() / "static"),
    ]:
        if candidate and Path(candidate).is_dir():
            static_dir = Path(candidate)
            break

    if static_dir is not None:
        @app.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
        def serve_privacy():
            privacy_file = static_dir / "privacy.html"
            if privacy_file.exists():
                return privacy_file.read_text(encoding="utf-8")
            raise HTTPException(status_code=404, detail="Privacy policy not found")

        # Mount at "/" with html=True so index.html is served automatically at root
        # and all JS/CSS assets are reachable at their root paths (e.g. /gamification.js).
        # This mount MUST come after all API routes — FastAPI resolves routes before mounts.
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    else:
        @app.get("/", include_in_schema=False)
        def serve_root_fallback():
            return {"message": "DealSim API is running. Static files not found."}

    # -- Admin stats (protected by ADMIN_KEY via Authorization header) --------
    from dealsim_mvp.analytics import get_tracker
    from dealsim_mvp.feedback import get_collector

    admin_key = os.environ.get("DEALSIM_ADMIN_KEY", "")

    def _verify_admin(request: Request) -> None:
        if not admin_key:
            raise HTTPException(
                status_code=503,
                detail="Admin dashboard disabled — DEALSIM_ADMIN_KEY not configured",
            )
        provided = request.headers.get("authorization", "")
        # Support both raw key and "Bearer <key>" format
        if provided.startswith("Bearer "):
            provided = provided[7:]
        if not provided or not secrets.compare_digest(provided, admin_key):
            raise HTTPException(status_code=403, detail="Invalid admin key")

    @app.get("/api/admin/stats", tags=["admin"])
    def admin_stats_json(request: Request):
        """JSON endpoint: full analytics + feedback summary."""
        _verify_admin(request)
        stats = get_tracker().get_stats()
        feedback_summary = get_collector().get_summary()
        return {
            **stats,
            "feedback": feedback_summary,
        }

    @app.get("/api/admin/analytics", tags=["admin"])
    def admin_analytics_extended(request: Request):
        """Extended analytics: scores by scenario/difficulty, period breakdowns."""
        _verify_admin(request)
        from dealsim_mvp.api.analytics import _read_jsonl, USER_HISTORY_FILE
        from collections import defaultdict
        from datetime import datetime, timezone, timedelta

        stats = get_tracker().get_stats()
        feedback_summary = get_collector().get_summary()

        # ------------------------------------------------------------------
        # Sessions today / this week from daily_active_sessions (already in
        # stats) — derive from the last-30-days array.
        # ------------------------------------------------------------------
        today_str = datetime.now(timezone.utc).date().isoformat()
        # ISO week: find Monday of current week
        today_date = datetime.now(timezone.utc).date()
        week_start = (today_date - timedelta(days=today_date.weekday())).isoformat()

        sessions_today = 0
        sessions_this_week = 0
        for entry in stats.get("daily_active_sessions", []):
            d = entry["date"]
            count = entry["sessions"]
            if d == today_str:
                sessions_today = count
            if d >= week_start:
                sessions_this_week += count

        # ------------------------------------------------------------------
        # Scores by scenario type and difficulty — read from user_history.
        # This file has one record per *completed* session with full context.
        # ------------------------------------------------------------------
        history = _read_jsonl(USER_HISTORY_FILE)

        scenario_scores: dict[str, list[int]] = defaultdict(list)
        difficulty_scores: dict[str, list[int]] = defaultdict(list)

        for r in history:
            score = r.get("overall_score")
            if score is None:
                continue
            stype = r.get("scenario_type", "unknown")
            diff = r.get("difficulty", "unknown")
            scenario_scores[stype].append(score)
            difficulty_scores[diff].append(score)

        avg_score_by_scenario = {
            k: round(sum(v) / len(v), 1)
            for k, v in scenario_scores.items()
        }
        avg_score_by_difficulty = {
            k: round(sum(v) / len(v), 1)
            for k, v in difficulty_scores.items()
        }

        # ------------------------------------------------------------------
        # Active sessions
        # ------------------------------------------------------------------
        from dealsim_mvp.core.session import _SESSIONS
        active_sessions = len(_SESSIONS)

        return {
            **stats,
            "feedback": feedback_summary,
            "sessions_today": sessions_today,
            "sessions_this_week": sessions_this_week,
            "avg_score_by_scenario": avg_score_by_scenario,
            "avg_score_by_difficulty": avg_score_by_difficulty,
            "active_sessions": active_sessions,
        }

    @app.get("/admin/stats", tags=["admin"], include_in_schema=False)
    def admin_stats_html(request: Request):
        """HTML dashboard for browser viewing."""
        _verify_admin(request)

        stats = get_tracker().get_stats()
        fb = get_collector().get_summary()

        # Build feature usage rows (sorted most-used first)
        feature_rows = ""
        for fname in stats.get("feature_usage_order", []):
            count = stats["feature_usage"].get(fname, 0)
            feature_rows += f"<tr><td>{html_escape(str(fname))}</td><td>{count}</td></tr>\n"
        if not feature_rows:
            feature_rows = '<tr><td colspan="2" style="color:rgba(255,255,255,0.3)">No feature data yet</td></tr>'

        # Build feedback rows
        feedback_rows = ""
        for item in fb.get("recent_comments", [])[:10]:
            stars = "\u2605" * item.get("rating", 0) + "\u2606" * (5 - item.get("rating", 0))
            comment = html_escape((item.get("comment", "") or "\u2014")[:80])
            ts = html_escape(item.get("submitted_at", "")[:19])
            feedback_rows += f"<tr><td>{ts}</td><td>{stars}</td><td>{comment}</td></tr>\n"
        if not feedback_rows:
            feedback_rows = '<tr><td colspan="3" style="color:rgba(255,255,255,0.3)">No feedback yet</td></tr>'

        # Build scenario popularity rows
        scenario_rows = ""
        for stype, count in sorted(stats.get("scenario_popularity", {}).items(), key=lambda x: -x[1]):
            scenario_rows += f"<tr><td>{html_escape(str(stype))}</td><td>{count}</td></tr>\n"

        html = f"""<!DOCTYPE html>
<html><head><title>DealSim Admin</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; background: #1a1b4b; color: #e2e8f0; }}
  h1 {{ color: #f95c5c; }}
  h2 {{ margin-top: 0; font-size: 1rem; color: rgba(255,255,255,0.6); }}
  .card {{ background: #1e2055; border-radius: 12px; padding: 24px; margin: 16px 0; border: 1px solid rgba(255,255,255,0.1); }}
  .stat {{ display: inline-block; margin: 0 32px 16px 0; }}
  .stat-num {{ font-size: 2rem; font-weight: 800; color: #f95c5c; }}
  .stat-label {{ font-size: 0.85rem; color: rgba(255,255,255,0.5); }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
  th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid rgba(255,255,255,0.1); font-size: 0.9rem; }}
  th {{ color: rgba(255,255,255,0.5); font-weight: 600; text-transform: uppercase; font-size: 0.75rem; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 600px) {{ .grid {{ grid-template-columns: 1fr; }} }}
</style></head><body>
<h1>DealSim Admin Dashboard</h1>

<div class="card">
  <div class="stat"><div class="stat-num">{html_escape(str(stats['total_sessions']))}</div><div class="stat-label">Sessions</div></div>
  <div class="stat"><div class="stat-num">{html_escape(str(stats['total_completed']))}</div><div class="stat-label">Completed</div></div>
  <div class="stat"><div class="stat-num">{html_escape(str(stats['completion_rate']))}%</div><div class="stat-label">Completion Rate</div></div>
  <div class="stat"><div class="stat-num">{html_escape(str(stats['average_score']))}</div><div class="stat-label">Avg Score</div></div>
  <div class="stat"><div class="stat-num">{html_escape(str(stats['total_messages']))}</div><div class="stat-label">Messages</div></div>
</div>

<div class="card">
  <div class="stat"><div class="stat-num">{html_escape(str(fb['total_feedback']))}</div><div class="stat-label">Total Feedback</div></div>
  <div class="stat"><div class="stat-num">{html_escape(str(fb['average_rating']))}</div><div class="stat-label">Avg Rating (1-5)</div></div>
  <div class="stat"><div class="stat-num">{html_escape(str(fb['feedback_with_comment_count']))}</div><div class="stat-label">With Comments</div></div>
  <div class="stat"><div class="stat-num">{html_escape(str(fb['feedback_with_email_count']))}</div><div class="stat-label">Left Email</div></div>
</div>

<div class="grid">
  <div class="card">
    <h2>Feature Usage (most &rarr; least)</h2>
    <table>
      <tr><th>Feature</th><th>Count</th></tr>
      {feature_rows}
    </table>
  </div>
  <div class="card">
    <h2>Scenario Popularity</h2>
    <table>
      <tr><th>Scenario</th><th>Count</th></tr>
      {scenario_rows if scenario_rows else '<tr><td colspan="2" style="color:rgba(255,255,255,0.3)">No data</td></tr>'}
    </table>
  </div>
</div>

<div class="card">
  <h2>Recent Feedback</h2>
  <table>
    <tr><th>Time</th><th>Rating</th><th>Comment</th></tr>
    {feedback_rows}
  </table>
</div>

<p style="text-align:center;color:rgba(255,255,255,0.3);font-size:0.8rem;margin-top:32px;">
  JSON API: <code style="color:#f95c5c;">GET /api/admin/stats</code> (Authorization header required)
</p>
</body></html>"""
        return HTMLResponse(content=html)

    logger.info("DealSim %s started (CORS origins: %s)", __version__, allowed_origins)
    return app


# Gunicorn / uvicorn entry point
app = create_app()
