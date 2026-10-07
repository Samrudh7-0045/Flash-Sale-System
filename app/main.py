from fastapi import FastAPI

app = FastAPI(title="Flash-Sale Inventory System")


@app.get("/")
def root():
    return {"message": "Flash-Sale System is running"}