# app/database.py
"""
Configuración de la conexión a PostgreSQL.

Stack definitivo:
  - PostgreSQL 15+
  - SQLAlchemy 2.0 (estilo moderno con select(), Session, etc.)
  - psycopg2 como driver (síncrono — compatible con FastAPI estándar)
  - Alembic para migraciones (reemplaza create_all en producción)

Variables de entorno requeridas en .env:
  DB_USER       → usuario de PostgreSQL
  DB_PASSWORD   → contraseña
  DB_HOST       → host (localhost en dev, nombre del servicio en Docker)
  DB_PORT       → puerto (default 5432)
  DB_NAME       → nombre de la base de datos

Ejemplo .env:
  DB_USER=incubant_user
  DB_PASSWORD=supersecreta
  DB_HOST=localhost
  DB_PORT=5432
  DB_NAME=incubantdb
"""
import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

# ─────────────────────────────────────────
# Parámetros de conexión desde .env
# ─────────────────────────────────────────

DB_USER     = os.getenv("DB_USER",     "incubant_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST     = os.getenv("DB_HOST",     "localhost")
DB_PORT     = os.getenv("DB_PORT",     "5432")
DB_NAME     = os.getenv("DB_NAME",     "incubantdb")

# URL de conexión PostgreSQL (psycopg2 síncrono)
DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ─────────────────────────────────────────
# Engine
# ─────────────────────────────────────────

engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("DB_ECHO", "false").lower() == "true",  # True solo en desarrollo
    pool_pre_ping=True,       # Verifica la conexión antes de usarla (evita conexiones muertas)
    pool_size=10,             # Conexiones permanentes en el pool
    max_overflow=20,          # Conexiones extra permitidas bajo carga alta
    pool_recycle=1800,        # Recicla conexiones cada 30 min (evita timeouts de PostgreSQL)
    connect_args={
        "options": "-c timezone=UTC"  # Todas las sesiones en UTC
    },
)

# ─────────────────────────────────────────
# Session factory
# ─────────────────────────────────────────

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,   # Evita queries innecesarias después del commit
)

# ─────────────────────────────────────────
# Dependencia FastAPI — get_db()
# ─────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    """
    Dependencia inyectable en cada endpoint.
    Garantiza que la sesión se cierre siempre,
    incluso si ocurre una excepción en el endpoint.

    Uso en router:
        @router.get("/")
        def list_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ─────────────────────────────────────────
# Utilidad de verificación de conexión
# ─────────────────────────────────────────

def verificar_conexion() -> bool:
    """
    Verifica que la conexión a PostgreSQL funciona.
    Se llama al iniciar la aplicación (en main.py lifespan).
    Retorna True si OK, lanza excepción si falla.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database(), version()"))
            row = result.fetchone()
            print(f"✅ PostgreSQL conectado — DB: {row[0]}")
            print(f"   {row[1][:60]}...")
        return True
    except Exception as e:
        print(f"❌ Error de conexión a PostgreSQL: {e}")
        raise