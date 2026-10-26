
import pytest
from fastapi import HTTPException

from app.api.transactions import (
    create_request_hash,
    normalize_idempotency_key,
)


def test_request_hash_is_stable_for_same_payload():
    payload = {
        "operation": "transfer",
        "recipient_user_id": 1,
        "amount": "10.00",
        "description": "Automated test",
    }

    first_hash = create_request_hash(payload)
    second_hash = create_request_hash(payload)

    assert first_hash == second_hash
    assert len(first_hash) == 64


def test_request_hash_is_independent_of_dictionary_key_order():
    first_payload = {
        "operation": "transfer",
        "recipient_user_id": 1,
        "amount": "10.00",
        "description": "Automated test",
    }

    second_payload = {
        "description": "Automated test",
        "amount": "10.00",
        "recipient_user_id": 1,
        "operation": "transfer",
    }

    assert create_request_hash(first_payload) == create_request_hash(
        second_payload
    )


def test_request_hash_changes_when_request_details_change():
    first_payload = {
        "operation": "transfer",
        "recipient_user_id": 1,
        "amount": "10.00",
        "description": "Automated test",
    }

    changed_payload = {
        **first_payload,
        "amount": "11.00",
    }

    assert create_request_hash(first_payload) != create_request_hash(
        changed_payload
    )


def test_idempotency_key_is_trimmed():
    key = "  wallet-transfer-test-001  "

    assert normalize_idempotency_key(key) == "wallet-transfer-test-001"


def test_idempotency_key_rejects_short_key():
    with pytest.raises(HTTPException) as exc_info:
        normalize_idempotency_key("short-key")

    assert exc_info.value.status_code == 422
    assert "at least 16 characters" in exc_info.value.detail
