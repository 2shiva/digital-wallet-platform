
import os

import pytest
from sqlalchemy.engine import make_url


def get_postgres_test_url() -> str:
    """Return the URL only when it targets the dedicated test database."""

    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url:
        pytest.skip(
            "PostgreSQL integration tests skipped: "
            "TEST_DATABASE_URL is not configured."
        )

    try:
        parsed_url = make_url(database_url)
    except Exception as exc:
        pytest.fail(f"TEST_DATABASE_URL is invalid: {exc}")

    if not parsed_url.drivername.startswith("postgresql"):
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL.")

    if parsed_url.database != "digital_wallet_test_db":
        pytest.fail(
            "Refusing to run PostgreSQL tests: the database must be "
            "digital_wallet_test_db."
        )

    return database_url
