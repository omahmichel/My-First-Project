# StockFlow — Micro Inventory & Invoice Generator

StockFlow is a full-stack inventory, sales, invoicing, receipt, waybill, customer, debt, reporting, and team-management system for Ghanaian building-materials shops and boutiques.

## Current stack

- Frontend: React 18 + Vite
- Backend: Django 6.0.7 + Django REST Framework
- Authentication: SimpleJWT with refresh-token rotation and blacklisting
- Development database: SQLite
- Currency: Ghana cedis only (GHS / GH₵ / ₵)

## Project folders

- `backend/` — Django API and business logic
- `frontend/` — React application
- `landing-page-static/` — standalone landing-page preview

## Current verified features

- Real registration and login
- Automatic access-token refresh
- Logout with refresh-token blacklisting
- Business workspace isolation
- Building-materials and boutique business types
- Real inventory APIs and tile-specific product fields
- Stock adjustments and stock-movement history
- Real customer records and debt-payment recording
- Real sales checkout with idempotency protection
- Invoices, receipts, persistent waybills, and purchase records
- Reports and statement exports
- Team-member creation and removal
- Owner and cashier permissions
- Business settings and onboarding
- API authentication rate limiting
- Environment-controlled production security settings
- Backend dependency locking through `backend/requirements.txt`

The project no longer uses frontend seed data or browser storage as a fake business database. Business records come from the Django API.

## Git workflow

Repository: `https://github.com/omahmichel/My-First-Project`

Branches:

- `main`
- `development`

Active development branch: `development`

Documentation baseline commit:

```text
3e4217a Update StockFlow project documentation
```

This commit records the verified project state when the handoff documentation was created.

Do not switch branches unless it is genuinely necessary.

## Backend setup

Open Windows CMD in the project root, then run:

```bat
cd backend
venv\Scripts\activate
python manage.py runserver
```

The backend normally runs at:

```text
http://127.0.0.1:8000/
```

The real environment file is `backend/.env` and must never be committed or shared. Use `backend/.env.example` only as a variable-name template.

## Frontend setup

Open a second Windows CMD terminal in the project root, then run:

```bat
cd frontend
npm install
npm run dev
```

The frontend normally runs at:

```text
http://localhost:5173/
```

There is no demo login. Create or use a real StockFlow account.

## Verification commands

After backend changes:

```bat
python manage.py check
python manage.py test
```

After frontend changes:

```bat
npm --prefix ..\frontend run build
```

Before committing:

```bat
git --no-pager status --short && git --no-pager diff --check && git --no-pager diff --stat
```

## Important development rules

- Preserve all working features.
- Work on one controlled step at a time.
- Back up files before modifying them.
- Add short, precise comments to new or modified code.
- Do not claim a change works until terminal tests or browser verification confirm it.
- Do not reintroduce demo data or local browser storage as the business database.

## Not yet implemented

The following were inspected but intentionally not started because they require coordinated architecture decisions:

- HttpOnly-cookie migration for refresh tokens
- Backend pagination for business collections
- Frontend Content Security Policy enforcement
- Final production hosting and domain configuration

These items must not be implemented casually because they can affect login, reports, totals, exports, checkout, CORS, and deployment.
