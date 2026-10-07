import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../context/AuthContext";

export default function AccountLaneRoute({ lane }) {
  const { isAuthenticated, isInitializing, user } = useAuth();
  const location = useLocation();
  const adminLane = lane === "admin";

  if (isInitializing) {
    return (
      <main className="auth-page">
        <section className="auth-form-panel">
          <div className="auth-form-card">
            <p>Loading your StockFlow account...</p>
          </div>
        </section>
      </main>
    );
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to={adminLane ? "/admin-login" : "/login"}
        replace
        state={{ from: location.pathname }}
      />
    );
  }

  if (adminLane && !user?.isPlatformAdmin) {
    return <Navigate to="/businesses" replace />;
  }

  if (!adminLane && user?.isPlatformAdmin) {
    return <Navigate to="/platform-admin/overview" replace />;
  }

  return <Outlet />;
}
