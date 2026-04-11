from pydantic import BaseModel, ConfigDict


class CreateUserRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: str
    username: str
    password: str


class UserRecord(BaseModel):
    id: str
    full_name: str
    username: str
    password_hash: str


class UserItem(BaseModel):
    id: str
    full_name: str
    username: str


class ListUsersResponse(BaseModel):
    users: list[UserItem]
    count: int
