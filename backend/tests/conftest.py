import json
import os
import time
from collections.abc import AsyncIterator

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


def _test_database_url() -> str:
    """Never reuse the runtime database: the schema here is dropped and recreated.

    TEST_DATABASE_URL wins if set; otherwise the runtime URL is reused with a
    "_test" suffix on the database name.
    """
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit

    runtime = os.environ.get("DATABASE_URL", "postgresql+asyncpg://peach:peach@db:5432/peach")
    base, _, database = runtime.rpartition("/")
    return f"{base}/{database}_test"


os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = _test_database_url()

from app.auth import get_verifier  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import Base, get_session  # noqa: E402
from app.main import create_app  # noqa: E402


async def _ensure_test_database(url: str) -> None:
    """Create the test database if it is not there yet."""
    from sqlalchemy import text

    database = url.rsplit("/", 1)[-1]
    admin_url = url.rsplit("/", 1)[0] + "/postgres"
    admin = create_async_engine(admin_url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": database}
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{database}"'))
    finally:
        await admin.dispose()


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator:
    url = os.environ["DATABASE_URL"]
    await _ensure_test_database(url)
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    """One connection per test, wrapped in a transaction that is always rolled back."""
    connection = await engine.connect()
    transaction = await connection.begin()
    factory = async_sessionmaker(bind=connection, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
    await transaction.rollback()
    await connection.close()


@pytest.fixture
def tokens(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    public.update(kid="test-key", alg="RS256", use="sig")
    monkeypatch.setenv(
        "COGNITO_AUTHORITY", "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST"
    )
    monkeypatch.setenv("COGNITO_CLIENT_ID", "test-client")
    monkeypatch.setenv("COGNITO_JWKS_JSON", json.dumps({"keys": [public]}))
    get_settings.cache_clear()
    get_verifier.cache_clear()

    def sign(sub="user-a", changes=None, remove=(), key=None, headers=None):
        claims = {
            "sub": sub,
            "iss": get_settings().cognito_authority,
            "client_id": "test-client",
            "token_use": "access",
            "exp": int(time.time()) + 3600,
        }
        claims.update(changes or {})
        for claim in remove:
            claims.pop(claim, None)
        return jwt.encode(
            claims, key or private, algorithm="RS256", headers=headers or {"kid": "test-key"}
        )

    yield sign
    get_verifier.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
async def client(session: AsyncSession, tokens) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def _override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"Authorization": "Bearer " + tokens()}
    ) as client:
        yield client
    app.dependency_overrides.clear()
