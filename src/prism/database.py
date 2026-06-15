from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from prism.config import settings

engine = create_async_engine(settings.database_url)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
