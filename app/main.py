from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas
from .database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Expense Splitter")


def split_equally(total: int, user_ids: list[int]) -> dict[int, int]:
    """Total paise ko barabar baanta hai, bacha hua paisa pehle logon ko milta hai."""
    base, remainder = divmod(total, len(user_ids))
    result = {}
    for i, uid in enumerate(user_ids):
        result[uid] = base + (1 if i < remainder else 0)
    return result


@app.get("/")
def home():
    return {"message": "Expense Splitter API chal rahi hai!"}


# ---------- Users ----------


@app.post("/users", response_model=schemas.UserOut, status_code=201)
def create_user(data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(models.User).where(models.User.email == data.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = models.User(**data.model_dump())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.scalars(select(models.User)).all()


# ---------- Groups ----------


@app.post("/groups", response_model=schemas.GroupOut, status_code=201)
def create_group(data: schemas.GroupCreate, db: Session = Depends(get_db)):
    group = models.Group(name=data.name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@app.get("/groups", response_model=list[schemas.GroupOut])
def list_groups(db: Session = Depends(get_db)):
    return db.scalars(select(models.Group)).all()


@app.get("/groups/{group_id}", response_model=schemas.GroupOut)
def get_group(group_id: int, db: Session = Depends(get_db)):
    group = db.get(models.Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


@app.post("/groups/{group_id}/members", response_model=schemas.GroupOut)
def add_member(group_id: int, data: schemas.MemberAdd, db: Session = Depends(get_db)):
    group = db.get(models.Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
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
    group_id: int, data: schemas.ExpenseCreate, db: Session = Depends(get_db)
):
    group = db.get(models.Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    member_ids = [m.id for m in group.members]
    if data.paid_by not in member_ids:
        raise HTTPException(status_code=400, detail="Payer is not a group member")

    expense = models.Expense(
        group_id=group_id,
        paid_by=data.paid_by,
        description=data.description,
        amount=data.amount,
    )
    for uid, share in split_equally(data.amount, member_ids).items():
        expense.splits.append(models.Split(user_id=uid, amount=share))

    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@app.get("/groups/{group_id}/expenses", response_model=list[schemas.ExpenseOut])
def list_expenses(group_id: int, db: Session = Depends(get_db)):
    if not db.get(models.Group, group_id):
        raise HTTPException(status_code=404, detail="Group not found")
    return db.scalars(
        select(models.Expense).where(models.Expense.group_id == group_id)
    ).all()