from app.database import engine
from sqlalchemy import text

def test_connection():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT DATABASE();"))
            db_name = result.scalar()
            print(f"✅ Conexión exitosa a la base de datos: {db_name}")
    except Exception as e:
        print(f"❌ Error en la conexión: {e}")

if __name__ == "__main__":
    test_connection()

