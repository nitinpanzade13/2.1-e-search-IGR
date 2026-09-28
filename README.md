# 2.1 e-search IGR

This project is a modern refactoring of the legacy IGR scraping script.

## Structure
- `backend/`: FastAPI + PostgreSQL backend.
- `frontend/`: React Native (Expo) TypeScript application.
- `2.1-script-main/`: Legacy reference codebase (DO NOT MODIFY).

## Getting Started

1. Set up the environment variables in `backend/.env`.
2. Start the services with Docker: `docker-compose up -d`
3. Start the frontend: `cd frontend && npm start`
