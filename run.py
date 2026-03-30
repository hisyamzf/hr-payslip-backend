"""
FastAPI Server untuk HR Payslip System
Manage server startup, routing, middleware configuration
"""

import logging
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import routers
from app.api.v1 import payslips, uploads, contracts, auth, users, companies, employees


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("🚀 HR Payslip API starting...")
    yield
    logger.info("🛑 HR Payslip API shutting down...")


app = FastAPI(
    title="HR Payslip API",
    description="Multi-tenant HR Payslip Management System",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(companies.router)
app.include_router(payslips.router)
app.include_router(uploads.router)
app.include_router(contracts.router)
app.include_router(employees.router)

# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "HR Payslip API",
        "version": "1.0.0"
    }

# Root endpoint
@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "HR Payslip API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "auth": {
                "request_otp": "POST /api/v1/auth/request-otp",
                "verify_otp": "POST /api/v1/auth/verify-otp",
                "refresh": "POST /api/v1/auth/refresh",
                "me": "GET /api/v1/auth/me",
                "logout": "POST /api/v1/auth/logout"
            },
            "payslips": "/api/v1/payslips/*",
            "uploads": "/api/v1/companies/{company_id}/payslips/uploads/*",
            "contracts": "/api/v1/companies/{company_id}/contracts/*"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting FastAPI server...")
    uvicorn.run(
        "run:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
