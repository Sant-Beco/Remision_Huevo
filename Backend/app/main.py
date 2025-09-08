from fastapi import FastAPI
from .routers import remisiones, modulos, galpones
from .database import Base, engine

# Crear tablas en la BD
Base.metadata.create_all(bind=engine)

app = FastAPI(title="🥚 API Remisión de Huevo")

# Rutas
app.include_router(remisiones.router)
app.include_router(modulos.router)
app.include_router(galpones.router)

@app.get("/")
def root():
    return {"message": "🚀 API de remisiones funcionando"}
