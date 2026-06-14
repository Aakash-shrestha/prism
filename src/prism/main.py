from fastapi import FastAPI

from prism.webhook import router

app = FastAPI()


@app.get("/")
def root():
    return {"status": "ok"}


app.include_router(router)
