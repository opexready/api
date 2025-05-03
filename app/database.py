from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

#Produccion
#DATABASE_URL_ASYNC = "postgresql+asyncpg://postgres:bbtpqLmIwPywDPsPyBkyKlnKwofAoIcD@ballast.proxy.rlwy.net:28910/railway"
# Usando la URL pública para la conexión
DATABASE_URL_ASYNC = "postgresql+asyncpg://postgres:TaAfBftyWBvbTabbIzzvFOPvToXmszym@autorack.proxy.rlwy.net:29750/railway"
#DATABASE_URL_ASYNC = "postgresql+asyncpg://postgres:LX125Uuisd@localhost:5432/bdRendicion"
# Crear el motor y la sesión de la base de datos
engine = create_async_engine(DATABASE_URL_ASYNC)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
Base = declarative_base()

async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        await db.close()
