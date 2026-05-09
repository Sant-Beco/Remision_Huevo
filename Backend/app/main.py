# app/main.py
"""
Punto de entrada de la API Incubant.

Características:
  - Lifespan: verifica conexión a PostgreSQL al arrancar.
  - Routers versionados bajo /api/v1/
  - CORS configurado para la PWA React (dev y producción).
  - Middleware de logging con loguru.
  - Documentación automática en /docs (Swagger) y /redoc.
  - Health check en / y /health.
"""
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import verificar_conexion

# ── Importar routers (están en app/api/v1/) ──────────────────────────────────
# Una vez que renombres routers/ → api/v1/, usa estas importaciones:
#
#   from app.api.v1 import remisiones, modulos, galpones
#
# Mientras tanto, si todavía tienes la carpeta como routers/:
from app.routers import remisiones, modulos, galpones, granjas


# ─────────────────────────────────────────
# Lifespan (reemplaza @app.on_event deprecated)
# ─────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Código que corre al INICIAR y al DETENER la aplicación.
    Al iniciar: verifica la conexión a PostgreSQL.
    Al detener: limpieza (futuro: cerrar conexiones async, etc.)
    """
    # ── Startup ──
    print("🚀 Iniciando Incubant API...")
    try:
        verificar_conexion()
    except Exception as e:
        print(f"💥 No se pudo conectar a la base de datos: {e}")
        raise

    print("✅ API lista")
    yield

    # ── Shutdown ──
    print("🛑 Apagando Incubant API...")


# ─────────────────────────────────────────
# Aplicación FastAPI
# ─────────────────────────────────────────

app = FastAPI(
    title="Incubant API",
    description=(
        "Sistema de Remisión de Huevo — Antioqueña de Incubación S.A.S.\n\n"
        "Digitalización del flujo de papel/Excel a PWA con soporte offline."
    ),
    version="0.2.0",
    docs_url="/docs",        # Swagger UI
    redoc_url="/redoc",      # ReDoc
    lifespan=lifespan,
    debug=os.getenv("DEBUG", "false").lower() == "true",
)


# ─────────────────────────────────────────
# CORS — permite peticiones desde la PWA React
# ─────────────────────────────────────────

# En producción reemplaza "*" con el dominio real de Hostinger
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000"   # Vite dev + CRA dev
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────
# Middleware de logging de requests
# ─────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Registra método, path y tiempo de respuesta de cada request.
    En producción esto se complementa con loguru (app/core/logging.py).
    """
    start = time.perf_counter()
    response = await call_next(request)
    duration = (time.perf_counter() - start) * 1000
    print(
        f"  {request.method} {request.url.path} "
        f"→ {response.status_code} ({duration:.1f}ms)"
    )
    return response


# ─────────────────────────────────────────
# Health checks
# ─────────────────────────────────────────

@app.get("/", tags=["health"], summary="Raíz — estado de la API")
def root():
    return {
        "app":     "Incubant API",
        "version": "0.2.0",
        "estado":  "activo",
        "docs":    "/docs",
    }


@app.get("/health", tags=["health"], summary="Health check para Docker / balanceador")
def health_check():
    """
    Endpoint que usan Docker Compose y el balanceador de Hostinger
    para verificar que la aplicación está viva.
    Retorna 200 si todo está bien.
    """
    try:
        verificar_conexion()
        return {"status": "ok", "db": "conectada"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "db": str(e)},
        )


# ─────────────────────────────────────────
# Routers versionados
# ─────────────────────────────────────────
#
# Prefijo /api/v1 en TODOS los routers.
# Cuando el router propio ya tiene prefix="/remisiones",
# la ruta final queda: /api/v1/remisiones/
#
# ── Estructura actual (routers/) ──
app.include_router(remisiones.router, prefix="/api/v1")
app.include_router(modulos.router,    prefix="/api/v1")
app.include_router(galpones.router,   prefix="/api/v1")
app.include_router(granjas.router, prefix="/api/v1")

#
# ── Una vez que tengas api/v1/, reemplaza por: ──
#
# from app.api.v1 import remisiones, modulos, galpones, lotes, users, sync
# app.include_router(remisiones.router, prefix="/api/v1", tags=["remisiones"])
# app.include_router(modulos.router,    prefix="/api/v1", tags=["modulos"])
# app.include_router(galpones.router,   prefix="/api/v1", tags=["galpones"])
# app.include_router(lotes.router,      prefix="/api/v1", tags=["lotes"])
# app.include_router(users.router,      prefix="/api/v1", tags=["usuarios"])
# app.include_router(sync.router,       prefix="/api/v1", tags=["sync"])
#