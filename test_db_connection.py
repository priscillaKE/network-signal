import os
import sys

import psycopg2

DB_HOST = os.getenv("QOS_DB_HOST", "localhost")
DB_PORT = os.getenv("QOS_DB_PORT", "5432")
DB_USER = os.getenv("QOS_DB_USER", "postgres")
DB_NAME = os.getenv("QOS_DB_NAME", "postgres")

def main():
    print("Checking PostgreSQL connectivity...")
    connection_settings = {
        "host": DB_HOST,
        "port": DB_PORT,
        "user": DB_USER,
        "database": DB_NAME,
    }

    try:
        with psycopg2.connect(**connection_settings) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT version();")
                db_version = cursor.fetchone()

        print("Connection successful.")
        print(f"Server: {db_version[0]}")
    except psycopg2.Error as error:
        print("Connection failed.")
        print(f"Error: {error}")
        print("Check %APPDATA%\\postgresql\\pgpass.conf for local credentials.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
