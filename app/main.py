"""FastAPI application entry point."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.config import settings
from app.database import init_db
from app.routers import generate as generate_router
from app.routers import scripts as scripts_router

BASE_DIR = os.path.dirname(__file__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="AI-driven database script generation and risk validation platform",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files
static_dir = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# API routers
app.include_router(generate_router.router)
app.include_router(scripts_router.router)


# ---------------------------------------------------------------------------
# Web UI routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"app_name": settings.app_name})


@app.get("/scripts", response_class=HTMLResponse, include_in_schema=False)
async def scripts_page(request: Request):
    return templates.TemplateResponse(request, "scripts.html", {"app_name": settings.app_name})


@app.get("/scripts/{script_id}", response_class=HTMLResponse, include_in_schema=False)
async def script_detail_page(request: Request, script_id: int):
    return templates.TemplateResponse(
        request,
        "script_detail.html",
        {"app_name": settings.app_name, "script_id": script_id},
    )
