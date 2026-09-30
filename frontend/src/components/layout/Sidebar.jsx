import {
  Activity, Bell, ShieldPlus,
  BarChart3,
  BrainCircuit,
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
  Smartphone,
  Sparkles,
  Car,
  Zap,
  Users,
  X,
} from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import { useStore } from "../../context/StoreContext";
import { businessTypeLabel } from "../../data/businessTypes";

import "../../styles/sidebar-business-switcher.css";
import "../../styles/sidebar-sections.css";

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
  provision_mini_mart: {
    to: "/app/provision-mini-mart",
    label: "Provision inventory",
    icon: Boxes,
  },
  phone_electronics_accessories: {
    to: "/app/phone-accessories",
    label: "Phone & accessories",
    icon: Smartphone,
  },
  electrical_electronics: {
    to: "/app/electrical-electronics",
    label: "Electrical inventory",
    icon: Zap,
  },
  auto_spare_parts: {
    to: "/app/auto-spare-parts",
    label: "Spare parts inventory",
    icon: Car,
  },
  cosmetics_beauty: {
    to: "/app/cosmetics-beauty",
    label: "Beauty inventory",
    icon: Sparkles,
  },
};

export default function Sidebar({ open, onClose }) {
  const { logout, user } = useAuth();
  const {
    business,
    businesses,
    activeBusinessId,
    switchBusiness,
    branch,
    branches,
    activeBranchId,
    branchesLoading,
    switchBranch,
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

  function handleBranchSwitch(event) {
    switchBranch(event.target.value);
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
  const navigation = !business.id ? [] : business.hasSystemAccess
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
          <NavLink to={business.id ? "/app/dashboard" : "/businesses"} className="app-brand" onClick={onClose}>
            <span className="app-brand-mark">S</span>
            <span>
              Stock<strong>Flow</strong>
            </span>
          </NavLink>

          <button type="button" className="sidebar-close-button" onClick={onClose}>
            <X size={21} />
          </button>
        </div>

        {business.id && <div className="sidebar-business-card sidebar-business-switcher">
          <div className="sidebar-business-switcher-heading">
            <span className="sidebar-business-switcher-icon">
              <Building2 size={16} />
            </span>

            <div>
              <span>Current workspace</span>
              <small>{businessTypeLabel(business.type)}</small>
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

          <label className="sidebar-business-select-label">
            <span className="sr-only">Switch branch</span>
            <select
              value={activeBranchId}
              onChange={handleBranchSwitch}
              aria-label="Switch active branch"
              disabled={branchesLoading || !branches.length}
            >
              {branches.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name}{item.isMain ? " · Main" : ""}
                </option>
              ))}
            </select>
          </label>

          <p>
            Showing <strong>{branch?.name || "branch"}</strong> records for{" "}
            <strong>{business.name}</strong>
          </p>
        </div>

        }
        <nav className="sidebar-nav">
          <section className="sidebar-business-navigation" aria-label="Business workspace">
          <p className="sidebar-group-title">Business workspace</p>
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

          {!business.id && <p className="sidebar-workspace-help">Choose an authorised workspace from My businesses to open stock, sales and reports.</p>}

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

          {business.id && business.hasSystemAccess && business.currentUserRole === "owner" ? (
            <NavLink to="/app/online-shop" onClick={onClose} className={({ isActive }) => isActive ? "sidebar-link sidebar-link-active" : "sidebar-link"}>
              <ShoppingCart size={19} /><span>Online shop</span>
            </NavLink>
          ) : null}

          {business.id && business.hasSystemAccess &&
          ["owner", "manager"].includes(business.currentUserRole) ? (
            <NavLink
              to="/intelligence/overview"
              onClick={onClose}
              className={({ isActive }) =>
                `sidebar-link ${isActive ? "sidebar-link-active" : ""}`
              }
            >
              <BrainCircuit size={19} />
              <span>Intelligence</span>
            </NavLink>
          ) : null}
          </section>
          {user?.isPlatformAdmin && <section className="sidebar-administration" aria-label="Administration">
            <p className="sidebar-group-title">Administration</p>
            {[["overview","Overview",LayoutDashboard],["users","Users",Users],["businesses","Businesses",Building2],["subscriptions","Subscriptions",CreditCard],["administrators","Add Admin",ShieldPlus],["bugs","Bugs",Bug],["activity","Activity log",Activity],["notifications","Notifications",Bell]].map(([key,label,Icon]) => <NavLink key={key} to={`/platform-admin/${key}`} onClick={onClose} className={({isActive})=>`sidebar-link ${isActive ? "sidebar-link-active" : ""}`}><Icon size={19}/><span>{label}</span></NavLink>)}
          </section>}
        </nav>

        <button type="button" className="sidebar-logout" onClick={handleLogout}>
          <LogOut size={19} />
          Log out
        </button>
      </aside>
    </>
  );
}
