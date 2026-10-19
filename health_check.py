import sys, os
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

issues = []
ok = []

print('=' * 60)
print('PROJECT HEALTH CHECK')
print('=' * 60)

# ----------------------------------------------------------
# 1. ENV VARIABLES
# ----------------------------------------------------------
print()
print('[1] ENV VARIABLES')
env_check = {
    'WEATHER_API_KEY': os.getenv('WEATHER_API_KEY'),
    'GOOGLE_API_KEY':  os.getenv('GOOGLE_API_KEY'),
    'PGPASSWORD':      os.getenv('PGPASSWORD'),
    'PGHOST':          os.getenv('PGHOST'),
    'PGDATABASE':      os.getenv('PGDATABASE'),
    'PGUSER':          os.getenv('PGUSER'),
}
BAD_VALUES = {'', None, 'YOUR_POSTGRES_PASSWORD', 'YOUR_GOOGLE_API_KEY'}
for k, v in env_check.items():
    if v and v not in BAD_VALUES:
        print(f'  OK      {k} = {str(v)[:12]}...')
        ok.append(k)
    else:
        print(f'  MISSING {k} = {repr(v)}')
        issues.append('ENV: ' + k + ' is missing or placeholder')

# ----------------------------------------------------------
# 2. WEATHERAPI
# ----------------------------------------------------------
print()
print('[2] WEATHERAPI (live data)')
try:
    from backend.services.india_environment import get_environment_for_user
    r = get_environment_for_user('Pune')
    cur = r.get('current', {})
    pm25 = cur.get('pm2_5')
    if pm25:
        print('  OK   PM2.5 =', pm25, 'ug/m3')
        ok.append('WeatherAPI')
    else:
        print('  FAIL No PM2.5 returned')
        issues.append('WeatherAPI: no PM2.5 data')
except Exception as e:
    print('  FAIL', e)
    issues.append('WeatherAPI: ' + str(e))

# ----------------------------------------------------------
# 3. POSTGRESQL
# ----------------------------------------------------------
print()
print('[3] POSTGRESQL DATABASE')
try:
    from backend.database.postgres_service import fetch_all
    rows = fetch_all('SELECT COUNT(*) FROM locations')
    loc_count = rows[0][0]
    rows2 = fetch_all('SELECT COUNT(*) FROM air_quality_observations')
    obs_count = rows2[0][0]
    print('  OK   locations =', loc_count, '| air_quality_observations =', obs_count)
    ok.append('PostgreSQL')
    if obs_count == 0:
        issues.append('DB: air_quality_observations table is EMPTY - no data to query')
    if loc_count == 0:
        issues.append('DB: locations table is EMPTY - no stations loaded')
except Exception as e:
    print('  FAIL', str(e)[:120])
    issues.append('PostgreSQL: ' + str(e)[:120])

# ----------------------------------------------------------
# 4. RAG VECTOR STORE
# ----------------------------------------------------------
print()
print('[4] RAG VECTOR STORE')
from pathlib import Path
rag_files = {
    'tfidf_vectorizer.pkl': Path('backend/rag/store/tfidf_vectorizer.pkl'),
    'tfidf_matrix.pkl':     Path('backend/rag/store/tfidf_matrix.pkl'),
    'chunks.pkl':           Path('backend/rag/store/chunks.pkl'),
}
for name, fp in rag_files.items():
    if fp.exists():
        print('  OK   ', name, '(', fp.stat().st_size, 'bytes)')
        ok.append('RAG:' + name)
    else:
        print('  MISSING', name)
        issues.append('RAG: ' + name + ' not found - knowledge base not built')

# 4b. RAG retrieve test
try:
    from backend.rag.retriever import retrieve
    docs = retrieve('PM2.5 standard NAAQS', top_k=3)
    print('  OK   retrieve() returned', len(docs), 'docs')
    if len(docs) == 0:
        issues.append('RAG: retriever returns 0 docs - knowledge base may be empty')
except Exception as e:
    print('  FAIL retrieve():', str(e)[:100])
    issues.append('RAG retriever: ' + str(e)[:100])

# ----------------------------------------------------------
# 5. ML MODELS
# ----------------------------------------------------------
print()
print('[5] ML MODELS')
ml_dirs = {
    'Anomaly Detection': Path('backend/ml/anomaly_detection'),
    'Forecasting':       Path('backend/ml/forecasting'),
    'DBSCAN':            Path('backend/ml/dbscan'),
    'Explainability':    Path('backend/ml/explainability'),
}
for name, p in ml_dirs.items():
    if p.exists():
        model_files = (
            list(p.glob('*.pkl')) +
            list(p.glob('*.joblib')) +
            list(p.glob('*.json')) +
            list(p.glob('*.py'))
        )
        if model_files:
            print('  OK   ', name, '->', [f.name for f in model_files[:5]])
            ok.append('ML:' + name)
        else:
            print('  EMPTY', name, '- folder exists but no files')
            issues.append('ML: ' + name + ' folder is empty')
    else:
        print('  MISSING', name, '-', str(p))
        issues.append('ML: ' + name + ' directory missing')

# ----------------------------------------------------------
# 6. ORCHESTRATOR IMPORT
# ----------------------------------------------------------
print()
print('[6] ORCHESTRATOR')
try:
    from backend.agents.orchestrator import run_pipeline
    print('  OK   orchestrator imported successfully')
    ok.append('Orchestrator')
except Exception as e:
    print('  FAIL', e)
    issues.append('Orchestrator import: ' + str(e))

# ----------------------------------------------------------
# 7. run_ai.py - check error
# ----------------------------------------------------------
print()
print('[7] RUN_AI.PY EXIT CODE CHECK')
try:
    from backend.services.intent_router import classify_intent
    test_q = 'What is the live AQI of Pune?'
    intent = classify_intent(test_q)
    print('  OK   classify_intent ->', intent)
    ok.append('intent_router')
except Exception as e:
    print('  FAIL', e)
    issues.append('intent_router: ' + str(e))

# ----------------------------------------------------------
# SUMMARY
# ----------------------------------------------------------
print()
print('=' * 60)
print('SUMMARY:', len(ok), 'OK,', len(issues), 'ISSUES FOUND')
print('=' * 60)
for i, issue in enumerate(issues, 1):
    print()
    print(' [' + str(i) + ']', issue)
print()
