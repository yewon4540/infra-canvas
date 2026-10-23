"""Deployment route assembly; public exports retained for callers."""
from fastapi import APIRouter
from eolgae.execution.dispatch import run_apply, run_destroy, run_plan
from .deployment_routes import read, plans, approval, apply, destroy
from .deployment_routes.common import REPEAT_APPLY_DETAIL, REPEAT_DESTROY_DETAIL
from .deployment_routes.read import deployment_summary, canvas_deployment_history, get_deployment
from .deployment_routes.plans import create_plan_deployment, create_destroy_plan_deployment
from .deployment_routes.approval import approve_plan_deployment
from .deployment_routes.apply import create_apply_deployment
from .deployment_routes.destroy import create_destroy_deployment

router = APIRouter()
for module in (read, plans, approval, apply, destroy):
    router.include_router(module.router)
