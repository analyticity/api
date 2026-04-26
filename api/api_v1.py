from fastapi import APIRouter
# from modules.admin.router import router as admin_router
from modules.map.router import router as map_router
from modules.contact.router import router as contact_router
# from modules.chart.router import router as chart_router

api_router = APIRouter()

# api_router.include_router(admin_router, prefix="/admin", tags=["admin"])
api_router.include_router(map_router, prefix="/map", tags=["map"])
api_router.include_router(contact_router, prefix="/contact", tags=["contact"])
# api_router.include_router(chart_router, prefix="/charts", tags=["charts"])