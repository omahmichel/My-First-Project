# StockFlow Frontend

A React + Vite frontend MVP for the Micro Inventory & Invoice Generator.

## Run the application

```bash
npm install
npm run dev
```

Open the URL shown by Vite, normally `http://localhost:5173`.

## Demo login

- Email: `owner@stockflow.demo`
- Password: `password123`

## Current frontend features

- Marketing landing page
- Registration and three-step business onboarding
- Protected application routes
- Responsive dashboard
- General product inventory
- Tile catalogue with design numbers, sizes, batches, boxes, pieces and coverage
- Boutique products with size and colour variants
- Stock movement history and manual adjustments
- Point-of-sale cart
- Cash, Mobile Money, bank transfer and credit sale options
- Automatic stock reduction after sales
- Invoice preview and printing
- Customer debt and repayments
- Reports, staff roles and business settings
- Browser local storage for temporary demo persistence

## Architecture note

`src/services/api.js` is reserved for the future Django REST Framework backend. The current demo data layer is isolated in `src/context/StoreContext.jsx` and `src/services/storage.js`, which makes the backend integration safer and more controlled.
