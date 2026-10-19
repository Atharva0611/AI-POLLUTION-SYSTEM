from fastapi import FastAPI

app = FastAPI(title='AI Pollution System API')

@app.get('/')
def root():
    return {'message': 'AI Pollution System API'}
