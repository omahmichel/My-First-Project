import {
  BarChart3,
  CalendarDays,
  Download,
  PieChart,
  TrendingUp,
} from "lucide-react";
import { useMemo, useState } from "react";

import Button from "../../components/ui/Button";
import PageHeader from "../../components/ui/PageHeader";
import StatCard from "../../components/ui/StatCard";
import { useStore } from "../../context/StoreContext";
import { formatCurrency } from "../../utils/formatters";
import { exportBusinessReportCsv } from "../../utils/reportExport";

import "../../styles/invoice-document-actions.css";

const RANGE_LABELS = {
  7: "Last 7 days",
  30: "Last 30 days",
  90: "Last 90 days",
  365: "Last 12 months",
};

export default function ReportsPage() {
  const {
    sales,
    products,
    customers,
    business,
    salesLoading,
    salesError,
    inventoryLoading,
    inventoryError,
    customersLoading,
    customersError,
  } = useStore();

  const [range, setRange] = useState("30");
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");

  const report = useMemo(() => {
    const days = Number(range);
    const cutoff = new Date();
    cutoff.setHours(0, 0, 0, 0);
    cutoff.setDate(cutoff.getDate() - days);

    const selectedSales = sales.filter(
      (sale) => new Date(sale.createdAt) >= cutoff,
    );

    const revenue = selectedSales.reduce(
      (sum, sale) => sum + Number(sale.total || 0),
      0,
    );

    const cost = selectedSales.reduce(
      (sum, sale) =>
        sum +
        (sale.items ?? []).reduce(
          (itemSum, item) =>
            itemSum +
            Number(item.costPrice || 0) *
              Number(item.quantity || 0),
          0,
        ),
      0,
    );

    // Sale.total already includes the discount, so it is not removed twice.
    const profit = revenue - cost;

    const paymentTotals = selectedSales.reduce((totals, sale) => {
      const successfulPayments = (sale.payments ?? []).filter(
        (payment) => payment.status === "successful",
      );

      if (successfulPayments.length) {
        successfulPayments.forEach((payment) => {
          const method = payment.method || "unknown";
          totals[method] =
            (totals[method] || 0) + Number(payment.amount || 0);
        });

        return totals;
      }

      const method = sale.paymentMethod || "unknown";
      totals[method] =
        (totals[method] || 0) + Number(sale.amountPaid || 0);

      return totals;
    }, {});

    const productTotals = {};

    selectedSales.forEach((sale) => {
      (sale.items ?? []).forEach((item) => {
        const name = item.name || "Unnamed product";
        productTotals[name] =
          (productTotals[name] || 0) +
          Number(item.quantity || 0);
      });
    });

    const topProducts = Object.entries(productTotals)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);

    const activeProducts = products.filter(
      (product) => product.status === "active",
    );

    const lowStockProducts = activeProducts.filter(
      (product) =>
        Number(product.stock || 0) <=
        Number(product.lowStockLevel || 0),
    );

    const stockCostValue = activeProducts.reduce(
      (sum, product) =>
        sum +
        Number(product.stock || 0) *
          Number(product.costPrice || 0),
      0,
    );

    const potentialRetailValue = activeProducts.reduce(
      (sum, product) =>
        sum +
        Number(product.stock || 0) *
          Number(product.sellingPrice || 0),
      0,
    );

    // Includes overdue charges in the report's customer debt total.
    const customerDebt = sales
      .filter((sale) => Boolean(sale.customerId))
      .reduce(
        (sum, sale) =>
          sum +
          Number(
            sale.totalDebtPayable ??
              Number(sale.outstandingBalance ?? 0) +
                Number(sale.overdueCharge ?? 0),
          ),
        0,
      );

    return {
      selectedSales,
      revenue,
      cost,
      profit,
      paymentTotals,
      topProducts,
      activeProducts,
      lowStockProducts,
      stockCostValue,
      potentialRetailValue,
      customerDebt,
    };
  }, [customers, products, range, sales]);

  const maxPayment = Math.max(
    1,
    ...Object.values(report.paymentTotals),
  );

  const maxProduct = Math.max(
    1,
    ...report.topProducts.map(([, quantity]) => quantity),
  );

  const isLoading =
    salesLoading || inventoryLoading || customersLoading;

  const loadError =
    salesError || inventoryError || customersError || "";

  function handleExportReport() {
    setActionMessage("");
    setActionError("");

    try {
      const filename = exportBusinessReportCsv({
        business,
        rangeLabel: RANGE_LABELS[range] || "Selected period",
        report,
      });

      setActionMessage(`${filename} downloaded successfully.`);
    } catch (error) {
      setActionError(
        error.message || "The business report could not be exported.",
      );
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Business intelligence"
        title="Reports"
        description="Understand sales, estimated gross profit, payments and product performance."
        actions={
          <>
            <select
              className="header-select"
              value={range}
              onChange={(event) => setRange(event.target.value)}
            >
              <option value="7">Last 7 days</option>
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
              <option value="365">Last 12 months</option>
            </select>

            <Button
              variant="secondary"
              onClick={handleExportReport}
              disabled={isLoading}
            >
              <Download size={18} />
              Export report
            </Button>
          </>
        }
      />

      {actionMessage ? (
        <div className="invoice-action-feedback" role="status">
          {actionMessage}
        </div>
      ) : null}

      {actionError ? (
        <div
          className="invoice-action-feedback invoice-action-feedback-error"
          role="alert"
        >
          {actionError}
        </div>
      ) : null}

      {isLoading ? (
        <section className="panel-card" role="status">
          <p className="muted-message">
            Loading the latest report data...
          </p>
        </section>
      ) : null}

      {loadError ? (
        <section className="panel-card" role="alert">
          <p className="danger-text">{loadError}</p>
        </section>
      ) : null}

      <section className="stats-grid stats-grid-four">
        <StatCard
          icon={TrendingUp}
          label="Sales revenue"
          value={formatCurrency(report.revenue)}
          detail={`${report.selectedSales.length} sale(s)`}
          tone="green"
        />
        <StatCard
          icon={BarChart3}
          label="Estimated gross profit"
          value={formatCurrency(report.profit)}
          detail="Before operating expenses"
          tone="blue"
        />
        <StatCard
          icon={CalendarDays}
          label="Average sale value"
          value={formatCurrency(
            report.selectedSales.length
              ? report.revenue / report.selectedSales.length
              : 0,
          )}
          detail="Across selected period"
          tone="amber"
        />
        <StatCard
          icon={PieChart}
          label="Customer debt"
          value={formatCurrency(report.customerDebt)}
          detail="Current outstanding total"
          tone="purple"
        />
      </section>

      <section className="report-grid">
        <article className="panel-card">
          <header className="panel-card-header">
            <div>
              <span>Money received</span>
              <h2>Payment methods</h2>
            </div>
          </header>

          <div className="horizontal-bar-list">
            {[
              "cash",
              "mobile_money",
              "bank_transfer",
              "credit",
            ].map((method) => {
              const value = report.paymentTotals[method] || 0;

              return (
                <div key={method}>
                  <div>
                    <span className="capitalize-text">
                      {method.replace("_", " ")}
                    </span>
                    <strong>{formatCurrency(value)}</strong>
                  </div>

                  <span className="bar-track">
                    <i
                      style={{
                        width: `${(value / maxPayment) * 100}%`,
                      }}
                    />
                  </span>
                </div>
              );
            })}
          </div>
        </article>

        <article className="panel-card">
          <header className="panel-card-header">
            <div>
              <span>Sales quantity</span>
              <h2>Top-selling products</h2>
            </div>
          </header>

          <div className="horizontal-bar-list product-bar-list">
            {report.topProducts.length ? (
              report.topProducts.map(([name, quantity]) => (
                <div key={name}>
                  <div>
                    <span>{name}</span>
                    <strong>{quantity} sold</strong>
                  </div>

                  <span className="bar-track">
                    <i
                      style={{
                        width: `${(quantity / maxProduct) * 100}%`,
                      }}
                    />
                  </span>
                </div>
              ))
            ) : (
              <p className="muted-message">
                No product sales fall inside the selected period.
              </p>
            )}
          </div>
        </article>
      </section>

      <section className="report-grid">
        <article className="panel-card report-summary-card">
          <header className="panel-card-header">
            <div>
              <span>Inventory position</span>
              <h2>Stock summary</h2>
            </div>
          </header>

          <div className="report-summary-list">
            <div>
              <span>Active products</span>
              <strong>{report.activeProducts.length}</strong>
            </div>
            <div>
              <span>Low-stock products</span>
              <strong>{report.lowStockProducts.length}</strong>
            </div>
            <div>
              <span>Stock cost value</span>
              <strong>{formatCurrency(report.stockCostValue)}</strong>
            </div>
            <div>
              <span>Potential retail value</span>
              <strong>
                {formatCurrency(report.potentialRetailValue)}
              </strong>
            </div>
          </div>
        </article>

        <article className="panel-card report-insight-card">
          <span>Management note</span>
          <h2>
            Stock and profit remain estimates until every sale and
            adjustment is recorded.
          </h2>
          <p>
            Consistent usage is more important than adding complicated
            accounting features at this stage.
          </p>
        </article>
      </section>
    </div>
  );
}
