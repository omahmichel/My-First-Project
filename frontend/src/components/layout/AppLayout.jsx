import { NotificationActionsProvider } from "../notifications/NotificationRefresh";
import { AlertTriangle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  Link,
  Navigate,
  Outlet,
  useLocation,
} from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import { useStore } from "../../context/StoreContext";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

import "../../styles/subscription.css";
import "../../styles/sidebar-pages-polish.css";
import "../../styles/platform-scroll.css";

export default function AppLayout({ platform = false }) {
  const { user, isAuthenticated, isInitializing } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { business } = useStore();
  const location = useLocation();
  const contentRef = useRef(null);
  useEffect(() => {
    if (platform && contentRef.current) contentRef.current.scrollTop = 0;
  }, [platform, location.pathname]);
  const subscriptionPath = "/app/subscription";
  const supportPath = "/app/report-issue";
  const isBoutiqueBusiness = business.type === "boutique";
  const expiredWorkspaceAllowedPaths = new Set([
    subscriptionPath,
    supportPath,
  ]);

  if (platform && isInitializing) return <p role="status">Loading account…</p>;
  if (platform && !isAuthenticated) return <Navigate to="/admin-login" replace state={{from:location.pathname}}/>;
  if (platform && !user?.isPlatformAdmin) return <Navigate to="/businesses" replace />;
  if (!platform && user?.isPlatformAdmin) return <Navigate to="/platform-admin/overview" replace />;
  // Keeps expired workspaces limited to renewal and support.
  if (
    !platform && business.id &&
    !business.hasSystemAccess &&
    !expiredWorkspaceAllowedPaths.has(location.pathname)
  ) {
    return <Navigate to={subscriptionPath} replace />;
  }

  const showTrialReminder = !platform &&
    business.hasSystemAccess &&
    business.isTrialActive &&
    business.subscriptionReminderDue &&
    location.pathname !== subscriptionPath;

  return (
    <NotificationActionsProvider>
    <div
      className={`app-shell ${platform ? "platform-admin-shell" : ""} ${isBoutiqueBusiness ? "stockflow-boutique-app" : ""}`}
    >
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="app-main-column">
        <Topbar platform={platform} onOpenSidebar={() => setSidebarOpen(true)} />

        {showTrialReminder ? (
          <aside className="subscription-reminder" role="status">
            <span className="subscription-reminder-icon">
              <AlertTriangle size={20} />
            </span>

            <div>
              <strong>
                {Math.max(0, business.trialDaysRemaining)} trial day
                {business.trialDaysRemaining === 1 ? "" : "s"} remaining
              </strong>
              <p>
                Subscribe before the 60-day free trial ends to prevent
                interruption to this workspace.
              </p>
            </div>

            <Link to={subscriptionPath}>Review subscription</Link>
          </aside>
        ) : null}

        <main ref={contentRef} className="app-content" tabIndex={platform ? 0 : undefined} aria-label={platform ? "Administration page content" : undefined}>
          <Outlet />
        </main>
      </div>
    </div>
    </NotificationActionsProvider>
  );
}
