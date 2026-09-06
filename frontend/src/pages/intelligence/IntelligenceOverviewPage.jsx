import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Boxes,
  CircleDollarSign,
  Gauge,
  PackageSearch,
  RefreshCw,
  TrendingDown,
  WalletCards,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useStore } from "../../context/StoreContext";
import { apiRequest } from "../../services/api";
import {
  formatCurrency,
  formatDateTime,
  formatNumber,
  formatPercent,
  titleCase,
} from "./intelligenceUtils";


function StatusPill({ value, prefix = "" }) {
  const normalized = String(value || "low").toLowerCase();

  return (
    <span
      className={
        "intelligence-status-pill " +
        `intelligence-status-${normalized}`
      }
    >
      {prefix}
      {titleCase(normalized)}
    </span>
  );
}


function TrendPill({ direction, percentage }) {
  const Icon =
    direction === "down"
      ? ArrowDownRight
      : direction === "up"
        ? ArrowUpRight
        : BarChart3;

  return (
    <span
      className={
        "intelligence-trend-pill " +
        `intelligence-trend-${direction || "flat"}`
      }
    >
      <Icon size={14} />
      {titleCase(direction || "flat")}
      {percentage !== null &&
      percentage !== undefined ? (
        <b>{formatPercent(percentage)}</b>
      ) : null}
    </span>
  );
}


function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
  tone = "blue",
}) {
  return (
    <article
      className={
        "intelligence-metric-card " +
        `intelligence-metric-${tone}`
      }
    >
      <div className="intelligence-metric-icon">
        <Icon size={20} />
      </div>

      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </article>
  );
}


