import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  CircleDollarSign,
  PackageSearch,
  ReceiptText,
  ShoppingCart,
  TrendingUp,
  Users,
} from "lucide-react";
import { Link } from "react-router-dom";

import Badge from "../../components/ui/Badge";
import PageHeader from "../../components/ui/PageHeader";
import StatCard from "../../components/ui/StatCard";
import StickyTableScroll from "../../components/ui/StickyTableScroll";
import { useStore } from "../../context/StoreContext";
import { formatCurrency, formatDateTime } from "../../utils/formatters";

import "../../styles/dashboard-polish.css";

/*
  Returns a greeting based on the user's current device time.
*/
function getTimeBasedGreeting() {
  const currentHour = new Date().getHours();

  if (currentHour < 12) {
    return "Good morning";
  }

  if (currentHour < 17) {
    return "Good afternoon";
  }

  return "Good evening";
}

export default function DashboardPage() {
  const {
    metrics,
    sales,
    products,
    business,
    salesLoading,
    salesError,
    inventoryLoading,
    inventoryError,
    customersLoading,
    customersError,
  } = useStore();

  const greeting = getTimeBasedGreeting();
  const recentSales = sales.slice(0, 5);

  // Ranks stock by its actual cost value to match the panel heading.
  const topProducts = [...products]
    .filter((product) => product.status === "active")
    .sort(
      (a, b) =>
        Number(b.stock || 0) * Number(b.costPrice || 0) -
        Number(a.stock || 0) * Number(a.costPrice || 0),
    )
    .slice(0, 5);

  const activeProductCount = Math.max(
    0,
    Number(metrics.activeProducts || 0),
  );
  const lowStockCount = metrics.lowStockProducts.length;

  // Calculates inventory health from active products instead of a fixed score.
  const inventoryHealth = activeProductCount
    ? Math.max(
        0,
        Math.round(
          ((activeProductCount - lowStockCount) / activeProductCount) *
            100,
        ),
      )
    : 100;

  const isLoading =
    salesLoading || inventoryLoading || customersLoading;

  const loadError =
    salesError || inventoryError || customersError || "";

  return (
    <div className="page-stack dashboard-page">
      <PageHeader
        eyebrow="Business overview"
        title={`${greeting}, ${business?.name || "Your business"}`}
        description="Here is what is happening across your business today."
        actions={
          <Link
            to="/app/new-sale"
            className="app-button app-button-primary app-button-medium"
          >
            <ShoppingCart size={18} />
            Record a sale
          </Link>
        }
      />

      {isLoading ? (
        <section className="panel-card" role="status">
          <p className="muted-message">
            Loading the latest business records...
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
          icon={CircleDollarSign}
          label="Today's sales"
          value={formatCurrency(metrics.todayRevenue)}
          detail={`${metrics.todaySales.length} transaction(s)`}
          tone="green"
        />
        <StatCard
          icon={TrendingUp}
          label="Estimated profit"
          value={formatCurrency(metrics.todayProfit)}
          detail="Gross profit before expenses"
          tone="blue"
        />
        <StatCard
          icon={Users}
          label="Customer debt"
          value={formatCurrency(metrics.customerDebt)}
          detail="Outstanding customer balances"
          tone="amber"
        />
        <StatCard
          icon={Boxes}
          label="Stock value"
          value={formatCurrency(metrics.stockValue)}
          detail={`${metrics.activeProducts} active products`}
          tone="purple"
        />
      </section>

      {metrics.lowStockProducts.length ? (
        <section className="dashboard-alert-card">
          <div className="dashboard-alert-icon">
            <AlertTriangle size={22} />
          </div>

          <div>
            <strong>
              {metrics.lowStockProducts.length} product(s) need stock
              attention
            </strong>
            <p>
              {metrics.lowStockProducts
                .map((product) =>
                  product.designCode
                    ? `Design ${product.designCode}`
                    : product.name,
                )
                .join(", ")}
            </p>
          </div>

          <Link to="/app/products">
            Review stock
            <ArrowRight size={17} />
          </Link>
        </section>
      ) : null}

      <section className="dashboard-content-grid">
        <article className="panel-card dashboard-sales-panel">
          <header className="panel-card-header">
            <div>
              <span>Latest activity</span>
              <h2>Recent sales</h2>
            </div>

            <Link to="/app/sales">
              View all
              <ArrowRight size={16} />
            </Link>
          </header>

          <StickyTableScroll>
            <table className="data-table compact-table">
              <thead>
                <tr>
                  <th>Sale</th>
                  <th>Customer</th>
                  <th>Payment</th>
                  <th>Total</th>
                  <th>Status</th>
                </tr>
              </thead>

              <tbody>
                {recentSales.map((sale) => (
                  <tr key={sale.id}>
                    <td>
                      <strong>{sale.saleNumber}</strong>
                      <small>{formatDateTime(sale.createdAt)}</small>
                    </td>
                    <td>{sale.customerName}</td>
                    <td className="capitalize-text">
                      {sale.paymentMethod.replace("_", " ")}
                    </td>
                    <td>
                      <strong>{formatCurrency(sale.total)}</strong>
                    </td>
                    <td>
                      {/* Uses full payable debt, including overdue charges. */}
                      <Badge
                        tone={
                          Number(
                            sale.totalDebtPayable ??
                              sale.outstandingBalance ??
                              0,
                          ) > 0
                            ? "warning"
                            : "success"
                        }
                      >
                        {Number(sale.daysOverdue ?? 0) > 0
                          ? `Overdue ${sale.daysOverdue} day(s)`
                          : Number(
                                sale.totalDebtPayable ??
                                  sale.outstandingBalance ??
                                  0,
                              ) > 0
                            ? "Part paid"
                            : "Completed"}
                      </Badge>
                    </td>
                  </tr>
                ))}

                {!isLoading && !recentSales.length ? (
                  <tr>
                    <td colSpan="5">
                      <p className="muted-message">
                        No sales have been recorded yet.
                      </p>
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </StickyTableScroll>
        </article>

        <article className="panel-card quick-actions-panel">
          <header className="panel-card-header">
            <div>
              <span>Shortcuts</span>
              <h2>Quick actions</h2>
            </div>
          </header>

          <div className="quick-action-list">
            <Link to="/app/new-sale">
              <span>
                <ShoppingCart size={20} />
              </span>
              <div>
                <strong>Record a new sale</strong>
                <small>Create a sale and invoice</small>
              </div>
              <ArrowRight size={17} />
            </Link>

            <Link to="/app/products">
              <span>
                <Boxes size={20} />
              </span>
              <div>
                <strong>Add stock or product</strong>
                <small>Update your inventory</small>
              </div>
              <ArrowRight size={17} />
            </Link>

            <Link to="/app/customers">
              <span>
                <Users size={20} />
              </span>
              <div>
                <strong>Record debt payment</strong>
                <small>Reduce a customer balance</small>
              </div>
              <ArrowRight size={17} />
            </Link>

            <Link to="/app/invoices">
              <span>
                <ReceiptText size={20} />
              </span>
              <div>
                <strong>Find an invoice</strong>
                <small>Review sales documents</small>
              </div>
              <ArrowRight size={17} />
            </Link>
          </div>
        </article>
      </section>

      <section className="dashboard-content-grid dashboard-bottom-grid">
        <article className="panel-card">
          <header className="panel-card-header">
            <div>
              <span>Inventory value</span>
              <h2>High-value stock</h2>
            </div>

            <Link to="/app/products">
              Inventory
              <ArrowRight size={16} />
            </Link>
          </header>

          <div className="stock-value-list">
            {topProducts.map((product) => (
              <div key={product.id}>
                <span
                  className={`product-visual-small ${
                    product.imageStyle || "product-generic"
                  }`}
                />
                <div>
                  <strong>{product.name}</strong>
                  <small>
                    {product.designCode
                      ? `Design ${product.designCode} · `
                      : ""}
                    {product.stock} {product.unit}(s)
                  </small>
                </div>
                <b>
                  {formatCurrency(
                    Number(product.stock || 0) *
                      Number(product.costPrice || 0),
                  )}
                </b>
              </div>
            ))}

            {!inventoryLoading && !topProducts.length ? (
              <p className="muted-message">
                No active inventory records are available.
              </p>
            ) : null}
          </div>
        </article>

        <article className="panel-card inventory-health-card">
          <header className="panel-card-header">
            <div>
              <span>Stock control</span>
              <h2>Inventory health</h2>
            </div>
            <PackageSearch size={20} />
          </header>

          <div className="inventory-health-chart">
            <div
              className="health-donut"
              style={{ "--health-value": `${inventoryHealth}%` }}
            >
              <span>{inventoryHealth}%</span>
              <small>Healthy</small>
            </div>

            <div className="health-legend">
              <div>
                <i className="legend-active" />
                <span>Active products</span>
                <strong>{metrics.activeProducts}</strong>
              </div>
              <div>
                <i className="legend-low" />
                <span>Low stock</span>
                <strong>{metrics.lowStockProducts.length}</strong>
              </div>
              <div>
                <i className="legend-inactive" />
                <span>Inactive</span>
                <strong>
                  {
                    products.filter(
                      (product) => product.status !== "active",
                    ).length
                  }
                </strong>
              </div>
            </div>
          </div>
        </article>
      </section>
    </div>
  );
}
