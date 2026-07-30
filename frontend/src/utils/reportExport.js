// Converts report values into a safe downloadable CSV document.

function escapeCsvCell(value) {
  const text = String(value ?? "");

  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }

  return text;
}

function safeFilename(value) {
  return String(value || "stockflow")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function downloadCsv(filename, rows) {
  const csv = rows
    .map((row) => row.map(escapeCsvCell).join(","))
    .join("\n");

  const blob = new Blob(["\uFEFF", csv], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);

  return filename;
}

export function exportBusinessReportCsv({
  business,
  rangeLabel,
  report,
}) {
  if (!business) {
    throw new Error("Select a business before exporting the report.");
  }

  const averageSale = report.selectedSales.length
    ? report.revenue / report.selectedSales.length
    : 0;

  const rows = [
    ["StockFlow business report"],
    ["Business", business.name],
    ["Period", rangeLabel],
    ["Generated at", new Date().toLocaleString()],
    ["Currency", "GHS"],
    [],
    ["Summary"],
    ["Metric", "Value"],
    ["Sales count", report.selectedSales.length],
    ["Sales revenue (GHS)", report.revenue.toFixed(2)],
    ["Estimated stock cost (GHS)", report.cost.toFixed(2)],
    ["Estimated gross profit (GHS)", report.profit.toFixed(2)],
    ["Average sale value (GHS)", averageSale.toFixed(2)],
    ["Customer debt (GHS)", report.customerDebt.toFixed(2)],
    ["Active products", report.activeProducts.length],
    ["Low-stock products", report.lowStockProducts.length],
    ["Stock cost value (GHS)", report.stockCostValue.toFixed(2)],
    [
      "Potential retail value (GHS)",
      report.potentialRetailValue.toFixed(2),
    ],
    [],
    ["Payment methods"],
    ["Method", "Amount received (GHS)"],
    ...Object.entries(report.paymentTotals).map(
      ([method, amount]) => [
        method.replaceAll("_", " "),
        Number(amount || 0).toFixed(2),
      ],
    ),
    [],
    ["Top-selling products"],
    ["Product", "Quantity sold"],
    ...report.topProducts.map(([name, quantity]) => [
      name,
      quantity,
    ]),
    [],
    ["Sales included"],
    [
      "Sale",
      "Invoice",
      "Date",
      "Customer",
      "Payment method",
      "Paid (GHS)",
      "Balance (GHS)",
      "Total (GHS)",
    ],
    ...report.selectedSales.map((sale) => [
      sale.saleNumber,
      sale.invoiceNumber,
      new Date(sale.createdAt).toLocaleString(),
      sale.customerName,
      String(sale.paymentMethod || "").replaceAll("_", " "),
      Number(sale.amountPaid || 0).toFixed(2),
      Number(sale.outstandingBalance || 0).toFixed(2),
      Number(sale.total || 0).toFixed(2),
    ]),
  ];

  const businessName = safeFilename(business.name) || "business";
  const date = new Date().toISOString().slice(0, 10);

  return downloadCsv(
    `${businessName}-report-${date}.csv`,
    rows,
  );
}
