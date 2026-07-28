# Micro Inventory & Invoice Generator

This workspace currently contains the first frontend delivery for the project.

## Folders

- `landing-page-static/` — standalone HTML landing page preview.
- `frontend/` — React + Vite application for the full frontend MVP.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal, usually `http://localhost:5173`.

## Demo login

- Email: `owner@stockflow.demo`
- Password: `password123`

The frontend currently uses browser local storage as a temporary demo database. It is structured so the local service can later be replaced by Django REST API calls.
