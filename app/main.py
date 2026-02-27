from fastapi import FastAPI
from app.routers import webhook

app = FastAPI(title="NP Academy")

app.include_router(webhook.router)