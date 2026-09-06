import {
  AlertTriangle,
  Boxes,
  CircleDollarSign,
  RefreshCw,
  SearchCheck,
  TrendingDown,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useStore } from "../../context/StoreContext";
import { apiRequest } from "../../services/api";
import {
  formatCurrency,
  formatDate,
  formatNumber,
  formatPercent,
  titleCase,
} from "./intelligenceUtils";


function InsightCard({
  icon: Icon,
  title,
  description,
  tone = "neutral",
  children,
}) {
  return (
    <article
      className={
        "intelligence-insight-card " +
        `intelligence-insight-${tone}`
      }
    >
      <div className="intelligence-insight-icon">
        <Icon size={21} />
      </div>
      <div>
        <span>{title}</span>
        <p>{description}</p>
        {children}
      </div>
    </article>
  );
}


export default function IntelligenceInsightsPage() {
  const { business } = useStore();
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadOverview = useCallback(async () => {
    if (!business.id) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await apiRequest(
        `/businesses/${business.id}/intelligence/overview/`,
      );
      setOverview(response);
    } catch (requestError) {
      setError(
        requestError.message ||
          "StockFlow could not load verified insight signals.",
      );
    } finally {
      setLoading(false);
    }
  }, [business.id]);

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  if (loading) {
    return (
      <div className="intelligence-state-card">
        <RefreshCw className="intelligence-spin" size={24} />
        <strong>Reading insight signals...</strong>
      </div>
    );
  }

  if (error || !overview) {
    return (
      <div className="intelligence-state-card intelligence-state-error">
        <AlertTriangle size={26} />
        <strong>Insights could not load</strong>
        <span>{error || "No verified overview was returned."}</span>
      </div>
    );
  }

  const products = overview.products || {};
  const overstock = overview.inventoryOverstock || {};
  const profitability = overview.productProfitability || {};
  const anomaly = overview.salesAnomaly || {};
  const debts = overview.debts || {};

  return (
    <div className="intelligence-page">
      <section className="intelligence-page-hero">
        <div>
          <span className="intelligence-eyebrow">
            <SearchCheck size={15} />
            Verified insight signals
          </span>
          <h2>Inspect the evidence behind important business changes.</h2>
          <p>
            This page groups stock, margin, anomaly and debt signals
            calculated by the backend.
          </p>
        </div>

        <button
          type="button"
          className="intelligence-primary-action"
          onClick={loadOverview}
        >
          <RefreshCw size={16} />
          Refresh signals
        </button>
      </section>

      <section className="intelligence-insights-grid">
        <InsightCard
          icon={Boxes}
          title="Stock-out risk"
          description={
            `${products.stockOutRisks?.length || 0} product(s) are ` +
            "inside the current verified risk window."
          }
          tone={
            products.stockOutRisks?.length ? "warning" : "good"
          }
        >
          <div className="intelligence-list">
            {(products.stockOutRisks || []).slice(0, 5).map((item) => (
              <div className="intelligence-list-row" key={item.productId}>
                <div>
                  <strong>{item.name}</strong>
                  <span>{item.sku}</span>
                </div>
                <div>
                  <strong>
                    {formatNumber(item.estimatedDaysRemaining, 1)} days
                  </strong>
                  <span>
                    {formatNumber(item.availableStock, 0)} available
                  </span>
                </div>
              </div>
            ))}
          </div>
        </InsightCard>

        <InsightCard
          icon={CircleDollarSign}
          title="Overstock cash exposure"
          description={
            `${overstock.candidateCount || 0} product(s) exceed the ` +
            "verified days-of-cover rule."
          }
          tone={overstock.candidateCount ? "warning" : "good"}
        >
          <strong className="intelligence-insight-big-value">
            {formatCurrency(overstock.totalExcessCostValue)}
          </strong>
          <span className="intelligence-insight-subtext">
            estimated cost value tied up in excess units
          </span>
        </InsightCard>

        <InsightCard
          icon={TrendingDown}
          title="Margin deterioration"
          description={
            `${profitability.marginDeterioration?.length || 0} product(s) ` +
            "have a lower margin than the previous comparison period."
          }
          tone={
            profitability.marginDeterioration?.length
              ? "warning"
              : "good"
          }
        >
          <div className="intelligence-list">
            {(profitability.marginDeterioration || [])
              .slice(0, 5)
              .map((item) => (
                <div
                  className="intelligence-list-row"
                  key={`${item.productId}-${item.sku}`}
                >
                  <div>
                    <strong>{item.name}</strong>
                    <span>{item.sku}</span>
                  </div>
                  <div>
                    <strong>{formatPercent(item.profitMargin)}</strong>
                    <span className="intelligence-negative">
                      {formatNumber(item.marginChangePoints, 2)} pp
                    </span>
                  </div>
                </div>
              ))}
          </div>
        </InsightCard>

        <InsightCard
          icon={AlertTriangle}
          title="Sales anomaly"
          description={
            anomaly.status === "anomaly"
              ? (
                  `${titleCase(anomaly.signalType)} detected for ` +
                  `${formatDate(anomaly.evaluatedDate)}.`
                )
              : "No eligible unusual completed-day revenue signal is active."
          }
          tone={anomaly.status === "anomaly" ? "danger" : "good"}
        >
          {anomaly.status === "anomaly" ? (
            <div className="intelligence-insight-evidence">
              <span>
                Current revenue{" "}
                <strong>{formatCurrency(anomaly.currentRevenue)}</strong>
              </span>
              <span>
                Baseline{" "}
                <strong>
                  {formatCurrency(anomaly.baselineAverageRevenue)}
                </strong>
              </span>
              <span>
                Change{" "}
                <strong>
                  {formatPercent(anomaly.percentageChange)}
                </strong>
              </span>
            </div>
          ) : null}
        </InsightCard>

        <InsightCard
          icon={CircleDollarSign}
          title="Outstanding debt"
          description="Verified receivables and supplier payables currently requiring management visibility."
          tone={
            Number(debts.customerDebt || 0) > 0 ||
            Number(debts.supplierDebt || 0) > 0
              ? "warning"
              : "good"
          }
        >
          <div className="intelligence-insight-evidence">
            <span>
              Customer debt{" "}
              <strong>{formatCurrency(debts.customerDebt)}</strong>
            </span>
            <span>
              Supplier debt{" "}
              <strong>{formatCurrency(debts.supplierDebt)}</strong>
            </span>
          </div>
        </InsightCard>
      </section>
    </div>
  );
}
