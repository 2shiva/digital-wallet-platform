import hashlib
import json
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models import Transaction, TransferRequest, User, Wallet
from app.schemas.transaction import DepositRequest, TransactionResponse


router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"],
)


class TransferRequestBody(BaseModel):
    recipient_user_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    description: str | None = Field(default=None, max_length=255)


class WithdrawalRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    description: str | None = Field(default=None, max_length=255)


def validate_amount(amount: Decimal) -> None:
    if not amount.is_finite() or amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Amount must be positive and finite.",
        )

    if amount.as_tuple().exponent < -2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Amount cannot have more than two decimal places.",
        )


def create_request_hash(payload: dict) -> str:
    canonical_request = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()


def normalize_idempotency_key(idempotency_key: str) -> str:
    normalized_key = idempotency_key.strip()

    if len(normalized_key) < 16:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Idempotency-Key must contain at least 16 characters.",
        )

    return normalized_key


@router.post(
    "/deposit",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def deposit_money(
    deposit_data: DepositRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionResponse:
    """Create a manual wallet deposit only when explicitly enabled."""

    # Manual deposits are disabled by default.
    if settings.DEPOSIT_MODE != "enabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manual deposits are disabled.",
        )

    validate_amount(deposit_data.amount)

    try:
        wallet = db.scalar(
            select(Wallet)
            .where(Wallet.user_id == current_user.id)
            .with_for_update()
        )

        if wallet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Wallet not found.",
            )

        if wallet.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Wallet is not active.",
            )

        transaction = Transaction(
            wallet_id=wallet.id,
            related_wallet_id=None,
            transaction_type="deposit",
            amount=deposit_data.amount,
            currency=wallet.currency,
            status="completed",
            reference=f"DEP-{uuid4().hex}",
            description=deposit_data.description or "Development deposit",
        )

        wallet.balance += deposit_data.amount
        db.add(transaction)
        db.commit()
        db.refresh(transaction)

        return transaction

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Deposit could not be processed.",
        )


@router.get(
    "/history",
    response_model=list[TransactionResponse],
)
def get_transaction_history(
    skip: int = Query(
        default=0,
        ge=0,
        description="Number of transactions to skip",
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of transactions to return",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TransactionResponse]:
    """Return the current user's transaction history with pagination."""

    wallet = db.scalar(
        select(Wallet).where(Wallet.user_id == current_user.id)
    )

    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found.",
        )

    transactions = db.scalars(
        select(Transaction)
        .where(Transaction.wallet_id == wallet.id)
        .order_by(
            Transaction.created_at.desc(),
            Transaction.id.desc(),
        )
        .offset(skip)
        .limit(limit)
    ).all()

    return list(transactions)


@router.post(
    "/transfer",
    response_model=list[TransactionResponse],
    status_code=status.HTTP_201_CREATED,
)
def transfer_money(
    transfer_data: TransferRequestBody,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=16,
        max_length=100,
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TransactionResponse]:
    """Transfer funds once per user and idempotency key."""

    validate_amount(transfer_data.amount)

    if transfer_data.recipient_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot transfer money to yourself.",
        )

    normalized_key = normalize_idempotency_key(idempotency_key)

    request_hash = create_request_hash(
        {
            "operation": "transfer",
            "recipient_user_id": transfer_data.recipient_user_id,
            "amount": format(transfer_data.amount, ".2f"),
            "description": transfer_data.description,
        }
    )

    try:
        # Serialize requests for this user.
        db.execute(
            select(User.id)
            .where(User.id == current_user.id)
            .with_for_update()
        ).scalar_one()

        previous_request = db.scalar(
            select(TransferRequest).where(
                TransferRequest.user_id == current_user.id,
                TransferRequest.idempotency_key == normalized_key,
            )
        )

        if previous_request is not None:
            if previous_request.request_hash != request_hash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This Idempotency-Key was already used "
                        "with different request details."
                    ),
                )

            existing_transactions = db.scalars(
                select(Transaction)
                .where(
                    Transaction.reference.in_(
                        [
                            f"{previous_request.transfer_reference}-OUT",
                            f"{previous_request.transfer_reference}-IN",
                        ]
                    )
                )
                .order_by(Transaction.id)
            ).all()

            if len(existing_transactions) != 2:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="The original transfer records are incomplete.",
                )

            db.commit()
            return list(existing_transactions)

        wallets = db.scalars(
            select(Wallet)
            .where(
                Wallet.user_id.in_(
                    [current_user.id, transfer_data.recipient_user_id]
                )
            )
            .order_by(Wallet.id)
            .with_for_update()
        ).all()

        wallet_by_user = {wallet.user_id: wallet for wallet in wallets}
        sender_wallet = wallet_by_user.get(current_user.id)
        recipient_wallet = wallet_by_user.get(
            transfer_data.recipient_user_id
        )

        if sender_wallet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Your wallet was not found.",
            )

        if recipient_wallet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recipient wallet was not found.",
            )

        if (
            sender_wallet.status != "active"
            or recipient_wallet.status != "active"
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both wallets must be active.",
            )

        if sender_wallet.currency != recipient_wallet.currency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Wallet currencies must match.",
            )

        amount = transfer_data.amount

        if sender_wallet.balance < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient wallet balance.",
            )

        transfer_reference = f"TRF-{uuid4().hex}"

        request_record = TransferRequest(
            user_id=current_user.id,
            idempotency_key=normalized_key,
            request_hash=request_hash,
            transfer_reference=transfer_reference,
        )

        debit = Transaction(
            wallet_id=sender_wallet.id,
            related_wallet_id=recipient_wallet.id,
            transaction_type="transfer",
            amount=amount,
            currency=sender_wallet.currency,
            status="completed",
            reference=f"{transfer_reference}-OUT",
            description=transfer_data.description or "Wallet transfer sent",
        )

        credit = Transaction(
            wallet_id=recipient_wallet.id,
            related_wallet_id=sender_wallet.id,
            transaction_type="transfer",
            amount=amount,
            currency=recipient_wallet.currency,
            status="completed",
            reference=f"{transfer_reference}-IN",
            description=(
                transfer_data.description or "Wallet transfer received"
            ),
        )

        sender_wallet.balance -= amount
        recipient_wallet.balance += amount

        db.add_all([request_record, debit, credit])
        db.commit()
        db.refresh(debit)
        db.refresh(credit)

        return [debit, credit]

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The transfer request conflicted with an existing request. "
                "Retry using the same Idempotency-Key."
            ),
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transfer could not be processed.",
        )


