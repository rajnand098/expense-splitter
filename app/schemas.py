from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    name: str
    email: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str