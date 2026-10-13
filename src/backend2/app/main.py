from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import Base, engine
from app.migrations import run_migrations
from app.routers import (
    admin,
    attendance,
    auth,
    drives,
    import_students,
    offers,
    policy,
    reports,
    students,
)

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Run non-destructive, idempotent startup migrations and seed defaults
    run_migrations(engine)
    yield


app = FastAPI(
    title="NFSU Placement Management",
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)
DOCS_PATHS = ("/docs", "/openapi.json")
DOCS_CSP = (
    "default-src 'none'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; connect-src 'self'; frame-ancestors 'none'"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Requested-With", "X-MFA-Token"],
)


@app.middleware("http")
async def csrf_and_headers(request: Request, call_next):
    if request.method in UNSAFE and request.headers.get("x-requested-with") != "placement-ui":
        return JSONResponse({"detail": "Missing X-Requested-With header"}, status_code=403)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    if settings.enable_hsts or request.url.scheme == "https":
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path in DOCS_PATHS:  # Swagger UI needs its CDN assets; dev only
        resp.headers["Content-Security-Policy"] = DOCS_CSP
    else:
        resp.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    resp.headers.setdefault("Cache-Control", "no-store")
    return resp


for r in (
    auth.router,
    students.router,
    offers.router,
    attendance.router,
    reports.router,
    drives.router,
    policy.policy_router,
    policy.reviews_router,
    import_students.router,
    admin.router,
):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}
