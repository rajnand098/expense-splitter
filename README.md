# Expense Splitter API

Splitwise-style expense sharing backend built with **FastAPI**.

## Features (planned)

- [x] Project setup
- [x] User management
- [ ] Groups and members
- [ ] Expenses with equal / exact / percentage splits
- [ ] Balance calculation and debt simplification
- [ ] JWT authentication
- [ ] Tests (pytest)
- [ ] Docker deployment

## Tech Stack

- Python 3.10+
- FastAPI
- SQLAlchemy
- SQLite

## Run locally

```bash
git clone https://github.com/AAPKA-USERNAME/expense-splitter.git
cd expense-splitter
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs

## Author

Your Name