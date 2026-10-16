
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class WalletResponse(BaseModel):
    """Return wallet details to its owner."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    balance: Decimal = Field(decimal_places=2)
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime
