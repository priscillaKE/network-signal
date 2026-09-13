import os
import sys

import psycopg2

DB_HOST = os.getenv("QOS_DB_HOST", "localhost")
DB_PORT = os.getenv("QOS_DB_PORT", "5432")
DB_USER = os.getenv("QOS_DB_USER", "postgres")
DB_NAME = os.getenv("QOS_DB_NAME", "postgres")

def main():
    print(" Attempting a handshake with your PostgreSQL local cluster server...")
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

        print("\n --- CONNECTIVITY STATUS: SUCCESS ---")
        print(f"Connected to database engine running on: {db_version[0]}")
        print(" Securely disconnected. Network channel is fully operational!")
    except psycopg2.Error as error:
        print("\n CONNECTIVITY STATUS: FAILED")
        print(f"Error Details: {error}")
        print("\n Troubleshooting Tip: Add your local credential to %APPDATA%\\postgresql\\pgpass.conf.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
