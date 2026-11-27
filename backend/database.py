import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

load_dotenv()

database_url = URL.create(
    "postgresql+psycopg",
    username=os.getenv("PGUSER", "postgres"),
    password=os.environ["PGPASSWORD"],
    host=os.getenv("PGHOST", "localhost"),
    port=int(os.getenv("PGPORT", "5432")),
    database=os.getenv("PGDATABASE", "ai_customer_support"),
)

engine = create_engine(database_url, pool_pre_ping=True)