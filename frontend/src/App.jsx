import { Navigate, Route, Routes } from "react-router-dom";

import AppLayout from "./components/layout/AppLayout";
import IntelligenceLayout from "./components/intelligence/IntelligenceLayout";
import ProtectedRoute from "./routes/ProtectedRoute";
import IndustryRoute from "./routes/IndustryRoute";
import RoleRoute from "./routes/RoleRoute";
import LandingPage from "./pages/public/LandingPage";
import LoginPage from "./pages/auth/LoginPage";
import LoginOTPPage from "./pages/auth/LoginOTPPage";
import ForgotPasswordPage from "./pages/auth/ForgotPasswordPage";
import ResetPasswordPage from "./pages/auth/ResetPasswordPage";
import RegisterPage from "./pages/auth/RegisterPage";
import RegistrationOTPPage from "./pages/auth/RegistrationOTPPage";
import OnboardingPage from "./pages/onboarding/OnboardingPage";
import MyBusinessesPage from "./pages/businesses/MyBusinessesPage";
import DashboardPage from "./pages/dashboard/DashboardPage";
import ProductsPage from "./pages/inventory/ProductsPage";
import TilesPage from "./pages/inventory/TilesPage";
import BoutiquePage from "./pages/inventory/BoutiquePage";
import StockMovementsPage from "./pages/inventory/StockMovementsPage";
import RestockingPage from "./pages/inventory/RestockingPage";
import NewSalePage from "./pages/sales/NewSalePage";
import SalesHistoryPage from "./pages/sales/SalesHistoryPage";
import InvoicesPage from "./pages/invoices/InvoicesPage";
import CustomersPage from "./pages/customers/CustomersPage";
import CustomerPurchaseRecordsPage from "./pages/customers/CustomerPurchaseRecordsPage";
import IntelligenceOverviewPage from "./pages/intelligence/IntelligenceOverviewPage";
import IntelligenceForecastsPage from "./pages/intelligence/IntelligenceForecastsPage";
import IntelligenceRecommendationsPage from "./pages/intelligence/IntelligenceRecommendationsPage";
import IntelligenceInsightsPage from "./pages/intelligence/IntelligenceInsightsPage";
import IntelligenceAskPage from "./pages/intelligence/IntelligenceAskPage";
import IntelligenceReportsPage from "./pages/intelligence/IntelligenceReportsPage";
import IntelligenceAutomationPage from "./pages/intelligence/IntelligenceAutomationPage";
import ReportsPage from "./pages/reports/ReportsPage";
import TeamPage from "./pages/team/TeamPage";
import SettingsPage from "./pages/settings/SettingsPage";
import SubscriptionPage from "./pages/settings/SubscriptionPage";
import ReportIssuePage from "./pages/support/ReportIssuePage";
import NotFoundPage from "./pages/NotFoundPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/verify-login" element={<LoginOTPPage />} />
      <Route
        path="/forgot-password"
        element={<ForgotPasswordPage />}
      />
      <Route
        path="/reset-password"
        element={<ResetPasswordPage />}
      />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/verify-registration"
        element={<RegistrationOTPPage />}
      />
      <Route path="/onboarding" element={<OnboardingPage />} />

      <Route element={<ProtectedRoute />}>
        {/* Account-level home for only the businesses this user can access. */}
        <Route path="/businesses" element={<MyBusinessesPage />} />

        <Route
          element={
            <RoleRoute
              allowedRoles={["owner", "manager"]}
              areaLabel="StockFlow Intelligence"
            />
          }
        >
          <Route path="/intelligence" element={<IntelligenceLayout />}>
            <Route index element={<Navigate to="overview" replace />} />
            <Route
              path="overview"
              element={<IntelligenceOverviewPage />}
            />
            <Route
              path="forecasts"
              element={<IntelligenceForecastsPage />}
            />
            <Route
              path="recommendations"
              element={<IntelligenceRecommendationsPage />}
            />
            <Route
              path="insights"
              element={<IntelligenceInsightsPage />}
            />
            <Route
              path="ask"
              element={<IntelligenceAskPage />}
            />
            <Route
              path="reports"
              element={<IntelligenceReportsPage />}
            />
            <Route
              path="automation"
              element={<IntelligenceAutomationPage />}
            />
          </Route>
        </Route>

        <Route path="/app" element={<AppLayout />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />

          <Route
            element={
              <RoleRoute
                allowedRoles={["owner", "manager", "inventory_clerk"]}
                areaLabel="inventory"
              />
            }
          >
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
            <Route path="restocking" element={<RestockingPage />} />
          </Route>

          <Route
            element={
              <RoleRoute
                allowedRoles={["owner", "manager", "cashier"]}
                areaLabel="sales and customer records"
              />
            }
          >
            <Route path="new-sale" element={<NewSalePage />} />
            <Route path="sales" element={<SalesHistoryPage />} />
            <Route path="invoices" element={<InvoicesPage />} />
            <Route path="customers" element={<CustomersPage />} />
            <Route path="purchases" element={<CustomerPurchaseRecordsPage />} />
          </Route>

          <Route
            element={
              <RoleRoute
                allowedRoles={["owner", "manager"]}
                areaLabel="management"
              />
            }
          >
            <Route path="reports" element={<ReportsPage />} />
            <Route path="team" element={<TeamPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>

          <Route path="report-issue" element={<ReportIssuePage />} />
          <Route path="subscription" element={<SubscriptionPage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}