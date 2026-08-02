import pytest
from fastapi.testclient import TestClient

from backend.agent.tools.tools import get_df, get_schema
from backend.api.main import app


@pytest.fixture(scope="session")
def df():
    return get_df()


@pytest.fixture(scope="session")
def schema():
    return get_schema()


@pytest.fixture(scope="session")
def client():
    # X-API-Key gets the higher rate-limit tier (100/min vs 10/min) — the test
    # suite alone makes more than 10 requests, and any non-empty value works.
    return TestClient(app, headers={"X-API-Key": "pytest-suite"})
