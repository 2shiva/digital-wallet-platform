
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core.config import settings
from app.models import Transaction, TransferRequest, Wallet


TRANSFER_KEY = "automated-transfer-test-001"
WITHDRAWAL_KEY = "automated-withdrawal-test-001"


def test_transfer_creates_two_transactions_and_updates_balances(
    client,
    test_db,
):
    response = client.post(
        "/transactions/transfer",
        headers={"Idempotency-Key": TRANSFER_KEY},
        json={
            "recipient_user_id": 2,
            "amount": "10.00",
            "description": "Automated transfer",
        },
    )

    assert response.status_code == 201
    assert len(response.json()) == 2
    assert test_db.get(Wallet, 1).balance == Decimal("90.00")
    assert test_db.get(Wallet, 2).balance == Decimal("35.00")
    assert test_db.query(Transaction).count() == 2
    assert test_db.query(TransferRequest).count() == 1


def test_repeated_transfer_does_not_duplicate_transactions(
    client,
    test_db,
):
    payload = {
        "recipient_user_id": 2,
        "amount": "10.00",
        "description": "Automated transfer",
    }
    headers = {"Idempotency-Key": TRANSFER_KEY}

    first_response = client.post(
        "/transactions/transfer",
        headers=headers,
        json=payload,
    )
    second_response = client.post(
        "/transactions/transfer",
        headers=headers,
        json=payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert [item["id"] for item in first_response.json()] == [
        item["id"] for item in second_response.json()
    ]
    assert test_db.query(Transaction).count() == 2
    assert test_db.query(TransferRequest).count() == 1
    assert test_db.get(Wallet, 1).balance == Decimal("90.00")
    assert test_db.get(Wallet, 2).balance == Decimal("35.00")


def test_transfer_rejects_reused_key_with_different_amount(
    client,
    test_db,
):
    headers = {"Idempotency-Key": TRANSFER_KEY}

    first_response = client.post(
        "/transactions/transfer",
        headers=headers,
        json={
            "recipient_user_id": 2,
            "amount": "10.00",
            "description": "Automated transfer",
        },
    )
    conflicting_response = client.post(
        "/transactions/transfer",
        headers=headers,
        json={
            "recipient_user_id": 2,
            "amount": "11.00",
            "description": "Automated transfer",
        },
    )

    assert first_response.status_code == 201
    assert conflicting_response.status_code == 409
    assert test_db.query(Transaction).count() == 2
    assert test_db.get(Wallet, 1).balance == Decimal("90.00")
    assert test_db.get(Wallet, 2).balance == Decimal("35.00")


def test_transfer_rejects_reused_key_with_different_recipient(
    client,
    test_db,
):
    headers = {"Idempotency-Key": TRANSFER_KEY}

    first_response = client.post(
        "/transactions/transfer",
        headers=headers,
        json={
            "recipient_user_id": 2,
            "amount": "10.00",
            "description": "Automated transfer",
        },
    )
    conflicting_response = client.post(
        "/transactions/transfer",
        headers=headers,
        json={
            "recipient_user_id": 3,
            "amount": "10.00",
            "description": "Automated transfer",
        },
    )

    assert first_response.status_code == 201
    assert conflicting_response.status_code == 409
    assert test_db.query(Transaction).count() == 2
    assert test_db.query(TransferRequest).count() == 1
    assert test_db.get(Wallet, 1).balance == Decimal("90.00")
    assert test_db.get(Wallet, 2).balance == Decimal("35.00")


def test_transfer_rejects_reused_key_with_different_description(
    client,
    test_db,
):
    headers = {"Idempotency-Key": TRANSFER_KEY}

    first_response = client.post(
        "/transactions/transfer",
        headers=headers,
        json={
            "recipient_user_id": 2,
            "amount": "10.00",
            "description": "First description",
        },
    )
    conflicting_response = client.post(
        "/transactions/transfer",
        headers=headers,
        json={
            "recipient_user_id": 2,
            "amount": "10.00",
            "description": "Different description",
        },
    )

    assert first_response.status_code == 201
    assert conflicting_response.status_code == 409
    assert test_db.query(Transaction).count() == 2
    assert test_db.query(TransferRequest).count() == 1
    assert test_db.get(Wallet, 1).balance == Decimal("90.00")


def test_withdrawal_creates_one_transaction_and_updates_balance(
    client,
    test_db,
):
    response = client.post(
        "/transactions/withdraw",
        headers={"Idempotency-Key": WITHDRAWAL_KEY},
        json={
            "amount": "20.00",
            "description": "Automated withdrawal",
        },
    )

    assert response.status_code == 201
    transaction = response.json()

    assert transaction["transaction_type"] == "withdrawal"
    assert transaction["amount"] == "20.00"
    assert test_db.get(Wallet, 1).balance == Decimal("80.00")
    assert test_db.query(Transaction).count() == 1
    assert test_db.query(TransferRequest).count() == 1


def test_repeated_withdrawal_does_not_deduct_balance_twice(
    client,
    test_db,
):
    payload = {
        "amount": "20.00",
        "description": "Automated withdrawal",
    }
    headers = {"Idempotency-Key": WITHDRAWAL_KEY}

    first_response = client.post(
        "/transactions/withdraw",
        headers=headers,
        json=payload,
    )
    second_response = client.post(
        "/transactions/withdraw",
        headers=headers,
        json=payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["id"] == second_response.json()["id"]
    assert test_db.query(Transaction).count() == 1
    assert test_db.query(TransferRequest).count() == 1
    assert test_db.get(Wallet, 1).balance == Decimal("80.00")


def test_withdrawal_rejects_reused_key_with_different_amount(
    client,
    test_db,
):
    headers = {"Idempotency-Key": WITHDRAWAL_KEY}

    first_response = client.post(
        "/transactions/withdraw",
        headers=headers,
        json={
            "amount": "20.00",
            "description": "Automated withdrawal",
        },
    )
    conflicting_response = client.post(
        "/transactions/withdraw",
        headers=headers,
        json={
            "amount": "21.00",
            "description": "Automated withdrawal",
        },
    )

    assert first_response.status_code == 201
    assert conflicting_response.status_code == 409
    assert test_db.query(Transaction).count() == 1
    assert test_db.get(Wallet, 1).balance == Decimal("80.00")


def test_idempotency_key_cannot_be_reused_for_different_operation(
    client,
    test_db,
):
    shared_key = "shared-operation-key-001"

    transfer_response = client.post(
        "/transactions/transfer",
        headers={"Idempotency-Key": shared_key},
        json={
            "recipient_user_id": 2,
            "amount": "10.00",
            "description": "Operation conflict test",
        },
    )
    withdrawal_response = client.post(
        "/transactions/withdraw",
        headers={"Idempotency-Key": shared_key},
        json={
            "amount": "10.00",
            "description": "Operation conflict test",
        },
    )

    assert transfer_response.status_code == 201
    assert withdrawal_response.status_code == 409
    assert test_db.query(Transaction).count() == 2
    assert test_db.query(TransferRequest).count() == 1
    assert test_db.get(Wallet, 1).balance == Decimal("90.00")
    assert test_db.get(Wallet, 2).balance == Decimal("35.00")


def test_transfer_requires_idempotency_key(client, test_db):
    response = client.post(
        "/transactions/transfer",
        json={
            "recipient_user_id": 2,
            "amount": "10.00",
            "description": "Missing key test",
        },
    )

    assert response.status_code == 422
    assert test_db.query(Transaction).count() == 0
    assert test_db.query(TransferRequest).count() == 0
    assert test_db.get(Wallet, 1).balance == Decimal("100.00")
    assert test_db.get(Wallet, 2).balance == Decimal("25.00")


def test_transfer_rejects_insufficient_balance(client, test_db):
    response = client.post(
        "/transactions/transfer",
        headers={"Idempotency-Key": TRANSFER_KEY},
        json={
            "recipient_user_id": 2,
            "amount": "101.00",
            "description": "Exceeds available balance",
        },
    )

    assert response.status_code == 400
    assert test_db.query(Transaction).count() == 0
    assert test_db.query(TransferRequest).count() == 0
    assert test_db.get(Wallet, 1).balance == Decimal("100.00")
    assert test_db.get(Wallet, 2).balance == Decimal("25.00")


def test_withdrawal_rejects_insufficient_balance(client, test_db):
    response = client.post(
        "/transactions/withdraw",
        headers={"Idempotency-Key": WITHDRAWAL_KEY},
        json={
            "amount": "101.00",
            "description": "Exceeds available balance",
        },
    )

    assert response.status_code == 400
    assert test_db.query(Transaction).count() == 0
    assert test_db.query(TransferRequest).count() == 0
    assert test_db.get(Wallet, 1).balance == Decimal("100.00")


def test_deposit_is_rejected_when_deposits_are_disabled(
    client,
    test_db,
):
    original_mode = settings.DEPOSIT_MODE

    try:
        settings.DEPOSIT_MODE = "disabled"

        response = client.post(
            "/transactions/deposit",
            json={
                "amount": "10.00",
                "description": "Test deposit",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Manual deposits are disabled."
        assert test_db.get(Wallet, 1).balance == Decimal("100.00")
        assert test_db.query(Transaction).count() == 0
        assert test_db.query(TransferRequest).count() == 0
    finally:
        settings.DEPOSIT_MODE = original_mode


def _create_transaction(
    test_db,
    *,
    wallet_id,
    transaction_type,
    amount,
    reference,
    created_at,
    description=None,
):
    transaction = Transaction(
        wallet_id=wallet_id,
        related_wallet_id=None,
        transaction_type=transaction_type,
        amount=Decimal(amount),
        currency="INR",
        status="completed",
        reference=reference,
        description=description,
        created_at=created_at,
        updated_at=created_at,
    )
    test_db.add(transaction)
    test_db.commit()
    test_db.refresh(transaction)
    return transaction


def test_transaction_history_returns_only_current_users_transactions(
    client,
    test_db,
):
    sender_transaction = _create_transaction(
        test_db,
        wallet_id=1,
        transaction_type="withdrawal",
        amount="10.00",
        reference="HISTORY-SENDER-001",
        created_at=datetime.now(timezone.utc),
    )
    _create_transaction(
        test_db,
        wallet_id=2,
        transaction_type="withdrawal",
        amount="5.00",
        reference="HISTORY-RECIPIENT-001",
        created_at=datetime.now(timezone.utc) + timedelta(seconds=1),
    )

    response = client.get("/transactions/history")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == sender_transaction.id
    assert body[0]["wallet_id"] == 1


def test_transaction_history_returns_empty_list_when_no_transactions(
    client,
):
    response = client.get("/transactions/history")

    assert response.status_code == 200
    assert response.json() == []


def test_transaction_history_paginates_with_skip_and_limit(
    client,
    test_db,
):
    now = datetime.now(timezone.utc)

    created_transactions = [
        _create_transaction(
            test_db,
            wallet_id=1,
            transaction_type="withdrawal",
            amount="1.00",
            reference=f"HISTORY-PAGE-{index}",
            created_at=now + timedelta(seconds=index),
        )
        for index in range(3)
    ]

    response = client.get(
        "/transactions/history",
        params={"skip": 1, "limit": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1

    # History is ordered newest first.
    expected_ids = [
        transaction.id
        for transaction in sorted(
            created_transactions,
            key=lambda item: (item.created_at, item.id),
            reverse=True,
        )
    ]
    assert body[0]["id"] == expected_ids[1]


def test_transaction_history_rejects_negative_skip(client):
    response = client.get(
        "/transactions/history",
        params={"skip": -1},
    )

    assert response.status_code == 422


def test_transaction_history_rejects_zero_limit(client):
    response = client.get(
        "/transactions/history",
        params={"limit": 0},
    )

    assert response.status_code == 422


def test_transaction_history_rejects_limit_above_maximum(client):
    response = client.get(
        "/transactions/history",
        params={"limit": 101},
    )

    assert response.status_code == 422


def test_transfer_rejects_zero_amount(client, test_db):
    response = client.post(
        "/transactions/transfer",
        headers={"Idempotency-Key": TRANSFER_KEY},
        json={
            "recipient_user_id": 2,
            "amount": "0.00",
            "description": "Invalid amount",
        },
    )

    assert response.status_code == 422
    assert test_db.query(Transaction).count() == 0
    assert test_db.query(TransferRequest).count() == 0
    assert test_db.get(Wallet, 1).balance == Decimal("100.00")


def test_transfer_rejects_amount_with_more_than_two_decimal_places(
    client,
    test_db,
):
    response = client.post(
        "/transactions/transfer",
        headers={"Idempotency-Key": TRANSFER_KEY},
        json={
            "recipient_user_id": 2,
            "amount": "10.001",
            "description": "Invalid precision",
        },
    )

    assert response.status_code == 422
    assert test_db.query(Transaction).count() == 0
    assert test_db.get(Wallet, 1).balance == Decimal("100.00")


def test_withdrawal_rejects_zero_amount(client, test_db):
    response = client.post(
        "/transactions/withdraw",
        headers={"Idempotency-Key": WITHDRAWAL_KEY},
        json={
            "amount": "0.00",
            "description": "Invalid amount",
        },
    )

    assert response.status_code == 422
    assert test_db.query(Transaction).count() == 0
    assert test_db.query(TransferRequest).count() == 0
    assert test_db.get(Wallet, 1).balance == Decimal("100.00")


def test_withdrawal_rejects_amount_with_more_than_two_decimal_places(
    client,
    test_db,
):
    response = client.post(
        "/transactions/withdraw",
        headers={"Idempotency-Key": WITHDRAWAL_KEY},
        json={
            "amount": "10.001",
            "description": "Invalid precision",
        },
    )

    assert response.status_code == 422
    assert test_db.query(Transaction).count() == 0
    assert test_db.get(Wallet, 1).balance == Decimal("100.00")


def test_transfer_rejects_description_longer_than_255_characters(
    client,
    test_db,
):
    response = client.post(
        "/transactions/transfer",
        headers={"Idempotency-Key": TRANSFER_KEY},
        json={
            "recipient_user_id": 2,
            "amount": "10.00",
            "description": "x" * 256,
        },
    )

    assert response.status_code == 422
    assert test_db.query(Transaction).count() == 0
    assert test_db.get(Wallet, 1).balance == Decimal("100.00")


def test_withdrawal_rejects_description_longer_than_255_characters(
    client,
    test_db,
):
    response = client.post(
        "/transactions/withdraw",
        headers={"Idempotency-Key": WITHDRAWAL_KEY},
        json={
            "amount": "10.00",
            "description": "x" * 256,
        },
    )

    assert response.status_code == 422
    assert test_db.query(Transaction).count() == 0
    assert test_db.get(Wallet, 1).balance == Decimal("100.00")