export default function IntelligenceOverviewPage() {
  const { business } = useStore();
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const loadOverview = useCallback(
    async ({ refresh = false } = {}) => {
      if (!business.id) {
        setLoading(false);
        return;
      }

      if (refresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setError("");

      try {
        const response = await apiRequest(
          `/businesses/${business.id}/intelligence/overview/`,
        );
        setOverview(response);
      } catch (requestError) {
        setError(
          requestError.message ||
            "StockFlow could not load the Intelligence overview.",
        );
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [business.id],
  );

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  if (loading) {
    return (
      <div className="intelligence-state-card">
        <RefreshCw className="intelligence-spin" size={25} />
        <strong>Reading verified business records...</strong>
        <span>
          StockFlow is calculating the latest business overview.
        </span>
      </div>
    );
  }

  if (error || !overview) {
    return (
      <div className="intelligence-state-card intelligence-state-error">
        <AlertTriangle size={27} />
        <strong>Overview could not load</strong>
        <span>{error || "No intelligence data was returned."}</span>
        <button type="button" onClick={() => loadOverview()}>
          Try again
        </button>
      </div>
    );
  }

  const health = overview.businessHealth || {};
  const confidence = overview.confidence || {};
  const inventory = overview.inventory || {};
  const debts = overview.debts || {};
  const performance = overview.performancePeriods || {};
  const products = overview.products || {};
  const overstock = overview.inventoryOverstock || {};
  const profitability = overview.productProfitability || {};
  const anomaly = overview.salesAnomaly || {};

  const periods = [
    ["Today", performance.today],
    ["Last 7 days", performance.last7Days],
    ["Last 30 days", performance.last30Days],
  ];

  return (
    <div className="intelligence-page">
      <section className="intelligence-page-hero">
        <div>
          <span className="intelligence-eyebrow">
            <Gauge size={15} />
            Verified overview
          </span>
          <h2>See what changed and what needs attention.</h2>
          <p>
            StockFlow is reading authoritative sales, inventory, debt
            and profitability records for{" "}
            <strong>{overview.businessName || business.name}</strong>.
          </p>

          <div className="intelligence-page-meta">
            <StatusPill
              value={confidence.grade}
              prefix="Data confidence: "
            />
            <span>
              Updated {formatDateTime(overview.generatedAt)}
            </span>
          </div>
        </div>

        <button
          type="button"
          className="intelligence-primary-action"
          onClick={() => loadOverview({ refresh: true })}
          disabled={refreshing}
        >
          <RefreshCw
            className={refreshing ? "intelligence-spin" : ""}
            size={16}
          />
          {refreshing ? "Refreshing..." : "Refresh overview"}
        </button>
      </section>

      <section
        className={
          "intelligence-health " +
          `intelligence-health-${health.status || "stable"}`
        }
      >
        <div>
          <span>Business health</span>
          <h3>{titleCase(health.status || "stable")}</h3>
        </div>

        <div>
          <strong>
            {health.attentionCount || 0} attention signal
            {health.attentionCount === 1 ? "" : "s"}
          </strong>

          {health.reasons?.length ? (
            <ul>
              {health.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : (
            <p>No verified attention signal is currently active.</p>
          )}
        </div>
      </section>

      <section className="intelligence-metric-grid">
        <MetricCard
          icon={CircleDollarSign}
          label="30-day revenue"
          value={formatCurrency(performance.last30Days?.revenue)}
          detail={
            performance.last30Days?.revenueChangePercentage !== null &&
            performance.last30Days?.revenueChangePercentage !== undefined
              ? (
                  `${formatPercent(
                    performance.last30Days.revenueChangePercentage,
                  )} vs previous period`
                )
              : "Previous comparison unavailable"
          }
          tone="blue"
        />

        <MetricCard
          icon={BarChart3}
          label="30-day gross profit"
          value={formatCurrency(
            performance.last30Days?.grossProfit,
          )}
          detail={`Margin ${formatPercent(
            performance.last30Days?.profitMargin,
          )}`}
          tone="green"
        />

        <MetricCard
          icon={Boxes}
          label="Inventory cost"
          value={formatCurrency(inventory.inventoryCostValue)}
          detail={`${formatNumber(
            inventory.availableStockUnits,
            0,
          )} available units`}
          tone="purple"
        />

        <MetricCard
          icon={PackageSearch}
          label="Low-stock products"
          value={formatNumber(inventory.lowStockCount, 0)}
          detail={`${products.stockOutRisks?.length || 0} stock-out risk(s)`}
          tone="amber"
        />

        <MetricCard
          icon={WalletCards}
          label="Customer debt"
          value={formatCurrency(debts.customerDebt)}
          detail={`${formatNumber(
            debts.customersWithDebt,
            0,
          )} customer(s) with debt`}
          tone="rose"
        />

        <MetricCard
          icon={TrendingDown}
          label="Supplier debt"
          value={formatCurrency(debts.supplierDebt)}
          detail={`${formatNumber(
            debts.supplierPurchasesWithBalance,
            0,
          )} purchase balance(s)`}
          tone="slate"
        />
      </section>

      <section className="intelligence-panel">
        <div className="intelligence-panel-heading">
          <div>
            <span>Performance</span>
            <h3>Revenue and profit movement</h3>
          </div>
          <small>Matching previous-period comparison</small>
        </div>

        <div className="intelligence-period-grid">
          {periods.map(([label, period]) => (
            <article className="intelligence-period-card" key={label}>
              <div>
                <span>{label}</span>
                <TrendPill
                  direction={period?.revenueDirection}
                  percentage={period?.revenueChangePercentage}
                />
              </div>

              <strong>{formatCurrency(period?.revenue)}</strong>

              <dl>
                <div>
                  <dt>Gross profit</dt>
                  <dd>{formatCurrency(period?.grossProfit)}</dd>
                </div>
                <div>
                  <dt>Margin</dt>
                  <dd>{formatPercent(period?.profitMargin)}</dd>
                </div>
                <div>
                  <dt>Sales</dt>
                  <dd>{formatNumber(period?.saleCount, 0)}</dd>
                </div>
                <div>
                  <dt>Units</dt>
                  <dd>{formatNumber(period?.unitsSold, 0)}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      </section>

      <section className="intelligence-split-grid">
        <article className="intelligence-panel">
          <div className="intelligence-panel-heading">
            <div>
              <span>Inventory intelligence</span>
              <h3>Risk and cash exposure</h3>
            </div>
          </div>

          <div className="intelligence-stat-row">
            <div>
              <span>Stock-out risks</span>
              <strong>{products.stockOutRisks?.length || 0}</strong>
            </div>
            <div>
              <span>Slow-moving</span>
              <strong>{products.slowMovingProducts?.length || 0}</strong>
            </div>
            <div>
              <span>Dead stock</span>
              <strong>{products.deadStockCandidates?.length || 0}</strong>
            </div>
            <div>
              <span>Overstock</span>
              <strong>{overstock.candidateCount || 0}</strong>
            </div>
          </div>

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

            {!products.stockOutRisks?.length ? (
              <p className="intelligence-muted">
                No current product is inside the verified stock-out risk
                window.
              </p>
            ) : null}
          </div>

          <div className="intelligence-cash-exposure">
            <span>Estimated overstock cash exposure</span>
            <strong>
              {formatCurrency(overstock.totalExcessCostValue)}
            </strong>
          </div>
        </article>

        <article className="intelligence-panel">
          <div className="intelligence-panel-heading">
            <div>
              <span>Margin and anomaly</span>
              <h3>Signals worth reviewing</h3>
            </div>
          </div>

          <div className="intelligence-list">
            {(profitability.marginDeterioration || [])
              .slice(0, 4)
              .map((item) => (
                <div
                  className="intelligence-list-row"
                  key={`${item.productId}-${item.sku}`}
                >
                  <div>
                    <strong>{item.name}</strong>
                    <span>Margin deterioration</span>
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

          <div
            className={
              "intelligence-anomaly " +
              (
                anomaly.status === "anomaly"
                  ? "intelligence-anomaly-alert"
                  : ""
              )
            }
          >
            <span>Latest sales anomaly check</span>
            <strong>
              {anomaly.status === "anomaly"
                ? titleCase(anomaly.signalType)
                : titleCase(anomaly.status || "not available")}
            </strong>
            <p>
              {anomaly.status === "anomaly"
                ? (
                    `Revenue changed ${formatPercent(
                      anomaly.percentageChange,
                    )} versus the verified same-weekday baseline.`
                  )
                : (
                    "StockFlow only flags unusual completed-day revenue when enough baseline evidence exists."
                  )}
            </p>
          </div>
        </article>
      </section>
    </div>
  );
}
