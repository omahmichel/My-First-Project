import { AlertTriangle } from "lucide-react";
import { useState } from "react";
import {
  Link,
  Navigate,
  Outlet,
  useLocation,
} from "react-router-dom";

import { useStore } from "../../context/StoreContext";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

import "../../styles/subscription.css";
import "../../styles/sidebar-pages-polish.css";

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { business } = useStore();
  const location = useLocation();
  const subscriptionPath = "/app/subscription";

  // Keeps expired workspaces inside the subscription renewal area.
  if (
    business.id &&
    !business.hasSystemAccess &&
    location.pathname !== subscriptionPath
  ) {
    return <Navigate to={subscriptionPath} replace />;
  }

  const showTrialReminder =
    business.hasSystemAccess &&
    business.isTrialActive &&
    business.subscriptionReminderDue &&
    location.pathname !== subscriptionPath;

  return (
    <div className="app-shell">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="app-main-column">
        <Topbar onOpenSidebar={() => setSidebarOpen(true)} />

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

        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
