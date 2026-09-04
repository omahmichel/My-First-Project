import {
  BarChart3,
  Building2,
  Bug,
  Boxes,
  CircleDollarSign,
  ClipboardList,
  CreditCard,
  FileText,
  LayoutDashboard,
  LogOut,
  PackagePlus,
  PackageSearch,
  ReceiptText,
  Settings,
  Shirt,
  ShoppingCart,
  Users,
  X,
} from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import { useStore } from "../../context/StoreContext";

import "../../styles/sidebar-business-switcher.css";

const commonNavigation = [
  { to: "/app/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/app/products", label: "All products", icon: Boxes },
  { to: "/app/new-sale", label: "New sale", icon: ShoppingCart },
  { to: "/app/sales", label: "Sales history", icon: CircleDollarSign },
  { to: "/app/invoices", label: "Invoices", icon: ReceiptText },
  { to: "/app/purchases", label: "Purchase records", icon: ClipboardList },
  { to: "/app/customers", label: "Customers", icon: Users },
  { to: "/app/stock-movements", label: "Stock movements", icon: FileText },
  { to: "/app/restocking", label: "Restocking", icon: PackagePlus },
  { to: "/app/reports", label: "Reports", icon: BarChart3 },
  { to: "/app/team", label: "Team", icon: Users },
  { to: "/app/report-issue", label: "Report an issue", icon: Bug },
  { to: "/app/subscription", label: "Subscription", icon: CreditCard },
  { to: "/app/settings", label: "Settings", icon: Settings },
];

const industryNavigation = {
  building_materials: {
    to: "/app/tiles",
    label: "Tile inventory",
    icon: PackageSearch,
  },
  boutique: {
    to: "/app/boutique",
    label: "Boutique inventory",
    icon: Shirt,
  },
};

export default function Sidebar({ open, onClose }) {
  const { logout } = useAuth();
  const {
    business,
    businesses,
    activeBusinessId,
    switchBusiness,
  } = useStore();
  const navigate = useNavigate();

  // Logs out through Django, clears JWT tokens and returns to Login.
  async function handleLogout() {
    await logout();
    onClose();
    navigate("/login", { replace: true });
  }

  // Switches the complete workspace and returns to a safe shared route.
  function handleBusinessSwitch(event) {
    switchBusiness(event.target.value);
    navigate("/app/dashboard", { replace: true });
    onClose();
  }

  // Insert only the inventory page that belongs to the current business type.
  const currentIndustryNavigation = industryNavigation[business.type];
  const fullNavigation = [
    ...commonNavigation.slice(0, 2),
    ...(currentIndustryNavigation ? [currentIndustryNavigation] : []),
    ...commonNavigation.slice(2),
  ];

  // Expired workspaces keep renewal and support available.
  const expiredWorkspacePaths = new Set([
    "/app/subscription",
    "/app/report-issue",
  ]);
  const navigation = business.hasSystemAccess
    ? fullNavigation
    : fullNavigation.filter(
        (item) => expiredWorkspacePaths.has(item.to),
      );

  return (
    <>
      <div
        className={`sidebar-overlay ${open ? "sidebar-overlay-visible" : ""}`}
        onClick={onClose}
      />

      <aside className={`app-sidebar ${open ? "app-sidebar-open" : ""}`}>
        <div className="sidebar-brand-row">
          <NavLink to="/app/dashboard" className="app-brand" onClick={onClose}>
            <span className="app-brand-mark">S</span>
            <span>
              Stock<strong>Flow</strong>
            </span>
          </NavLink>

          <button type="button" className="sidebar-close-button" onClick={onClose}>
            <X size={21} />
          </button>
        </div>

        <div className="sidebar-business-card sidebar-business-switcher">
          <div className="sidebar-business-switcher-heading">
            <span className="sidebar-business-switcher-icon">
              <Building2 size={16} />
            </span>

            <div>
              <span>Current workspace</span>
              <small>
                {business.type === "boutique"
                  ? "Boutique"
                  : "Building materials"}
              </small>
            </div>
          </div>

          <label className="sidebar-business-select-label">
            <span className="sr-only">Switch business</span>
            <select
              value={activeBusinessId}
              onChange={handleBusinessSwitch}
              aria-label="Switch active business"
            >
              {businesses.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>

          <p>
            Showing records for <strong>{business.name}</strong>
          </p>
        </div>

        <nav className="sidebar-nav">
          {/* Always lets the account return to its authorized business list. */}
          <NavLink
            to="/businesses"
            onClick={onClose}
            className={({ isActive }) =>
              `sidebar-link ${isActive ? "sidebar-link-active" : ""}`
            }
          >
            <Building2 size={19} />
            <span>My businesses</span>
          </NavLink>

          {navigation.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onClose}
              className={({ isActive }) =>
                `sidebar-link ${isActive ? "sidebar-link-active" : ""}`
              }
            >
              <Icon size={19} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <button type="button" className="sidebar-logout" onClick={handleLogout}>
          <LogOut size={19} />
          Log out
        </button>
      </aside>
    </>
  );
}