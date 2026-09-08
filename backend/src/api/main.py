"""FastAPI application - Punto de entrada principal."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.rutas_grafo import router as grafo_router
from src.api.rutas_agente import router as agente_router
from src.api.rutas_busqueda import router as busqueda_router
from src.api.rutas_mapa import router as mapa_router
from src.utilidades.config import settings
from src.utilidades.logging import configurar_logging

# Configurar logging al inicio
configurar_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión de ciclo de vida de la aplicación."""
    # Startup
    print("Iniciando API TransMilenio...")
    yield
    # Shutdown
    print("Cerrando API TransMilenio...")


app = FastAPI(
    title="Sistema Inteligente Planificación Rutas TransMilenio",
    description="API para agente inteligente, grafo de movilidad y algoritmos de búsqueda",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS para frontend Nuxt
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3001", "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(grafo_router, prefix="/api/v1/grafo", tags=["Grafo"])
app.include_router(agente_router, prefix="/api/v1/agente", tags=["Agente"])
app.include_router(busqueda_router, prefix="/api/v1/busqueda", tags=["Busqueda"])
app.include_router(mapa_router, prefix="/api/v1/mapa", tags=["Mapa"])

# Health check
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "transmilenio-api"}

# Root
@app.get("/")
async def root():
    return {
        "mensaje": "Sistema Inteligente Planificación Rutas TransMilenio",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)