# Frontend architecture

## Public area

- Landing page
- Login
- Registration
- Business onboarding

## Protected application

- Dashboard
- All products
- Tile inventory
- Boutique stock
- New sale
- Sales history
- Invoices
- Customers and debt
- Stock movements
- Reports
- Team members
- Settings

## State and service separation

- `src/context/AuthContext.jsx` manages temporary frontend authentication.
- `src/context/StoreContext.jsx` manages demo business data and workflows.
- `src/services/storage.js` contains local persistence.
- `src/services/api.js` is reserved for Django REST API integration.
- `src/data/seedData.js` contains the initial demonstration records.

## Important business rules already represented

- Normal sales cannot reduce stock below zero.
- Credit sales require an identified customer.
- Customer payment cannot exceed outstanding debt.
- Every stock adjustment creates a movement record.
- Completed sales preserve their item prices and cost prices.
- Tile products support design codes, batch numbers, box stock, loose pieces and square-metre coverage.
- Boutique products support style codes and visible size/colour variants.
