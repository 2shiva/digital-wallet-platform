
from decimal import Decimal

from sqlalchemy import select

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
    transactions = response.json()
    assert len(transactions) == 2

    sender_wallet = test_db.get(Wallet, 1)
    recipient_wallet = test_db.get(Wallet, 2)

    assert sender_wallet.balance == Decimal("90.00")
    assert recipient_wallet.balance == Decimal("35.00")

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
