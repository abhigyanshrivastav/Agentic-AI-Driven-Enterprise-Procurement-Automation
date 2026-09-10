from fastapi import FastAPI
from src.api.routes import router
from src.config import get_app_yaml_config

config = get_app_yaml_config()
app_info = config.get("app", {})

app = FastAPI(
    title=app_info.get("name", "Enterprise Procurement LLMOps Prototype"),
    version=app_info.get("version", "1.0.0"),
    description="Integrated Reference Architecture & Controlled E0–E3 Benchmark Prototype"
)

app.include_router(router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "name": app.title,
        "version": app.version,
        "docs": "/docs",
        "health": "/api/v1/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=8000, reload=True)
