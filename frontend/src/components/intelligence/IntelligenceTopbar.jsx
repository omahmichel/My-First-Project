import {
  Bell,
  Menu,
  ShieldCheck,
} from "lucide-react";
import { useLocation } from "react-router-dom";

import { useStore } from "../../context/StoreContext";


const pageTitles = {
  "/intelligence/overview": "Overview",
  "/intelligence/forecasts": "Forecasts",
  "/intelligence/recommendations": "Stock Recommendations",
  "/intelligence/insights": "Insights",
  "/intelligence/ask": "Ask StockFlow",
  "/intelligence/reports": "Intelligence Reports",
};


export default function IntelligenceTopbar({ onOpenSidebar }) {
  const location = useLocation();
  const { business } = useStore();

  const title =
    pageTitles[location.pathname] ||
    "StockFlow Intelligence";

  return (
    <header className="intelligence-topbar">
      <div className="intelligence-topbar-left">
        <button
          type="button"
          className="intelligence-mobile-menu"
          onClick={onOpenSidebar}
          aria-label="Open Intelligence navigation"
        >
          <Menu size={20} />
        </button>

        <div>
          <span>StockFlow Intelligence</span>
          <h1>{title}</h1>
        </div>
      </div>

      <div className="intelligence-topbar-right">
        <div className="intelligence-topbar-security">
          <ShieldCheck size={16} />
          <span>Verified business data</span>
        </div>

        <button
          type="button"
          className="intelligence-topbar-icon"
          aria-label="Intelligence notifications"
          disabled
        >
          <Bell size={18} />
        </button>

        <div className="intelligence-topbar-business">
          <span>{business.name || "Business"}</span>
          <small>
            {business.currentUserRole
              ? business.currentUserRole.replaceAll("_", " ")
              : "Management"}
          </small>
        </div>
      </div>
    </header>
  );
}
