from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.auth import router as auth_router
from app.api.wallets import router as wallets_router
from app.api.transactions import router as transactions_router
from app.database.session import engine


app = FastAPI(
    title="Digital Wallet & Transaction Processing Platform",
    description=(
        "A backend API for secure wallets, payments, "
        "and transaction processing."
    ),
    version="1.0.0",
)

# Register API routers
app.include_router(auth_router)
app.include_router(wallets_router)
app.include_router(transactions_router)


@app.get("/", tags=["Health"])
def root():
    return {
        "success": True,
        "message": "Digital Wallet API is running",
    }


@app.get("/health", tags=["Health"])
def health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "success": True,
            "database": "connected",
        }

    except SQLAlchemyError:
        return {
            "success": False,
            "database": "disconnected",
        }