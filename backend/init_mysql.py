"""Initializes MySQL with schema.sql and seed.sql."""

import os
import pymysql
from backend.config import settings


def init_mysql_database():
    print(f"Connecting to MySQL at {settings.MYSQL_HOST}:{settings.MYSQL_PORT}...")
    conn = pymysql.connect(
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        autocommit=True,
    )
    
    with conn.cursor() as cursor:
        print("Ensuring database enterprise_analytics exists...")
        cursor.execute("CREATE DATABASE IF NOT EXISTS enterprise_analytics;")
        cursor.execute("USE enterprise_analytics;")

        # Apply schema.sql
        schema_file = os.path.join("data", "schema.sql")
        if os.path.exists(schema_file):
            print("Applying schema.sql...")
            with open(schema_file, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            for stmt in schema_sql.split(";"):
                stmt = stmt.strip()
                if stmt:
                    cursor.execute(stmt)
            print("Schema applied successfully.")

        # Apply seed.sql
        seed_file = os.path.join("data", "seed.sql")
        if os.path.exists(seed_file):
            print("Applying seed.sql (this may take a few seconds)...")
            with open(seed_file, "r", encoding="utf-8") as f:
                seed_sql = f.read()
            
            statements = [s.strip() for s in seed_sql.split(";\n") if s.strip()]
            for stmt in statements:
                try:
                    cursor.execute(stmt)
                except Exception as e:
                    print(f"Statement notice: {e}")
            print("Seed data loaded into MySQL successfully.")

    conn.close()
    print("MySQL initialization completed.")


if __name__ == "__main__":
    init_mysql_database()
