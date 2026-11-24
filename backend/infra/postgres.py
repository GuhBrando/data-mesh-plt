import asyncpg

from backend.infra.config import (
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_SSL_MODE,
    DB_USER,
)


async def connect() -> asyncpg.Connection:
    """A connection with the application's settings; the caller closes it."""
    return await asyncpg.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        host=DB_HOST,
        port=DB_PORT,
        ssl=DB_SSL_MODE if DB_SSL_MODE != "disable" else False,
    )


async def get_db_connection():
    """
    FastAPI dependency that yields a database connection
    and closes it after the request.
    """
    conn = await connect()
    try:
        yield conn
    finally:
        await conn.close()
