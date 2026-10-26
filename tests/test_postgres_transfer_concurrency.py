
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.main import app
from app.models import Transaction, TransferRequest, User, Wallet

# Import the fixtures from the existing PostgreSQL integration test module.
from tests.test_postgres_integration import (
    postgres_engine,
    postgres_session,
)


@pytest.fixture()
def postgres_api(postgres_engine, postgres_session):
    """Provide API access using independent PostgreSQL sessions."""

    session_factory = sessionmaker(
        bind=postgres_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    sender_id = postgres_session["sender"].id
    recipient_id = postgres_session["recipient"].id

    def override_get_db():
        with session_factory() as session:
            yield session

    def authenticated_test_user(db: Session = Depends(get_db)):
        user = db.scalar(
            select(User).where(User.id == sender_id)
        )
        if user is None:
            raise RuntimeError("PostgreSQL test sender was not found.")
        return user

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = authenticated_test_user

    try:
        with TestClient(app) as client:
            yield {
                "client": client,
                "session_factory": session_factory,
                "sender_id": sender_id,
                "recipient_id": recipient_id,
            }
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


def run_concurrently(client, requests):
    """Send requests together using separate worker threads."""

    barrier = Barrier(len(requests))

    def send_request(payload, key):
        barrier.wait(timeout=10)
        return client.post(
            "/transactions/transfer",
            json=payload,
            headers={"Idempotency-Key": key},
        )

    with ThreadPoolExecutor(max_workers=len(requests)) as executor:
        futures = [
            executor.submit(send_request, payload, key)
            for payload, key in requests
        ]
        return [future.result(timeout=30) for future in futures]


def read_wallet_balances(session_factory, sender_id, recipient_id):
    """Read balances from a fresh PostgreSQL session."""

    with session_factory() as session:
        sender_wallet = session.scalar(
            select(Wallet).where(Wallet.user_id == sender_id)
        )
        recipient_wallet = session.scalar(
            select(Wallet).where(Wallet.user_id == recipient_id)
        )

        assert sender_wallet is not None
        assert recipient_wallet is not None

        return sender_wallet.balance, recipient_wallet.balance


def test_concurrent_identical_transfers_are_applied_once(postgres_api):
    """Concurrent identical retries must create only one transfer."""

    client = postgres_api["client"]
    session_factory = postgres_api["session_factory"]
    sender_id = postgres_api["sender_id"]
    recipient_id = postgres_api["recipient_id"]

    key = f"pg-concurrent-same-{uuid4().hex}"
    payload = {
        "recipient_user_id": recipient_id,
        "amount": "10.00",
        "description": "Concurrent idempotency test",
    }

    responses = run_concurrently(
        client,
        [(payload, key), (payload, key)],
    )

    assert all(response.status_code == 201 for response in responses), [
        (response.status_code, response.text)
        for response in responses
    ]
    assert responses[0].json() == responses[1].json()
    assert len(responses[0].json()) == 2

    sender_balance, recipient_balance = read_wallet_balances(
        session_factory, sender_id, recipient_id
    )
    assert sender_balance == Decimal("90.00")
    assert recipient_balance == Decimal("35.00")

    with session_factory() as session:
        requests_count = session.scalar(
            select(func.count())
            .select_from(TransferRequest)
            .where(
                TransferRequest.user_id == sender_id,
                TransferRequest.idempotency_key == key,
            )
        )
        assert requests_count == 1

        transfer_reference = session.scalar(
            select(TransferRequest.transfer_reference).where(
                TransferRequest.user_id == sender_id,
                TransferRequest.idempotency_key == key,
            )
        )
        assert transfer_reference is not None

        transaction_count = session.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(
                Transaction.reference.in_(
                    [
                        f"{transfer_reference}-OUT",
                        f"{transfer_reference}-IN",
                    ]
                )
            )
        )
        assert transaction_count == 2


def test_concurrent_transfers_cannot_overspend_wallet(postgres_api):
    """Two concurrent ₹70 transfers cannot overspend a ₹100 wallet."""

    client = postgres_api["client"]
    session_factory = postgres_api["session_factory"]
    sender_id = postgres_api["sender_id"]
    recipient_id = postgres_api["recipient_id"]

    requests = [
        (
            {
                "recipient_user_id": recipient_id,
                "amount": "70.00",
                "description": "Concurrent overspend test A",
            },
            f"pg-overspend-a-{uuid4().hex}",
        ),
        (
            {
                "recipient_user_id": recipient_id,
                "amount": "70.00",
                "description": "Concurrent overspend test B",
            },
            f"pg-overspend-b-{uuid4().hex}",
        ),
    ]

    responses = run_concurrently(client, requests)

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [201, 400], [
        (response.status_code, response.text)
        for response in responses
    ]

    sender_balance, recipient_balance = read_wallet_balances(
        session_factory, sender_id, recipient_id
    )
    assert sender_balance == Decimal("30.00")
    assert recipient_balance == Decimal("95.00")

    with session_factory() as session:
        sender_wallet_id = session.scalar(
            select(Wallet.id).where(Wallet.user_id == sender_id)
        )

        completed_debits = session.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(
                Transaction.wallet_id == sender_wallet_id,
                Transaction.transaction_type == "transfer",
                Transaction.status == "completed",
                Transaction.description.in_(
                    [
                        "Concurrent overspend test A",
                        "Concurrent overspend test B",
                    ]
                ),
            )
        )

        assert completed_debits == 1
