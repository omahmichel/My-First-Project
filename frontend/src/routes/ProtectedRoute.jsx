import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { useStore } from "../context/StoreContext";

export default function ProtectedRoute() {
  const { isAuthenticated, isInitializing } = useAuth();
  const { businessesLoading } = useStore();
  const location = useLocation();

  if (isInitializing || (isAuthenticated && businessesLoading)) {
    return (
      <main className="auth-page">
        <section className="auth-form-panel">
          <div className="auth-form-card">
            <p>Loading your StockFlow workspace...</p>
          </div>
        </section>
      </main>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
