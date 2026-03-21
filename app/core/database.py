from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables and seed default admin user."""
    from app.models import user, document, course  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_default_users()


async def _seed_default_users():
    from app.models.user import User
    from app.core.security import hash_password
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == "admin@company.com"))
        if result.scalar_one_or_none():
            return  # already seeded

        users = [
            User(
                email="admin@company.com",
                full_name="Администратор",
                password_hash=hash_password("admin123"),
                role="admin",
            ),
            User(
                email="hr@company.com",
                full_name="HR Менеджер",
                password_hash=hash_password("hr123"),
                role="hr",
            ),
            User(
                email="user@company.com",
                full_name="Иван Петров",
                password_hash=hash_password("user123"),
                role="employee",
            ),
        ]
        db.add_all(users)
        await db.commit()
        print("✅ Default users seeded")
        print("   admin@company.com / admin123")
        print("   hr@company.com    / hr123")
        print("   user@company.com  / user123")
