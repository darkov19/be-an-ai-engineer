import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

@pytest.fixture
def app():
    # Import main FastAPI application
    from backend.main import app as real_app
    yield real_app
    # Teardown: reset pool state to prevent inter-test pollution.
    # Tests share a singleton app object; without this reset, a mock pool
    # set by one test may leak into the next.
    if hasattr(real_app.state, "pool"):
        real_app.state.pool = None

@pytest_asyncio.fixture
async def client(app):
    # Setup HTTPX AsyncClient with ASGI transport to run integration tests locally without network sockets
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac
