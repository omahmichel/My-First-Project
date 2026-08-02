import { Navigate, Route, Routes } from "react-router-dom";

import AppLayout from "./components/layout/AppLayout";
import ProtectedRoute from "./routes/ProtectedRoute";
import IndustryRoute from "./routes/IndustryRoute";
import LandingPage from "./pages/public/LandingPage";
import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";
import OnboardingPage from "./pages/onboarding/OnboardingPage";
import DashboardPage from "./pages/dashboard/DashboardPage";
import ProductsPage from "./pages/inventory/ProductsPage";
import TilesPage from "./pages/inventory/TilesPage";
import BoutiquePage from "./pages/inventory/BoutiquePage";
import StockMovementsPage from "./pages/inventory/StockMovementsPage";
import NewSalePage from "./pages/sales/NewSalePage";
import SalesHistoryPage from "./pages/sales/SalesHistoryPage";
import InvoicesPage from "./pages/invoices/InvoicesPage";
import CustomersPage from "./pages/customers/CustomersPage";
import CustomerPurchaseRecordsPage from "./pages/customers/CustomerPurchaseRecordsPage";
import ReportsPage from "./pages/reports/ReportsPage";
import TeamPage from "./pages/team/TeamPage";
import SettingsPage from "./pages/settings/SettingsPage";
import SubscriptionPage from "./pages/settings/SubscriptionPage";
import NotFoundPage from "./pages/NotFoundPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/onboarding" element={<OnboardingPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="products" element={<ProductsPage />} />

          <Route
            element={
              <IndustryRoute allowedBusinessTypes={["building_materials"]} />
            }
          >
            <Route path="tiles" element={<TilesPage />} />
          </Route>

          <Route
            element={<IndustryRoute allowedBusinessTypes={["boutique"]} />}
          >
            <Route path="boutique" element={<BoutiquePage />} />
          </Route>

          <Route path="stock-movements" element={<StockMovementsPage />} />
          <Route path="new-sale" element={<NewSalePage />} />
          <Route path="sales" element={<SalesHistoryPage />} />
          <Route path="invoices" element={<InvoicesPage />} />
          <Route path="customers" element={<CustomersPage />} />
          <Route path="purchases" element={<CustomerPurchaseRecordsPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="team" element={<TeamPage />} />
          <Route path="subscription" element={<SubscriptionPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}