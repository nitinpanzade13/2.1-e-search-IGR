# API Architecture: e-Search IGR

This document describes the API and Frontend architecture connecting the Stage 1 backend to the React Native Expo app.

## High-Level Architecture

```mermaid
graph TD
    A[React Native Expo (Web/Mobile)] -->|HTTP GET/POST| B(FastAPI Server)
    B -->|SQLAlchemy| C[(PostgreSQL: esearch_igr)]
    B -->|BackgroundTasks| D[SearchWorker]
    D -->|HTTP Request| E[IGR Source System]
    D -->|PostgreSQL| C
```

## Demo Mode

To allow frontend development without consuming daily IGR scraper quotas, the API supports a **Demo Mode**. 
- Enabled by setting `SCRAPER_TEST_MODE = True` in `backend/app/core/config.py` (or `.env`).
- When active, `POST /api/v1/search` intercepts the scraper worker. Instead of fetching from IGR, it instantly sets the Job Status to `COMPLETED`.
- `GET /api/v1/search/{job_id}/results` returns static JSON demo data bypassing the database. 
- **Database Safety**: Demo records are intentionally NOT written to PostgreSQL to prevent polluting production metrics.

## REST Endpoints (`/api/v1`)

- `GET /health` - Service health
- `GET /locations/districts` - Active districts
- `GET /locations/districts/{id}/talukas` - Active talukas
- `GET /locations/talukas/{id}/villages` - Active villages
- `GET /offices` - Configured offices
- `POST /search` - Submit an async IGR search job
- `GET /search/{id}` - Poll for job completion status (`QUEUED`, `RUNNING`, `COMPLETED`, `RATE_LIMITED`)
- `GET /search/{id}/results` - Fetch retrieved Registrations
- `GET /registrations/{id}` - Document overview
- `GET /registrations/{id}/parties` - Sellers and buyers
- `GET /registrations/{id}/properties` - Real estate assets

## Startup Instructions

**Start the Backend**:
```bash
cd backend
./venv/Scripts/Activate.ps1
uvicorn app.main:app --reload
```
Swagger UI will be available at `http://127.0.0.1:8000/docs`

**Start the Frontend**:
```bash
cd frontend
npm start
# Or to run on web specifically:
npm run web
```
The React Native frontend will open in your browser or simulator.
