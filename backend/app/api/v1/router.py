from fastapi import APIRouter

from app.api.v1 import alerts, auth, health, imports, models, rules, scoring, transactions, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(transactions.router)
api_router.include_router(imports.router)
api_router.include_router(scoring.router)
api_router.include_router(alerts.router)
api_router.include_router(rules.router)
api_router.include_router(models.router)
