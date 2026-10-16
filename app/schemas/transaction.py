from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DepositRequest(BaseModel):
    amount: Decimal = Field(
        gt=0,
        max_digits=18,
        decimal_places=2,
    )
    description: str | None = Field(
        default=None,
        max_length=255,
    )


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_id: int
    related_wallet_id: int | None
    transaction_type: str
    amount: Decimal
    currency: str
    status: str
    reference: str
    description: str | None
    created_at: datetime
    updated_at: datetime