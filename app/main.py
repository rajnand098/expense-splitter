from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from .database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Expense Splitter")


# ---------- Split helpers ----------


def split_equally(total: int, user_ids: list[int]) -> dict[int, int]:
    """Total paise ko barabar baanta hai, bacha hua paisa pehle logon ko milta hai."""
    base, remainder = divmod(total, len(user_ids))
    result = {}
    for i, uid in enumerate(user_ids):
        result[uid] = base + (1 if i < remainder else 0)
    return result


def split_exact(total: int, splits: list[schemas.SplitInput]) -> dict[int, int]:
    result = {}
    for s in splits:
        if s.amount is None:
            raise HTTPException(
                status_code=400, detail="Exact split needs amount for each user"
            )
        result[s.user_id] = s.amount
    if sum(result.values()) != total:
        raise HTTPException(
            status_code=400,
            detail=f"Split amounts add up to {sum(result.values())}, expected {total}",
        )
    return result


def split_percentage(total: int, splits: list[schemas.SplitInput]) -> dict[int, int]:
    for s in splits:
        if s.percent is None:
            raise HTTPException(
                status_code=400, detail="Percentage split needs percent for each user"
            )
    if sum(s.percent for s in splits) != 10000:
        raise HTTPException(
            status_code=400, detail="Percentages must add up to 100% (10000)"
        )
    result = {s.user_id: total * s.percent // 10000 for s in splits}
    leftover = total - sum(result.values())
    for uid in list(result)[:leftover]:
        result[uid] += 1
    return result


# ---------- Balance helpers ----------


def calculate_balances(
    expenses: list[models.Expense], member_ids: list[int]
) -> dict[int, int]:
    """Har member ka net balance (paise). Positive = lene hain, negative = dene hain."""
    balances = {uid: 0 for uid in member_ids}
    for expense in expenses:
        balances[expense.paid_by] = balances.get(expense.paid_by, 0) + expense.amount
        for split in expense.splits:
            balances[split.user_id] = balances.get(split.user_id, 0) - split.amount
    return balances


def simplify_debts(balances: dict[int, int]) -> list[dict]:
    """Greedy algorithm: sabse bada debtor sabse bade creditor ko deta hai."""
    creditors = sorted(
        [[uid, bal] for uid, bal in balances.items() if bal > 0],
        key=lambda x: -x[1],
    )
    debtors = sorted(
        [[uid, -bal] for uid, bal in balances.items() if bal < 0],
        key=lambda x: -x[1],
    )
    settlements = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        pay = min(debtors[i][1], creditors[j][1])
        settlements.append(
            {"from_user": debtors[i][0], "to_user": creditors[j][0], "amount": pay}
        )
        debtors[i][1] -= pay
        creditors[j][1] -= pay
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return settlements


# ---------- Group access helper ----------


def get_group_for_member(
    group_id: int, db: Session, current_user: models.User
) -> models.Group:
    group = db.get(models.Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if current_user not in group.members:
        raise HTTPException(
            status_code=403, detail="You are not a member of this group"
        )
    return group


@app.get("/")
def home():
    return {"message": "Expense Splitter API chal rahi hai!"}


# ---------- Auth ----------


@app.post("/register", response_model=schemas.UserOut, status_code=201)
def register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(models.User).where(models.User.email == data.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = models.User(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/login", response_model=schemas.Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # /docs ka Authorize button "username" field bhejta hai, hum usme email lete hain
    user = db.scalar(select(models.User).where(models.User.email == form.username))
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@app.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


# ---------- Users ----------


@app.get("/users", response_model=list[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.scalars(select(models.User)).all()


# ---------- Groups ----------


@app.post("/groups", response_model=schemas.GroupOut, status_code=201)
def create_group(
    data: schemas.GroupCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    group = models.Group(name=data.name)
    group.members.append(current_user)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@app.get("/groups", response_model=list[schemas.GroupOut])
def list_my_groups(current_user: models.User = Depends(get_current_user)):
    return current_user.groups


@app.get("/groups/{group_id}", response_model=schemas.GroupOut)
def get_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return get_group_for_member(group_id, db, current_user)


@app.post("/groups/{group_id}/members", response_model=schemas.GroupOut)
def add_member(
    group_id: int,
    data: schemas.MemberAdd,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    group = get_group_for_member(group_id, db, current_user)
    user = db.get(models.User, data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user in group.members:
        raise HTTPException(status_code=400, detail="User already in group")
    group.members.append(user)
    db.commit()
    db.refresh(group)
    return group


# ---------- Expenses ----------


@app.post(
    "/groups/{group_id}/expenses",
    response_model=schemas.ExpenseOut,
    status_code=201,
)
def create_expense(
    group_id: int,
    data: schemas.ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    group = get_group_for_member(group_id, db, current_user)
    member_ids = [m.id for m in group.members]

    if data.split_type == "equal":
        shares = split_equally(data.amount, member_ids)
    else:
        if not data.splits:
            raise HTTPException(status_code=400, detail="splits list is required")
        ids = [s.user_id for s in data.splits]
        if len(set(ids)) != len(ids):
            raise HTTPException(status_code=400, detail="Duplicate user in splits")
        if any(uid not in member_ids for uid in ids):
            raise HTTPException(
                status_code=400, detail="Split user is not a group member"
            )
        if data.split_type == "exact":
            shares = split_exact(data.amount, data.splits)
        else:
            shares = split_percentage(data.amount, data.splits)

    expense = models.Expense(
        group_id=group_id,
        paid_by=current_user.id,
        description=data.description,
        amount=data.amount,
    )
    for uid, share in shares.items():
        expense.splits.append(models.Split(user_id=uid, amount=share))

    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@app.get("/groups/{group_id}/expenses", response_model=list[schemas.ExpenseOut])
def list_expenses(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    get_group_for_member(group_id, db, current_user)
    return db.scalars(
        select(models.Expense).where(models.Expense.group_id == group_id)
    ).all()


# ---------- Balances ----------


@app.get("/groups/{group_id}/balances", response_model=list[schemas.BalanceOut])
def get_balances(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    group = get_group_for_member(group_id, db, current_user)
    expenses = db.scalars(
        select(models.Expense).where(models.Expense.group_id == group_id)
    ).all()
    balances = calculate_balances(expenses, [m.id for m in group.members])
    return [{"user_id": uid, "balance": bal} for uid, bal in balances.items()]


@app.get("/groups/{group_id}/settlements", response_model=list[schemas.SettlementOut])
def get_settlements(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    group = get_group_for_member(group_id, db, current_user)
    expenses = db.scalars(
        select(models.Expense).where(models.Expense.group_id == group_id)
    ).all()
    balances = calculate_balances(expenses, [m.id for m in group.members])
    return simplify_debts(balances)