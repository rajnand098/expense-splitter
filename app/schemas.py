from datetime import datetime

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


class ExpenseCreate(BaseModel):
    description: str
    amount: int = Field(gt=0, description="Amount in paise (Rs 100.50 = 10050)")
    paid_by: int


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