import sys, os
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

from backend.database.postgres_service import fetch_all, execute_sql
from pathlib import Path

print('=' * 60)
print('DATABASE SETUP')
print('=' * 60)

# 1. Test connection
try:
    rows = fetch_all('SELECT version()')
    print()
    print('OK  Connected:', rows[0][0][:50])
except Exception as e:
    print('FAIL DB connection:', e)
    sys.exit(1)

# 2. Check existing tables
try:
    rows = fetch_all(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY table_name"
    )
    tables = [r[0] for r in rows]
    print('OK  Tables:', tables)
except Exception as e:
    print('FAIL table check:', e)
    tables = []

# 3. Run schema.sql if tables missing
needed = ['locations', 'air_quality_observations', 'anomalies', 'hotspots']
missing = [t for t in needed if t not in tables]

if missing:
    print()
    print('Missing tables:', missing)
    print('Running schema.sql ...')
    schema_path = Path('backend/database/schema.sql')
    sql = schema_path.read_text(encoding='utf-8')
    try:
        execute_sql(sql)
        print('OK  Schema applied')
    except Exception as e:
        print('WARN schema.sql error (PostGIS may be missing):', str(e)[:200])
        # Try without PostGIS
        sql_no_gis = '\n'.join(
            line for line in sql.splitlines()
            if 'postgis' not in line.lower()
            and 'geometry' not in line.lower()
            and 'gist' not in line.lower()
        )
        try:
            execute_sql(sql_no_gis)
            print('OK  Schema applied (without PostGIS)')
        except Exception as e2:
            print('FAIL schema:', str(e2)[:200])
else:
    print('OK  All required tables exist')

# 4. Check row counts
print()
print('ROW COUNTS:')
for t in needed:
    try:
        rows = fetch_all('SELECT COUNT(*) FROM ' + t)
        print('  ', t, '=', rows[0][0], 'rows')
    except Exception as e:
        print('  ', t, '= ERROR:', str(e)[:80])

print()
print('Database setup complete.')
