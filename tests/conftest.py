
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_user
from app.database.session import Base, get_db
from app.main import app
from app.models import Role, Transaction, TransferRequest, User, Wallet


@pytest.fixture()
def test_db():
    """Create an isolated in-memory SQLite database for each test."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite does not support PostgreSQL's regular-expression operator.
    # Remove only that constraint from the temporary test schema.
    tables = Base.metadata.sorted_tables
    original_constraint = next(
        constraint
        for constraint in Wallet.__table__.constraints
        if constraint.name == "ck_wallets_currency_format"
    )

    Wallet.__table__.constraints.remove(original_constraint)

    try:
        Base.metadata.create_all(engine)
    finally:
        Wallet.__table__.constraints.add(original_constraint)

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    session = TestingSessionLocal()

    try:
        customer_role = Role(
            id=4,
            name="customer",
            description="Test customer",
        )
        session.add(customer_role)
        session.flush()

        sender = User(
            id=1,
            role_id=4,
            full_name="Test Sender",
            email="sender@example.test",
            hashed_password="not-used-in-these-tests",
            is_active=True,
        )
        recipient = User(
            id=2,
            role_id=4,
            full_name="Test Recipient",
            email="recipient@example.test",
            hashed_password="not-used-in-these-tests",
            is_active=True,
        )
        session.add_all([sender, recipient])
        session.flush()

        sender_wallet = Wallet(
            id=1,
            user_id=sender.id,
            balance=Decimal("100.00"),
            currency="INR",
            status="active",
        )
        recipient_wallet = Wallet(
            id=2,
            user_id=recipient.id,
            balance=Decimal("25.00"),
            currency="INR",
            status="active",
        )
        session.add_all([sender_wallet, recipient_wallet])
        session.commit()

        yield session

    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(test_db):
    """Provide a test client with database and authentication overrides."""

    def override_get_db():
        yield test_db

    def override_current_user():
        return test_db.get(User, 1)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def sender_wallet(test_db):
    return test_db.query(Wallet).filter_by(user_id=1).one()


@pytest.fixture()
def recipient_wallet(test_db):
    return test_db.query(Wallet).filter_by(user_id=2).one()
