# Digital Wallet Platform

## Project Description

The Digital Wallet Platform is a backend application developed using Python, FastAPI, and PostgreSQL.

It allows users to register, log in, check their wallet balance, transfer money, withdraw money, and view transaction history.

## Technologies Used

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Pytest
- JWT Authentication

## Main Features

- User Registration and Login
- Secure Authentication
- Wallet Balance
- Money Transfer
- Money Withdrawal
- Transaction History
- Duplicate Transaction Prevention
- Automated Testing

## How to Run the Project

### 1. Clone the Project

```bash
git clone https://github.com/2shiva/digital-wallet-platform.git
cd digital-wallet-platform
```

### 2. Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the Database

Create a `.env` file using the example:

```bash
cp .env.example .env
```

Update the database details and secret key in `.env`.

### 5. Run Database Migrations

```bash
alembic upgrade head
```

### 6. Start the Application

```bash
uvicorn app.main:app --reload
```

Open the API documentation in your browser:

http://127.0.0.1:8000/docs

## Run Tests

```bash
python -m pytest -v
```

The latest recorded test run completed with **47 tests passed**. PostgreSQL tests require a configured test database.

## Author

GitHub: [@2shiva](https://github.com/2shiva)

## GitHub Repository

https://github.com/2shiva/digital-wallet-platform
