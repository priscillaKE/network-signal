import os
import random
from datetime import datetime, timedelta

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

DB_HOST = os.getenv("QOS_DB_HOST", "localhost")
DB_PORT = os.getenv("QOS_DB_PORT", "5432")
DB_USER = os.getenv("QOS_DB_USER", "postgres")
TARGET_DB = os.getenv("QOS_DB_NAME", "telecom_qos_db")
ROW_COUNT = int(os.getenv("QOS_ROW_COUNT", "50000"))
RANDOM_SEED = int(os.getenv("QOS_RANDOM_SEED", "20260801"))


def connection_kwargs(database):
    """Build connection settings; libpq resolves credentials locally."""
    return {
        "host": DB_HOST,
        "port": DB_PORT,
        "user": DB_USER,
        "database": database,
    }

def setup_database_instance():
    """Creates the warehouse database if it does not already exist."""
    print("Checking PostgreSQL database...")
    conn = psycopg2.connect(**connection_kwargs("postgres"))
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (TARGET_DB,))
    if cursor.fetchone():
        print(f"Using existing database '{TARGET_DB}'.")
    else:
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TARGET_DB)))
        print(f"Created database '{TARGET_DB}'.")
    cursor.close()
    conn.close()

def build_schema_layout():
    """Create the telemetry schema, indexes, and Power BI reporting view."""
    print(f"Preparing schema in '{TARGET_DB}'...")
    conn = psycopg2.connect(**connection_kwargs(TARGET_DB))
    try:
        cursor = conn.cursor()

        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS fact_network_telemetry (
            telemetry_id TEXT PRIMARY KEY,
            recorded_at TIMESTAMPTZ NOT NULL,
            device_model VARCHAR(50) NOT NULL,
            network_type VARCHAR(10) NOT NULL CHECK (network_type IN ('5G', '4G LTE', '3G', '2G')),
            signal_strength_dbm SMALLINT NOT NULL CHECK (signal_strength_dbm BETWEEN -140 AND -30),
            latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
            packet_loss_pct NUMERIC(5, 2) NOT NULL CHECK (packet_loss_pct BETWEEN 0 AND 100),
            call_dropped_flag BOOLEAN NOT NULL,
            district VARCHAR(50) NOT NULL,
            location geometry(Point, 4326) NOT NULL
        );
        """)

        cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'fact_network_telemetry'
        """)
        column_types = {row[0]: row[1] for row in cursor.fetchall()}
        columns = set(column_types)

        if "timestamp" in columns and "recorded_at" not in columns:
            cursor.execute("""
            ALTER TABLE fact_network_telemetry
            RENAME COLUMN timestamp TO recorded_at
            """)
            columns.remove("timestamp")
            columns.add("recorded_at")

        if column_types.get("recorded_at") == "timestamp without time zone":
            cursor.execute("""
            ALTER TABLE fact_network_telemetry
            ALTER COLUMN recorded_at TYPE TIMESTAMPTZ
            USING recorded_at AT TIME ZONE 'UTC'
            """)
        if column_types.get("signal_strength_dbm") != "smallint":
            cursor.execute("""
            ALTER TABLE fact_network_telemetry
            ALTER COLUMN signal_strength_dbm TYPE SMALLINT
            USING signal_strength_dbm::SMALLINT
            """)
        if column_types.get("packet_loss_pct") != "numeric":
            cursor.execute("""
            ALTER TABLE fact_network_telemetry
            ALTER COLUMN packet_loss_pct TYPE NUMERIC(5, 2)
            USING packet_loss_pct::NUMERIC(5, 2)
            """)
        if column_types.get("call_dropped_flag") != "boolean":
            cursor.execute("""
            ALTER TABLE fact_network_telemetry
            ALTER COLUMN call_dropped_flag TYPE BOOLEAN
            USING (call_dropped_flag <> 0)
            """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_qos_network_type ON fact_network_telemetry(network_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_qos_district ON fact_network_telemetry(district);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_qos_recorded_at ON fact_network_telemetry(recorded_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_qos_location ON fact_network_telemetry USING GIST(location);")

        cursor.execute("""
        CREATE OR REPLACE VIEW vw_powerbi_network_telemetry AS
        SELECT
            telemetry_id,
            recorded_at,
            recorded_at::date AS observation_date,
            EXTRACT(YEAR FROM recorded_at)::INTEGER AS observation_year,
            EXTRACT(MONTH FROM recorded_at)::INTEGER AS observation_month,
            TO_CHAR(recorded_at, 'YYYY-MM') AS observation_month_label,
            device_model,
            network_type,
            signal_strength_dbm,
            CASE
                WHEN signal_strength_dbm >= -75 THEN 'Excellent'
                WHEN signal_strength_dbm >= -90 THEN 'Good'
                WHEN signal_strength_dbm >= -105 THEN 'Weak'
                ELSE 'Critical'
            END AS signal_band,
            latency_ms,
            packet_loss_pct,
            call_dropped_flag,
            CASE
                WHEN call_dropped_flag
                    OR signal_strength_dbm < -105
                    OR latency_ms > 100
                    OR packet_loss_pct > 5
                THEN TRUE
                ELSE FALSE
            END AS network_issue_flag,
            GREATEST(
                0,
                LEAST(
                    100,
                    100
                    - ((-signal_strength_dbm - 50) * 0.8)
                    - (latency_ms * 0.15)
                    - (packet_loss_pct * 2)
                    - CASE WHEN call_dropped_flag THEN 25 ELSE 0 END
                )
            )::NUMERIC(5, 2) AS qos_score,
            district,
            ST_Y(location) AS latitude,
            ST_X(location) AS longitude
        FROM fact_network_telemetry;
        """)

        conn.commit()
        print("Schema and reporting view are ready.")
    finally:
        conn.close()

def bulk_stream_telemetry():
    """Generate deterministic telemetry observations and load them into PostgreSQL."""
    print(f"Generating {ROW_COUNT:,} telemetry observations...")
    
    districts = ["Kampala", "Wakiso", "Mbarara", "Gulu", "Jinja", "Entebbe", "Mukono", "Masaka", "Arua", "Mbale"]
    devices = ["iPhone 15 Pro", "Samsung S24 Ultra", "Tecno Camon 30", "Infinix Hot 40", "Huawei Nova 11"]
    net_types = ["5G", "4G LTE", "3G", "2G"]
    district_coordinates = {
        "Kampala": (0.3476, 32.5825), "Wakiso": (0.4044, 32.4594),
        "Mbarara": (-0.6072, 30.6545), "Gulu": (2.7724, 32.2881),
        "Jinja": (0.4479, 33.2026), "Entebbe": (0.0512, 32.4637),
        "Mukono": (0.3533, 32.7553), "Masaka": (-0.3338, 31.7341),
        "Arua": (3.0303, 30.9111), "Mbale": (1.0788, 34.1814),
    }
    
    random.seed(RANDOM_SEED)
    records = []
    start_time = datetime(2026, 8, 1)
    
    for i in range(ROW_COUNT):
        t_id = f"TEL-QOS-{i+100000:06d}"
        district = random.choice(districts)
        device = random.choice(devices)
        latitude, longitude = district_coordinates[district]
        latitude += random.uniform(-0.03, 0.03)
        longitude += random.uniform(-0.03, 0.03)
        
        if district in ["Gulu", "Arua", "Masaka"] and random.random() > 0.4:
            net_type = random.choice(["3G", "2G"])
            signal = random.randint(-120, -105)   # Severe signal degradation
            latency = random.randint(120, 350)
            packet_loss = round(random.uniform(5.0, 25.0), 2)
            dropped = random.random() > 0.3
        else:
            net_type = random.choice(net_types)
            signal = random.randint(-95, -50)
            latency = random.randint(15, 65)
            packet_loss = round(random.uniform(0.0, 1.8), 2)
            dropped = random.random() > 0.96  # Rare drop
            
        time_delta = timedelta(days=random.randint(0, 30), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        timestamp = start_time + time_delta
        
        records.append((t_id, timestamp, device, net_type, signal, latency, packet_loss, dropped, district, longitude, latitude))
        
    print("Loading observations into PostgreSQL...")
    conn = psycopg2.connect(**connection_kwargs(TARGET_DB))
    try:
        cursor = conn.cursor()

        insert_query = """
        INSERT INTO fact_network_telemetry 
        (telemetry_id, recorded_at, device_model, network_type, signal_strength_dbm, latency_ms, packet_loss_pct, call_dropped_flag, district, location)
        VALUES %s
        ON CONFLICT (telemetry_id) DO NOTHING
        """
        insert_template = "(%s, %s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))"

        execute_values(cursor, insert_query, records, template=insert_template, page_size=1000)
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM fact_network_telemetry;")
        total_written = cursor.fetchone()[0]
        print(f"Load complete. Database contains {total_written:,} telemetry rows.")
    finally:
        conn.close()

if __name__ == "__main__":
    setup_database_instance()
    build_schema_layout()
    bulk_stream_telemetry()