@router.post(
    "/withdraw",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def withdraw_money(
    withdrawal_data: WithdrawalRequest,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=16,
        max_length=100,
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionResponse:
    """Withdraw funds once per user and idempotency key."""

    validate_amount(withdrawal_data.amount)
    normalized_key = normalize_idempotency_key(idempotency_key)

    request_hash = create_request_hash(
        {
            "operation": "withdrawal",
            "amount": format(withdrawal_data.amount, ".2f"),
            "description": withdrawal_data.description,
        }
    )

    try:
        db.execute(
            select(User.id)
            .where(User.id == current_user.id)
            .with_for_update()
        ).scalar_one()

        previous_request = db.scalar(
            select(TransferRequest).where(
                TransferRequest.user_id == current_user.id,
                TransferRequest.idempotency_key == normalized_key,
            )
        )

        if previous_request is not None:
            if previous_request.request_hash != request_hash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This Idempotency-Key was already used "
                        "with different request details."
                    ),
                )

            existing_transaction = db.scalar(
                select(Transaction).where(
                    Transaction.reference
                    == previous_request.transfer_reference
                )
            )

            if existing_transaction is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="The original withdrawal record is missing.",
                )

            db.commit()
            return existing_transaction

        wallet = db.scalar(
            select(Wallet)
            .where(Wallet.user_id == current_user.id)
            .with_for_update()
        )

        if wallet is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Wallet not found.",
            )

        if wallet.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Wallet is not active.",
            )

        amount = withdrawal_data.amount

        if wallet.balance < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient wallet balance.",
            )

        withdrawal_reference = f"WDR-{uuid4().hex}"

        request_record = TransferRequest(
            user_id=current_user.id,
            idempotency_key=normalized_key,
            request_hash=request_hash,
            transfer_reference=withdrawal_reference,
        )

        transaction = Transaction(
            wallet_id=wallet.id,
            related_wallet_id=None,
            transaction_type="withdrawal",
            amount=amount,
            currency=wallet.currency,
            status="completed",
            reference=withdrawal_reference,
            description=(
                withdrawal_data.description or "Wallet withdrawal"
            ),
        )

        wallet.balance -= amount
        db.add_all([request_record, transaction])
        db.commit()
        db.refresh(transaction)

        return transaction

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The withdrawal request conflicted with an existing request. "
                "Retry using the same Idempotency-Key."
            ),
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Withdrawal could not be processed.",
        )