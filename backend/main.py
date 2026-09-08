import os
import time

import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Calculator Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "calculator")
DB_USER = os.getenv("POSTGRES_USER", "calculator")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "calculator123")

OPERATIONS = {
    "add": lambda a, b: a + b,
    "subtract": lambda a, b: a - b,
    "multiply": lambda a, b: a * b,
    "divide": lambda a, b: a / b,
}


class CalculationRequest(BaseModel):
    operation: str
    a: float
    b: float


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def init_db():
    for attempt in range(10):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS calculations (
                    id SERIAL PRIMARY KEY,
                    operation VARCHAR(20) NOT NULL,
                    a DOUBLE PRECISION NOT NULL,
                    b DOUBLE PRECISION NOT NULL,
                    result DOUBLE PRECISION NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                """
            )
            conn.commit()
            cur.close()
            conn.close()
            return
        except psycopg2.OperationalError:
            time.sleep(3)
    raise RuntimeError("Could not connect to database after multiple attempts")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/calculate")
def calculate(req: CalculationRequest):
    if req.operation not in OPERATIONS:
        raise HTTPException(status_code=400, detail="Invalid operation")

    if req.operation == "divide" and req.b == 0:
        raise HTTPException(status_code=400, detail="Cannot divide by zero")

    result = OPERATIONS[req.operation](req.a, req.b)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO calculations (operation, a, b, result) VALUES (%s, %s, %s, %s)",
        (req.operation, req.a, req.b, result),
    )
    conn.commit()
    cur.close()
    conn.close()

    return {"operation": req.operation, "a": req.a, "b": req.b, "result": result}
