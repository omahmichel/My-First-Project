import {
  ArrowLeft,
  BarChart3,
  Bot,
  BrainCircuit,
  ChevronRight,
  Gauge,
  Lightbulb,
  Sparkles,
  WandSparkles,
  X,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { useStore } from "../../context/StoreContext";


const navigation = [
  {
    to: "/intelligence/overview",
    label: "Overview",
    icon: Gauge,
  },
  {
    to: "/intelligence/forecasts",
    label: "Forecasts",
    icon: BarChart3,
  },
  {
    to: "/intelligence/recommendations",
    label: "Stock Recommendations",
    icon: WandSparkles,
  },
  {
    to: "/intelligence/insights",
    label: "Insights",
    icon: Lightbulb,
  },
  {
    to: "/intelligence/ask",
    label: "Ask StockFlow",
    icon: Bot,
  },
  {
    to: "/intelligence/reports",
    label: "Intelligence Reports",
    icon: BrainCircuit,
  },
];

const comingSoon = [
  {
    label: "Automation",
    icon: Sparkles,
  },
];


export default function IntelligenceSidebar({ open, onClose }) {
  const { business } = useStore();

  return (
    <>
      <button
        type="button"
        className={
          "intelligence-sidebar-backdrop " +
          (open ? "intelligence-sidebar-backdrop-open" : "")
        }
        onClick={onClose}
        aria-label="Close Intelligence navigation"
      />

      <aside
        className={
          "intelligence-sidebar " +
          (open ? "intelligence-sidebar-open" : "")
        }
      >
        <div className="intelligence-sidebar-brand">
          <div className="intelligence-sidebar-brand-mark">
            <BrainCircuit size={23} />
          </div>

          <div>
            <strong>
              Stock<span>Flow</span>
            </strong>
            <small>Intelligence</small>
          </div>

          <button
            type="button"
            className="intelligence-sidebar-close"
            onClick={onClose}
            aria-label="Close Intelligence navigation"
          >
            <X size={19} />
          </button>
        </div>

        <div className="intelligence-sidebar-business">
          <span>Business workspace</span>
          <strong>{business.name || "StockFlow business"}</strong>
          <small>
            {business.currentUserRole
              ? business.currentUserRole.replaceAll("_", " ")
              : "Management"}
          </small>
        </div>

        <nav className="intelligence-sidebar-nav">
          <span className="intelligence-sidebar-section-label">
            Intelligence
          </span>

          {navigation.map((item) => {
            const Icon = item.icon;

            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onClose}
                className={({ isActive }) =>
                  (
                    "intelligence-sidebar-link " +
                    (isActive
                      ? "intelligence-sidebar-link-active"
                      : "")
                  ).trim()
                }
              >
                <Icon size={18} />
                <span>{item.label}</span>
                <ChevronRight size={15} />
              </NavLink>
            );
          })}

          <span className="intelligence-sidebar-section-label intelligence-sidebar-future-label">
            Coming later
          </span>

          {comingSoon.map((item) => {
            const Icon = item.icon;

            return (
              <div
                key={item.label}
                className="intelligence-sidebar-link intelligence-sidebar-link-disabled"
              >
                <Icon size={18} />
                <span>{item.label}</span>
                <small>Soon</small>
              </div>
            );
          })}
        </nav>

        <div className="intelligence-sidebar-footer">
          <NavLink to="/app/dashboard" className="intelligence-back-link">
            <ArrowLeft size={17} />
            <span>Back to StockFlow</span>
          </NavLink>

          <p>
            Django calculates the truth. Intelligence explains the
            evidence and keeps you in control.
          </p>
        </div>
      </aside>
    </>
  );
}
