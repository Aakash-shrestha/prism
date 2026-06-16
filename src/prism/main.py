from fastapi import FastAPI

from prism.logging import configure_logging
from prism.webhook import router

configure_logging()

app = FastAPI()


@app.get("/")
def root():
    return {"status": "ok"}


app.include_router(router)
