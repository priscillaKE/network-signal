# Telecom QoS Warehouse

A reproducible PostgreSQL/PostGIS data generator for mobile network quality-of-service analysis and Power BI reporting.

## Requirements

- Python 3.10+
- PostgreSQL 14+
- PostGIS installed in the PostgreSQL server
- A PostgreSQL user that can create the `telecom_qos_db` database and enable PostGIS

Install the Python dependency:

```powershell
python -m pip install -r requirements.txt
```

## Configuration

Set the non-secret connection values as environment variables. PostgreSQL's
client library (`libpq`) reads the password locally from its password file, so
the password is not stored in these scripts or in the repository.

On Windows, create `%APPDATA%\postgresql\pgpass.conf` with one line:

```text
localhost:5432:*:postgres:your-local-password
```

Restrict the file to your Windows account. PostgreSQL uses the format
`host:port:database:user:password`; use `*` for the database so the same
credential works for both the cluster check and `telecom_qos_db`.

Then set the non-secret values in PowerShell:

```powershell
$env:QOS_DB_NAME = "telecom_qos_db"
```

The scripts also accept `QOS_DB_HOST`, `QOS_DB_PORT`, `QOS_DB_USER`,
`QOS_ROW_COUNT`, and `QOS_RANDOM_SEED`. Do not commit a `.env` file or a
password file.

## Run

Check connectivity to the PostgreSQL cluster:

```powershell
python test_db_connection.py
```

Create the database and schema, then load deterministic sample telemetry:

```powershell
python build_qos_warehouse.py
```

The loader is safe to rerun for the generated IDs. For a clean rebuild, remove the existing `fact_network_telemetry` table before running it again.
Older versions of the table are migrated in place before indexes and new rows are loaded.

## Data model

`fact_network_telemetry` stores one telemetry observation per row:

- `recorded_at`: UTC-capable observation timestamp
- `network_type`: `5G`, `4G LTE`, `3G`, or `2G`
- `signal_strength_dbm`: signal strength in dBm
- `latency_ms`: network latency
- `packet_loss_pct`: packet loss percentage
- `call_dropped_flag`: boolean dropped-call indicator
- `district`: Uganda district label
- `location`: PostGIS point in EPSG:4326

The spatial, district, network type, and timestamp indexes support map visuals and common Power BI filters.

## Power BI compatibility

The loader preserves the existing `fact_network_telemetry` table and its
column names. It creates the table only when it does not exist, and reruns use
`ON CONFLICT (telemetry_id) DO NOTHING`, so an existing Power BI model can
continue using the same PostgreSQL connection and fields.
