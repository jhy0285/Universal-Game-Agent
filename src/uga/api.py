import secrets
import sqlite3
from contextlib import asynccontextmanager
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlsplit

import psutil
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from starlette.middleware.trustedhost import TrustedHostMiddleware

from uga import __version__
from uga.capabilities import capabilities
from uga.core.contracts import CONTRACTS, EvaluationResult, TaskSpec
from uga.core.errors import AuthorizationRequired, UGAError
from uga.evaluation.experiments import ExperimentManager
from uga.integrations.registry import AgentRegistry
from uga.orchestrator.jobs import Orchestrator


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    baseline: EvaluationResult
    candidate: EvaluationResult


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: bool = False


def create_app(root: Path | None = None, *, analysis_root: Path | None = None) -> FastAPI:
    root = (root or Path(".uga")).resolve()

    @asynccontextmanager
    async def lifespan(app):
        jobs = Orchestrator(root, analysis_root=analysis_root)
        app.state.jobs = jobs
        app.state.token = secrets.token_urlsafe(32)
        token_path = root / "api-token"
        token_path.write_text(app.state.token, encoding="utf-8")
        token_path.chmod(0o600)
        app.state.process = psutil.Process()
        app.state.process.cpu_percent()
        try:
            yield
        finally:
            jobs.close()

    app = FastAPI(
        title="Universal Game Agent",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )

    @app.middleware("http")
    async def local_access(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin:
            parsed = urlsplit(origin)
            if parsed.scheme not in ("http", "https") or parsed.netloc != request.headers.get(
                "host"
            ):
                return JSONResponse({"detail": "cross-origin access is disabled"}, 403)
        public = {"/api/v1/capabilities", "/api/v1/contracts"}
        if request.url.path.startswith("/api/v1/") and request.url.path not in public:
            token = request.headers.get("x-uga-token", "")
            if not token and request.headers.get("authorization", "").startswith("Bearer "):
                token = request.headers["authorization"][7:]
            expected = getattr(app.state, "token", None)
            if not expected or not secrets.compare_digest(token, expected):
                return JSONResponse({"detail": "local capability token required"}, 401)
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if len(await request.body()) > 65536:
                return JSONResponse({"detail": "request body exceeds 64 KiB"}, 413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'"
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(AuthorizationRequired)
    async def authorization_error(request, exc):
        return JSONResponse({"detail": str(exc)}, 403)

    @app.exception_handler(UGAError)
    async def uga_error(request, exc):
        return JSONResponse({"detail": str(exc)}, 400)

    @app.exception_handler(KeyError)
    async def not_found(request, exc):
        return JSONResponse({"detail": "record not found"}, 404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, 422)

    @app.exception_handler(sqlite3.IntegrityError)
    async def conflict(request, exc):
        return JSONResponse({"detail": "record already exists"}, 409)

    static = Path(str(files("uga") / "dashboard"))
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard():
        return (
            (static / "index.html")
            .read_text(encoding="utf-8")
            .replace("{{UGA_TOKEN}}", app.state.token)
        )

    @app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
    def docs():
        return '<!doctype html><html lang="en"><meta charset="utf-8"><title>UGA API v1</title><link rel="stylesheet" href="/static/style.css"><main><h1>UGA API v1</h1><p>Local, versioned agent jobs.</p><p><a href="/openapi.json">OpenAPI schema</a> · <a href="/api/v1/contracts">Wire contracts</a> · <a href="/">Dashboard</a></p><p>Send X-UGA-Token or Authorization: Bearer with the local token from the state directory api-token file. Tokens rotate at server startup. Never commit or share this file.</p><p>POST /api/v1/jobs → GET /api/v1/jobs/{id} → POST /api/v1/jobs/{id}/cancel</p><p>The server only runs registered operations. Builder build and Godot workflows require authorized=true and only execute the generated original UGA project. Export requires a matching installed Godot template.</p></main></html>'

    @app.get("/health")
    def health():
        return {
            "status": "ok" if app.state.jobs.thread.is_alive() else "degraded",
            "version": __version__,
        }

    @app.get("/api/v1/capabilities")
    def get_capabilities():
        return capabilities()

    @app.get("/api/v1/contracts")
    def contracts():
        return {model.__name__: model.model_json_schema() for model in CONTRACTS}

    @app.get("/api/v1/agents")
    def agents():
        return AgentRegistry().describe()

    @app.get("/api/v1/system")
    def system():
        process = app.state.process
        workers = []
        with app.state.jobs._lock:
            for identity, run in app.state.jobs.running.items():
                workers.append(
                    {"task_id": identity, "agent": run.spec.agent, "health": run.watchdog.inspect()}
                )
        return {
            "cpu_percent": psutil.cpu_percent(),
            "process_cpu_percent": process.cpu_percent(),
            "rss_mb": process.memory_info().rss / 2**20,
            "ram_percent": psutil.virtual_memory().percent,
            "gpu": None,
            "vram_mb": None,
            "gpu_status": "not measured; CPU workflow",
            "workers": workers,
            "orchestrator_healthy": app.state.jobs.thread.is_alive(),
        }

    @app.get("/api/v1/jobs")
    def jobs(limit: int = Query(50, ge=1, le=100)):
        return app.state.jobs.store.tasks(limit)

    @app.post("/api/v1/jobs", status_code=202)
    def submit(task: TaskSpec):
        return app.state.jobs.submit(task)

    @app.get("/api/v1/jobs/{task_id}")
    def job(task_id: str):
        return app.state.jobs.store.task(task_id)

    @app.post("/api/v1/jobs/{task_id}/cancel")
    def cancel(task_id: str):
        return app.state.jobs.cancel(task_id)

    @app.post("/api/v1/stop")
    def stop_all():
        stopped = []
        for row in app.state.jobs.store.tasks(100):
            if row["status"] in ("running", "queued"):
                app.state.jobs.cancel(row["id"])
                stopped.append(row["id"])
        return {"cancelled": stopped}

    @app.get("/api/v1/events")
    def events(
        task_id: str | None = None,
        after: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
    ):
        return app.state.jobs.store.events(task_id, after, limit)

    @app.get("/api/v1/jobs/{task_id}/preview")
    def preview(task_id: str):
        row = app.state.jobs.store.task(task_id)
        base = root / "jobs" / row["id"]
        for path in (base / "last-frame.png", base / "reference-play" / "last-frame.png"):
            if path.is_file() and path.resolve().is_relative_to(base.resolve()):
                return FileResponse(path, media_type="image/png")
        raise HTTPException(404, "no captured frame yet")

    @app.get("/api/v1/jobs/{task_id}/artifacts")
    def artifacts(task_id: str):
        row = app.state.jobs.store.task(task_id)
        if row["status"] in ("queued", "running"):
            return []
        store = app.state.jobs.store
        name = "job-artifacts:" + task_id
        saved = store.load_checkpoint(name)
        if saved:
            return saved["artifacts"]
        base = root / "jobs" / row["id"]
        result = []
        for path in sorted(base.rglob("*"))[:300]:
            if (
                path.is_file()
                and not path.is_symlink()
                and path.suffix in (".json", ".png", ".log", ".gd", ".tscn", ".godot", ".cfg")
                and path.stat().st_size <= 8_000_000
            ):
                content_type = (
                    "image/png"
                    if path.suffix == ".png"
                    else "application/json"
                    if path.suffix == ".json"
                    else "text/plain"
                )
                ref = store.put_artifact(
                    path.read_bytes(),
                    content_type,
                    "png" if path.suffix == ".png" else "json" if path.suffix == ".json" else "txt",
                )
                result.append(
                    {"name": str(path.relative_to(base)), "reference": ref.model_dump(mode="json")}
                )
        store.checkpoint(name, {"artifacts": result})
        return result

    @app.get("/api/v1/artifacts/{artifact_id}")
    def artifact(artifact_id: str):
        store = app.state.jobs.store
        ref = store.artifact(artifact_id)
        return Response(store.read_artifact(ref), media_type=ref.media_type)

    @app.get("/api/v1/experiments")
    def experiments():
        return [r["value"] for r in app.state.jobs.store.list_checkpoints("experiment:")]

    @app.post("/api/v1/experiments", status_code=201)
    def propose(data: ComparisonRequest):
        return ExperimentManager(app.state.jobs.store).propose(data.baseline, data.candidate)

    @app.post("/api/v1/experiments/{identity}/approve")
    def approve(identity: str, data: ApprovalRequest):
        return ExperimentManager(app.state.jobs.store).promote(identity, approved=data.approved)

    @app.post("/api/v1/rollback")
    def rollback():
        return ExperimentManager(app.state.jobs.store).rollback()

    return app
