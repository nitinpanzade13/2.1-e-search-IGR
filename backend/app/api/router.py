from fastapi import APIRouter

from app.api.v1 import health, locations, village_fetch, records, network

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(locations.router, prefix="/locations", tags=["Locations"])
api_router.include_router(village_fetch.router)
api_router.include_router(records.router)
api_router.include_router(network.router, prefix="/network", tags=["Network Admin"])
