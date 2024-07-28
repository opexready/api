# app/database.py

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL_ASYNC = "postgresql+asyncpg://postgres:LX125Uuisd@localhost:5432/bdRendicion"

engine = create_async_engine(DATABASE_URL_ASYNC)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
Base = declarative_base()
