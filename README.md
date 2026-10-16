Digital Wallet Platform

A secure digital wallet REST API built with FastAPI, Python, and PostgreSQL, featuring wallet management, transaction processing, JWT authentication, and idempotency protection for financial operations.

Features

Authentication: JWT-based authentication and authenticated API access.

Wallet Management: Retrieve wallet information and balance.

Transactions: Support for deposits, withdrawals, transfers, and transaction history.

Idempotency: Prevent duplicate transfer and withdrawal processing when clients retry requests with the same idempotency key.

Request Validation: Validate transaction amounts and request data.

Database Migrations: Manage database schema changes with Alembic.

Automated Testing: Test transaction logic and API behavior with pytest.

Technology Stack

Python

FastAPI

PostgreSQL

SQLAlchemy

Alembic

Pytest

JWT authentication

Project Structure

digital-wallet-platform/
├── alembic/
│   └── versions/
├── app/
│   ├── api/
│   │   ├── auth.py
│   │   ├── transactions.py
│   │   └── wallets.py
│   ├── core/
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   └── security.py
│   ├── database/
│   │   └── session.py
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   └── main.py
├── tests/
│   ├── conftest.py
│   ├── test_transaction_api.py
│   └── test_transactions.py
├── .env.example
├── .gitignore
├── alembic.ini
├── dependencies.py
├── pytest.ini
├── requirements.txt
└── README.md

Prerequisites

Install the following before running the project:

Python compatible with the installed dependencies

PostgreSQL

Git

Installation

1. Clone the repository

git clone https://github.com/2shiva/digital-wallet-platform.git
cd digital-wallet-platform

2. Create and activate a virtual environment

On macOS or Linux:

python3 -m venv venv
source venv/bin/activate

3. Install dependencies

python -m pip install -r requirements.txt

4. Configure environment variables

Create your local environment file:

cp .env.example .env

Open .env and configure the values for your local PostgreSQL database.

Required settings:

DATABASE_URL=postgresql://YOUR_DB_USER:YOUR_DB_PASSWORD@localhost:5432/digital_wallet_db
SECRET_KEY=replace-with-a-strong-random-secret
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

Replace the placeholders with your local configuration. Generate a strong secret key and never commit .env or real credentials to GitHub.

5. Prepare the database

Create the PostgreSQL database and database user according to your local configuration.

Apply the Alembic migrations:

alembic upgrade head

If your database already contains the application's tables, check the current migration state before applying migrations.

6. Run the application

uvicorn app.main:app --reload

The development server will normally be available at:

http://127.0.0.1:8000

FastAPI interactive API documentation:

http://127.0.0.1:8000/docs

API Capabilities

The application provides endpoints for:

Feature

Description

Authentication

Authenticate users and access protected endpoints

Wallet

Retrieve the authenticated user's wallet

Deposit

Add funds to a wallet

Withdrawal

Withdraw funds subject to validation and balance checks

Transfer

Transfer funds between wallets

Transaction History

Retrieve the authenticated user's transaction history

For exact endpoint paths, request schemas, and authentication requirements, refer to the API documentation at /docs while the application is running.

Idempotency

Transfer and withdrawal requests support an Idempotency-Key header.

Example:

Idempotency-Key: unique-operation-key-123

The same key and same request details can be used to retry an operation without creating duplicate transactions. Reusing a key with different request details returns a conflict response (409 Conflict).

Clients should generate a unique key for each new financial operation and reuse that key when retrying the same operation.

Running Tests

Activate the virtual environment, then run:

python -m pytest -q

The current test suite contains 13 tests covering transaction helper functions and API behavior, including idempotency, balance updates, and insufficient-balance cases.

Security Notes

Keep .env out of version control.

Never commit passwords, signing secrets, or production database credentials.

Use a strong, unique secret key.

Use HTTPS and secure deployment configuration in production.

Review authentication, authorization, transaction consistency, and database configuration before production use.

Future Improvements

Potential enhancements include:

Expanded authentication and authorization tests.

Improved API documentation and error handling.

Structured logging and monitoring.

CI automation for tests.

Production deployment and operational hardening.

Author

GitHub: @2shiva

Repository

https://github.com/2shiva/digital-wallet-platform