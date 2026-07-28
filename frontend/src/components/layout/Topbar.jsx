import { Bell, Menu, Search } from "lucide-react";
import { useLocation } from "react-router-dom";

import { useAuth } from "../../context/AuthContext";
import { useStore } from "../../context/StoreContext";

const titles = {
  "/app/dashboard": "Dashboard",
  "/app/products": "Products",
  "/app/tiles": "Tile inventory",
  "/app/boutique": "Boutique inventory",
  "/app/new-sale": "New sale",
  "/app/sales": "Sales history",
  "/app/invoices": "Invoices",
  "/app/customers": "Customers",
  "/app/stock-movements": "Stock movements",
  "/app/reports": "Reports",
  "/app/team": "Team",
  "/app/settings": "Settings",
};

export default function Topbar({ onOpenSidebar }) {
  const { user } = useAuth();
  const { business } = useStore();
  const location = useLocation();
  const title = titles[location.pathname] ?? "StockFlow";

  return (
    <header className="app-topbar">
      <div className="topbar-left">
        <button type="button" className="topbar-menu-button" onClick={onOpenSidebar}>
          <Menu size={22} />
        </button>
        <div>
          <span>Workspace</span>
          <strong>{title}</strong>
        </div>
      </div>

      <div className="topbar-actions">
        <div className="topbar-search">
          <Search size={18} />
          <input type="search" placeholder="Search records..." aria-label="Search records" />
        </div>

        <button type="button" className="topbar-icon-button" aria-label="Notifications">
          <Bell size={20} />
          <span className="notification-dot" />
        </button>

        <div className="topbar-user">
          <div className="topbar-avatar">{user?.name?.slice(0, 2).toUpperCase() ?? "BO"}</div>
          <div>
            <strong>{user?.name ?? "Business Owner"}</strong>
            <span>{business?.currentUserRole ?? user?.role ?? "account"}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
