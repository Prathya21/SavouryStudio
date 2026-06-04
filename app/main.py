from fastapi import FastAPI
from app.api.routes import router
from app.core.logging_config import logger

app = FastAPI(
    title="SavouryStudio API",
    version="1.0.0"
)

app.include_router(router)

@app.on_event("startup")
async def startup_event():
    logger.info("SavouryStudio API started")

@app.get("/")
def root():
    logger.info("Root endpoint accessed")

    return {
        "message": "Welcome to SavouryStudio API"
    }