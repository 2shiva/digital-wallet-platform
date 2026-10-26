
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.models import Role, Transaction, TransferRequest, User, Wallet
from tests.postgres_test_config import get_postgres_test_url


@pytest.fixture(scope="module")
def postgres_engine():
    """Connect only to the dedicated PostgreSQL test database."""

    database_url = get_postgres_test_url()
    engine = create_engine(database_url, poolclass=NullPool)

    try:
        with engine.connect() as connection:
            database_name = connection.scalar(
                text("SELECT current_database()")
            )

        if database_name != "digital_wallet_test_db":
            pytest.fail(
                "Safety check failed: connected to an unexpected database."
            )

        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def postgres_session(postgres_engine):
    """Create uniquely identified test records and remove them afterward."""

    TestingSessionLocal = sessionmaker(
        bind=postgres_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    suffix = uuid4().hex
    sender_email = f"pg-sender-{suffix}@example.com"
    recipient_email = f"pg-recipient-{suffix}@example.com"
    idempotency_key = f"pg-test-{suffix}"

    with TestingSessionLocal() as session:
        try:
            role = session.scalar(
                select(Role).where(Role.name == "customer")
            )

            if role is None:
                role = Role(
                    name="customer",
                    description="Customer",
                )
                session.add(role)
                session.flush()

            sender = User(
                full_name="Postgres Test Sender",
                email=sender_email,
                hashed_password="not-used-in-tests",
                is_active=True,
                role_id=role.id,
            )
            recipient = User(
                full_name="Postgres Test Recipient",
                email=recipient_email,
                hashed_password="not-used-in-tests",
                is_active=True,
                role_id=role.id,
            )
            session.add_all([sender, recipient])
            session.flush()

            sender_wallet = Wallet(
                user_id=sender.id,
                balance=Decimal("100.00"),
                currency="INR",
                status="active",
            )
            recipient_wallet = Wallet(
                user_id=recipient.id,
                balance=Decimal("25.00"),
                currency="INR",
                status="active",
            )
            session.add_all([sender_wallet, recipient_wallet])
            session.commit()

            yield {
                "session": session,
                "sender": sender,
                "recipient": recipient,
                "sender_wallet": sender_wallet,
                "recipient_wallet": recipient_wallet,
                "idempotency_key": idempotency_key,
            }

        finally:
            session.rollback()

            # Delete only records created by this fixture.
            sender = session.scalar(
                select(User).where(User.email == sender_email)
            )
            recipient = session.scalar(
                select(User).where(User.email == recipient_email)
            )

            user_ids = [
                user.id
                for user in (sender, recipient)
                if user is not None
            ]

            if user_ids:
                wallet_ids = list(
                    session.scalars(
                        select(Wallet.id).where(
                            Wallet.user_id.in_(user_ids)
                        )
                    ).all()
                )

                if wallet_ids:
                    session.query(Transaction).filter(
                        Transaction.wallet_id.in_(wallet_ids)
                    ).delete(synchronize_session=False)

                session.query(TransferRequest).filter(
                    TransferRequest.user_id.in_(user_ids)
                ).delete(synchronize_session=False)

                session.query(Wallet).filter(
                    Wallet.user_id.in_(user_ids)
                ).delete(synchronize_session=False)

                session.query(User).filter(
                    User.id.in_(user_ids)
                ).delete(synchronize_session=False)

                session.commit()


def test_postgres_database_is_the_dedicated_test_database(
    postgres_engine,
):
    with postgres_engine.connect() as connection:
        assert connection.scalar(
            text("SELECT current_database()")
        ) == "digital_wallet_test_db"


def test_postgres_wallet_balance_constraint(postgres_engine):
    """PostgreSQL itself must reject a negative wallet balance."""

    with postgres_engine.begin() as connection:
        with pytest.raises(Exception):
            connection.execute(
                text(
                    """
                    INSERT INTO wallets (user_id, balance, currency, status)
                    VALUES (-987654321, -1.00, 'INR', 'active')
                    """
                )
            )


def test_postgres_transaction_amount_constraint(
    postgres_session,
):
    """A transaction amount must be positive."""

    session = postgres_session["session"]
    wallet = postgres_session["sender_wallet"]

    transaction = Transaction(
        wallet_id=wallet.id,
        transaction_type="deposit",
        amount=Decimal("-1.00"),
        currency="INR",
        status="completed",
        reference=f"PG-NEG-{uuid4().hex}",
    )

    session.add(transaction)

    with pytest.raises(Exception):
        session.commit()

    session.rollback()


def test_postgres_transfer_request_idempotency_constraint(
    postgres_session,
):
    """The same user's idempotency key cannot be inserted twice."""

    session = postgres_session["session"]
    sender = postgres_session["sender"]
    key = postgres_session["idempotency_key"]

    session.add(
        TransferRequest(
            user_id=sender.id,
            idempotency_key=key,
            request_hash="a" * 64,
            transfer_reference=f"PG-REF-{uuid4().hex}",
        )
    )
    session.commit()

    session.add(
        TransferRequest(
            user_id=sender.id,
            idempotency_key=key,
            request_hash="b" * 64,
            transfer_reference=f"PG-REF-{uuid4().hex}",
        )
    )

    with pytest.raises(Exception):
        session.commit()

    session.rollback()
