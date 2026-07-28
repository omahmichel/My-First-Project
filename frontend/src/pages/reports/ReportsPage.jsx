import { BarChart3, CalendarDays, Download, PieChart, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";

import Button from "../../components/ui/Button";
import PageHeader from "../../components/ui/PageHeader";
import StatCard from "../../components/ui/StatCard";
import { useStore } from "../../context/StoreContext";
import { formatCurrency } from "../../utils/formatters";

export default function ReportsPage() {
  const { sales, products, customers } = useStore();
  const [range, setRange] = useState("30");

  const report = useMemo(() => {
    const days = Number(range);
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);
    const selectedSales = sales.filter((sale) => new Date(sale.createdAt) >= cutoff);
    const revenue = selectedSales.reduce((sum, sale) => sum + sale.total, 0);
    const cost = selectedSales.reduce((sum, sale) => sum + sale.items.reduce((itemSum, item) => itemSum + item.costPrice * item.quantity, 0), 0);
    const profit = revenue - cost - selectedSales.reduce((sum, sale) => sum + sale.discount, 0);
    const paymentTotals = selectedSales.reduce((totals, sale) => ({ ...totals, [sale.paymentMethod]: (totals[sale.paymentMethod] || 0) + sale.amountPaid }), {});
    const productTotals = {};
    selectedSales.forEach((sale) => sale.items.forEach((item) => {
      productTotals[item.name] = (productTotals[item.name] || 0) + item.quantity;
    }));
    const topProducts = Object.entries(productTotals).sort((a, b) => b[1] - a[1]).slice(0, 5);
    return { selectedSales, revenue, profit, paymentTotals, topProducts };
  }, [range, sales]);

  const maxPayment = Math.max(1, ...Object.values(report.paymentTotals));
  const maxProduct = Math.max(1, ...report.topProducts.map(([, quantity]) => quantity));

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Business intelligence"
        title="Reports"
        description="Understand sales, estimated gross profit, payments and product performance."
        actions={<><select className="header-select" value={range} onChange={(event) => setRange(event.target.value)}><option value="7">Last 7 days</option><option value="30">Last 30 days</option><option value="90">Last 90 days</option><option value="365">Last 12 months</option></select><Button variant="secondary"><Download size={18} /> Export report</Button></>}
      />

      <section className="stats-grid stats-grid-four">
        <StatCard icon={TrendingUp} label="Sales revenue" value={formatCurrency(report.revenue)} detail={`${report.selectedSales.length} sale(s)`} tone="green" />
        <StatCard icon={BarChart3} label="Estimated gross profit" value={formatCurrency(report.profit)} detail="Before operating expenses" tone="blue" />
        <StatCard icon={CalendarDays} label="Average sale value" value={formatCurrency(report.selectedSales.length ? report.revenue / report.selectedSales.length : 0)} detail="Across selected period" tone="amber" />
        <StatCard icon={PieChart} label="Customer debt" value={formatCurrency(customers.reduce((sum, customer) => sum + customer.outstandingBalance, 0))} detail="Current outstanding total" tone="purple" />
      </section>

      <section className="report-grid">
        <article className="panel-card">
          <header className="panel-card-header"><div><span>Money received</span><h2>Payment methods</h2></div></header>
          <div className="horizontal-bar-list">
            {["cash", "mobile_money", "bank_transfer", "credit"].map((method) => {
              const value = report.paymentTotals[method] || 0;
              return <div key={method}><div><span className="capitalize-text">{method.replace("_", " ")}</span><strong>{formatCurrency(value)}</strong></div><span className="bar-track"><i style={{ width: `${(value / maxPayment) * 100}%` }} /></span></div>;
            })}
          </div>
        </article>

        <article className="panel-card">
          <header className="panel-card-header"><div><span>Sales quantity</span><h2>Top-selling products</h2></div></header>
          <div className="horizontal-bar-list product-bar-list">
            {report.topProducts.length ? report.topProducts.map(([name, quantity]) => <div key={name}><div><span>{name}</span><strong>{quantity} sold</strong></div><span className="bar-track"><i style={{ width: `${(quantity / maxProduct) * 100}%` }} /></span></div>) : <p className="muted-message">No product sales fall inside the selected period.</p>}
          </div>
        </article>
      </section>

      <section className="report-grid">
        <article className="panel-card report-summary-card">
          <header className="panel-card-header"><div><span>Inventory position</span><h2>Stock summary</h2></div></header>
          <div className="report-summary-list">
            <div><span>Active products</span><strong>{products.filter((product) => product.status === "active").length}</strong></div>
            <div><span>Low-stock products</span><strong>{products.filter((product) => product.stock <= product.lowStockLevel).length}</strong></div>
            <div><span>Stock cost value</span><strong>{formatCurrency(products.reduce((sum, product) => sum + product.stock * product.costPrice, 0))}</strong></div>
            <div><span>Potential retail value</span><strong>{formatCurrency(products.reduce((sum, product) => sum + product.stock * product.sellingPrice, 0))}</strong></div>
          </div>
        </article>

        <article className="panel-card report-insight-card">
          <span>Management note</span>
          <h2>Stock and profit remain estimates until every sale and adjustment is recorded.</h2>
          <p>Consistent usage is more important than adding complicated accounting features at this stage.</p>
        </article>
      </section>
    </div>
  );
}
