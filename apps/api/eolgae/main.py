"""FastAPI entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from eolgae.routers import (
    auth,
    aws_connections,
    canvas,
    deployments,
    environments,
    groups,
    settings,
    targets,
)

app = FastAPI(
    title="Eolgae API",
    version="0.0.1",
    description="GitOps for AWS Infrastructure — Canvas + Apply backend",
)

# CORS — local dev: Next.js dev / Caddy 둘 다 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:80",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(aws_connections.router)
app.include_router(canvas.router)
app.include_router(deployments.router)
app.include_router(environments.router)
app.include_router(groups.router)
app.include_router(groups.ownership_router)
app.include_router(settings.router)
app.include_router(targets.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Eolgae API running", "status": "ok"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
