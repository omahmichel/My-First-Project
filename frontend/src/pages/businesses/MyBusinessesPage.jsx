import {
  ArrowRight,
  Building2,
  LogOut,
  MapPin,
  Plus,
  RefreshCw,
  ShieldCheck,
  Store,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import Button from "../../components/ui/Button";
import { useAuth } from "../../context/AuthContext";
import { useStore } from "../../context/StoreContext";

import "../../styles/business-workspaces.css";


function businessTypeLabel(type) {
  if (type === "boutique") return "Boutique";
  if (type === "building_materials") return "Building materials";
  return "Business";
}


function subscriptionLabel(business) {
  if (business.hasActiveSubscription) {
    return "Active subscription";
  }

  if (business.isTrialActive) {
    const days = Math.max(0, Number(business.trialDaysRemaining ?? 0));
    return `${days} trial day${days === 1 ? "" : "s"} remaining`;
  }

  return "Subscription required";
}


export default function MyBusinessesPage() {
  const { user, logout } = useAuth();
  const {
    businesses,
    businessesError,
    businessesLoading,
    loadBusinesses,
    switchBusiness,
  } = useStore();
  const navigate = useNavigate();

  function openBusiness(businessId) {
    // Activates only a business already returned for this authenticated user.
    switchBusiness(businessId);
    navigate("/app/dashboard");
  }

  function addBusiness() {
    // Reuses the existing secure onboarding flow for another owned workspace.
    navigate("/onboarding");
  }

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <main className="business-workspaces-page">
      <header className="business-workspaces-topbar">
        <button
          type="button"
          className="business-workspaces-brand"
          onClick={() => navigate("/businesses")}
          aria-label="StockFlow business home"
        >
          <span>S</span>
          <strong>
            Stock<b>Flow</b>
          </strong>
        </button>

        <div className="business-workspaces-account">
          <div>
            <span>Signed in as</span>
            <strong>{user?.name ?? user?.email ?? "StockFlow account"}</strong>
          </div>

          <button
            type="button"
            className="business-workspaces-logout"
            onClick={handleLogout}
          >
            <LogOut size={17} />
            Log out
          </button>
        </div>
      </header>

      <section className="business-workspaces-shell">
        <div className="business-workspaces-heading">
          <div>
            <span className="business-workspaces-eyebrow">
              <ShieldCheck size={16} />
              Your StockFlow account
            </span>
            <h1>My businesses</h1>
            <p>
              Choose a business to open its private workspace. Inventory,
              customers, sales, reports, settings and subscription access stay
              separate for every business.
            </p>
          </div>

          <Button onClick={addBusiness}>
            <Plus size={18} />
            Add another business
          </Button>
        </div>

        {businessesError ? (
          <div className="business-workspaces-error" role="alert">
            <div>
              <strong>We could not load your businesses.</strong>
              <span>{businessesError}</span>
            </div>

            <button
              type="button"
              onClick={() => loadBusinesses()}
              disabled={businessesLoading}
            >
              <RefreshCw size={16} />
              {businessesLoading ? "Refreshing..." : "Try again"}
            </button>
          </div>
        ) : null}

        {!businessesLoading && businesses.length === 0 ? (
          <section className="business-workspaces-empty">
            <span className="business-workspaces-empty-icon">
              <Store size={28} />
            </span>
            <h2>Create your first business workspace</h2>
            <p>
              This account does not have a business yet. Set up a workspace to
              start managing stock, customers and sales.
            </p>
            <Button onClick={addBusiness}>
              <Plus size={18} />
              Create business
            </Button>
          </section>
        ) : null}

        {businesses.length > 0 ? (
          <div className="business-workspaces-grid">
            {businesses.map((business) => (
              <article className="business-workspace-card" key={business.id}>
                <div className="business-workspace-card-head">
                  <span className="business-workspace-icon">
                    <Building2 size={22} />
                  </span>

                  <div className="business-workspace-badges">
                    <span>{businessTypeLabel(business.type)}</span>
                    <span
                      className={
                        business.hasSystemAccess
                          ? "business-workspace-access-active"
                          : "business-workspace-access-blocked"
                      }
                    >
                      {subscriptionLabel(business)}
                    </span>
                  </div>
                </div>

                <div className="business-workspace-details">
                  <h2>{business.name}</h2>
                  <p>
                    <MapPin size={15} />
                    <span>
                      {business.location || "No business location added yet"}
                    </span>
                  </p>
                </div>

                <div className="business-workspace-meta">
                  <div>
                    <span>Your role</span>
                    <strong>{business.currentUserRole || "account"}</strong>
                  </div>
                  <div>
                    <span>Team members</span>
                    <strong>{business.activeTeamMembers ?? 0}</strong>
                  </div>
                </div>

                <button
                  type="button"
                  className="business-workspace-open"
                  onClick={() => openBusiness(business.id)}
                >
                  <span>
                    {business.hasSystemAccess
                      ? "Open business"
                      : "Review business"}
                  </span>
                  <ArrowRight size={18} />
                </button>
              </article>
            ))}
          </div>
        ) : null}
      </section>
    </main>
  );
}
