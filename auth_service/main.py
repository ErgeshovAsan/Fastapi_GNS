from fastapi import FastAPI, HTTPException
from tortoise.contrib.fastapi import register_tortoise
from tortoise.models import Model
from tortoise import fields
from pydantic import BaseModel
from passlib.hash import bcrypt
from dotenv import load_dotenv
import os
import logging
logging.basicConfig(level=logging.DEBUG)

app = FastAPI(title="Auth Service")

load_dotenv()

X_Road_Client = os.getenv("X_Road_Client")
ClientUUID = os.getenv("ClientUUID")
USER_TIN = os.getenv("USER_TIN")
Authorization = os.getenv("Authorization")

class UserIn(BaseModel):
    username: str
    password: str

class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    hashed_password = fields.CharField(max_length=128)

@app.post("/register")
async def register(user: UserIn):
    if await User.get_or_none(username=user.username):
        raise HTTPException(400, detail="User already exists")
    hashed = bcrypt.hash(user.password)
    await User.create(username=user.username, hashed_password=hashed)
    return {"msg": "User registered"}

@app.post("/login")
async def login(user: UserIn):
    db_user = await User.get_or_none(username=user.username)
    if not db_user or not bcrypt.verify(user.password, db_user.hashed_password):
        raise HTTPException(401, detail="Invalid credentials")

    return {
        "X-Road-Client": X_Road_Client,
        "ClientUUID": ClientUUID,
        "USER-TIN": USER_TIN,
        "Authorization": Authorization
    }

register_tortoise(
    app,
    db_url="sqlite:///./auth_db/auth_db.sqlite3",
    modules={"models": ["main"]},
    generate_schemas=True,
    add_exception_handlers=True,
)


