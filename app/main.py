from fastapi import FastAPI

app = FastAPI(title="Expense Splitter")


@app.get("/")
def home():
    return {"message": "Expense Splitter API chal rahi hai!"}