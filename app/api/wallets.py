
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.models import User, Wallet
from app.schemas.wallet import WalletResponse


router = APIRouter(
    prefix="/wallets",
    tags=["Wallets"],
)


@router.get(
    "/me",
    response_model=WalletResponse,
)
def get_my_wallet(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WalletResponse:
    """Return the authenticated user's wallet."""

    wallet = db.scalar(
        select(Wallet).where(
            Wallet.user_id == current_user.id
        )
    )

    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found for this user.",
        )

    return wallet
