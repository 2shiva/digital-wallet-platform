
from decimal import Decimal

from sqlalchemy import select

from app.models import Transaction, TransferRequest, Wallet


def test_transfer_same_idempotency_key_returns_original_result(
    client,
    test_db,
):
    """An identical retry must not transfer money a second time."""

    idempotency_key = "transfer-test-key-0001"
    headers = {"Idempotency-Key": idempotency_key}
    payload = {
        "recipient_user_id": 2,
        "amount": "10.00",
        "description": "Idempotency API test",
    }

    first_response = client.post(
        "/transactions/transfer",
        json=payload,
        headers=headers,
    )

    assert first_response.status_code == 201, first_response.text
    first_result = first_response.json()
    assert len(first_result) == 2

    retry_response = client.post(
        "/transactions/transfer",
        json=payload,
        headers=headers,
    )

    assert retry_response.status_code == 201, retry_response.text
    retry_result = retry_response.json()

    # Both requests must return the same transactions.
    assert retry_result == first_result

    test_db.expire_all()

    sender_wallet = test_db.scalar(
        select(Wallet).where(Wallet.user_id == 1)
    )
    recipient_wallet = test_db.scalar(
        select(Wallet).where(Wallet.user_id == 2)
    )

    assert sender_wallet.balance == Decimal("90.00")
    assert recipient_wallet.balance == Decimal("35.00")

    transfer_request = test_db.scalar(
        select(TransferRequest).where(
            TransferRequest.user_id == 1,
            TransferRequest.idempotency_key == idempotency_key,
        )
    )

    assert transfer_request is not None

    transactions = test_db.scalars(
        select(Transaction).where(
            Transaction.reference.in_(
                [
                    f"{transfer_request.transfer_reference}-OUT",
                    f"{transfer_request.transfer_reference}-IN",
                ]
            )
        )
    ).all()

    assert len(transactions) == 2


def test_transfer_same_key_with_different_payload_returns_conflict(
    client,
    test_db,
):
    """Reusing a key for different transfer data must return HTTP 409."""

    idempotency_key = "transfer-test-key-0002"
    headers = {"Idempotency-Key": idempotency_key}

    first_response = client.post(
        "/transactions/transfer",
        json={
            "recipient_user_id": 2,
            "amount": "10.00",
            "description": "Original transfer",
        },
        headers=headers,
    )

    assert first_response.status_code == 201, first_response.text

    conflict_response = client.post(
        "/transactions/transfer",
        json={
            "recipient_user_id": 2,
            "amount": "20.00",
            "description": "Different transfer",
        },
        headers=headers,
    )

    assert conflict_response.status_code == 409, conflict_response.text

    test_db.expire_all()

    sender_wallet = test_db.scalar(
        select(Wallet).where(Wallet.user_id == 1)
    )
    recipient_wallet = test_db.scalar(
        select(Wallet).where(Wallet.user_id == 2)
    )

    # Only the original transfer should affect the balances.
    assert sender_wallet.balance == Decimal("90.00")
    assert recipient_wallet.balance == Decimal("35.00")

    transfer_request = test_db.scalar(
        select(TransferRequest).where(
            TransferRequest.user_id == 1,
            TransferRequest.idempotency_key == idempotency_key,
        )
    )

    assert transfer_request is not None

    transactions = test_db.scalars(
        select(Transaction).where(
            Transaction.reference.in_(
                [
                    f"{transfer_request.transfer_reference}-OUT",
                    f"{transfer_request.transfer_reference}-IN",
                ]
            )
        )
    ).all()

    assert len(transactions) == 2
