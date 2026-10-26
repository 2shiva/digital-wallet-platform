
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.database.session import get_db
from app.main import app
from app.models import User, Wallet


def create_test_client(test_db):
    """Use the isolated test database without bypassing JWT authentication."""

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_register_creates_customer_and_wallet(test_db):
    client = create_test_client(test_db)

    try:
        response = client.post(
            "/auth/register",
            json={
                "full_name": "New Customer",
                "email": "newcustomer@example.com",
                "password": "StrongPassword123!",
            },
        )

        assert response.status_code == 201, response.json()

        body = response.json()
        assert body["full_name"] == "New Customer"
        assert body["email"] == "newcustomer@example.com"
        assert body["is_active"] is True
        assert "hashed_password" not in body

        user = test_db.scalar(
            select(User).where(User.email == "newcustomer@example.com")
        )

        assert user is not None
        assert user.role_id == 4
        assert user.hashed_password != "StrongPassword123!"

        wallet = test_db.scalar(
            select(Wallet).where(Wallet.user_id == user.id)
        )

        assert wallet is not None
        assert wallet.balance == Decimal("0.00")
        assert wallet.currency == "INR"
        assert wallet.status == "active"

    finally:
        client.close()
        app.dependency_overrides.clear()


def test_register_rejects_duplicate_email(test_db):
    client = create_test_client(test_db)

    try:
        response = client.post(
            "/auth/register",
            json={
                "full_name": "Duplicate Sender",
                "email": "sender@example.com",
                "password": "StrongPassword123!",
            },
        )

        assert response.status_code == 409, response.json()

    finally:
        client.close()
        app.dependency_overrides.clear()


def test_register_rejects_short_password(test_db):
    client = create_test_client(test_db)

    try:
        response = client.post(
            "/auth/register",
            json={
                "full_name": "Short Password",
                "email": "shortpassword@example.com",
                "password": "short",
            },
        )

        assert response.status_code == 422, response.json()

    finally:
        client.close()
        app.dependency_overrides.clear()


def test_login_returns_valid_access_token(test_db):
    user = test_db.get(User, 1)
    assert user is not None

    user.hashed_password = hash_password("StrongPassword123!")
    test_db.commit()

    client = create_test_client(test_db)

    try:
        response = client.post(
            "/auth/login",
            json={
                "email": user.email,
                "password": "StrongPassword123!",
            },
        )

        assert response.status_code == 200, response.json()

        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]

        payload = jwt.decode(
            body["access_token"],
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )

        assert payload["sub"] == str(user.id)
        assert payload["role_id"] == user.role_id
        assert "exp" in payload

    finally:
        client.close()
        app.dependency_overrides.clear()


def test_login_rejects_wrong_password(test_db):
    user = test_db.get(User, 1)
    assert user is not None

    user.hashed_password = hash_password("CorrectPassword123!")
    test_db.commit()

    client = create_test_client(test_db)

    try:
        response = client.post(
            "/auth/login",
            json={
                "email": user.email,
                "password": "WrongPassword123!",
            },
        )

        assert response.status_code == 401, response.json()
        assert response.headers.get("www-authenticate") == "Bearer"

    finally:
        client.close()
        app.dependency_overrides.clear()


def test_login_rejects_inactive_user(test_db):
    user = test_db.get(User, 1)
    assert user is not None

    user.hashed_password = hash_password("StrongPassword123!")
    user.is_active = False
    test_db.commit()

    client = create_test_client(test_db)

    try:
        response = client.post(
            "/auth/login",
            json={
                "email": user.email,
                "password": "StrongPassword123!",
            },
        )

        assert response.status_code == 403, response.json()

    finally:
        client.close()
        app.dependency_overrides.clear()


def test_me_rejects_expired_token(test_db):
    now = datetime.now(timezone.utc)

    expired_token = jwt.encode(
        {
            "sub": "1",
            "role_id": 4,
            "iat": now - timedelta(minutes=10),
            "exp": now - timedelta(minutes=5),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )

    client = create_test_client(test_db)

    try:
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        assert response.status_code == 401, response.json()

    finally:
        client.close()
        app.dependency_overrides.clear()


def test_me_rejects_invalid_token(test_db):
    client = create_test_client(test_db)

    try:
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid.token.value"},
        )

        assert response.status_code == 401, response.json()

    finally:
        client.close()
        app.dependency_overrides.clear()


def test_me_rejects_inactive_user(test_db):
    user = test_db.get(User, 1)
    assert user is not None

    now = datetime.now(timezone.utc)

    token = jwt.encode(
        {
            "sub": str(user.id),
            "role_id": user.role_id,
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )

    user.is_active = False
    test_db.commit()

    client = create_test_client(test_db)

    try:
        response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401, response.json()

    finally:
        client.close()
        app.dependency_overrides.clear()
