from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    name: str
    email: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str


class GroupCreate(BaseModel):
    name: str


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    members: list[UserOut] = []


class MemberAdd(BaseModel):
    user_id: int


class SplitInput(BaseModel):
    user_id: int
    amount: int | None = Field(default=None, gt=0, description="Exact paise")
    percent: int | None = Field(
        default=None, gt=0, le=10000, description="Basis points (50% = 5000)"
    )


class ExpenseCreate(BaseModel):
    description: str
    amount: int = Field(gt=0, description="Amount in paise (Rs 100.50 = 10050)")
    paid_by: int
    split_type: Literal["equal", "exact", "percentage"] = "equal"
    splits: list[SplitInput] | None = None


class SplitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    amount: int


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    paid_by: int
    description: str
    amount: int
    created_at: datetime
    splits: list[SplitOut] = []


class BalanceOut(BaseModel):
    user_id: int
    balance: int  # paise; positive = lene hain, negative = dene hain


class SettlementOut(BaseModel):
    from_user: int
    to_user: int
    amount: int  # paise