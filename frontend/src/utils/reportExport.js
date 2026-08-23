import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

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
      "Amount paid (GHS)",
      "Balance due (GHS)",
      "Overdue charge (GHS)",
      "Total payable (GHS)",
      "Sale total (GHS)",
    ],
    ...report.selectedSales.map((sale) => [
      sale.saleNumber,
      sale.invoiceNumber,
      new Date(sale.createdAt).toLocaleString(),
      sale.customerName,
      String(sale.paymentMethod || "").replaceAll("_", " "),
      Number(sale.amountPaid || 0).toFixed(2),
      Number(sale.outstandingBalance || 0).toFixed(2),
      Number(sale.overdueCharge || 0).toFixed(2),
      Number(
        sale.totalDebtPayable ??
          Number(sale.outstandingBalance ?? 0) +
            Number(sale.overdueCharge ?? 0),
      ).toFixed(2),
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


function formatReportCurrency(value) {
  return `GHS ${Number(value || 0).toLocaleString("en-GH", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

function formatReportNumber(value) {
  return Number(value || 0).toLocaleString("en-GH", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

function formatReportDate(value) {
  if (!value) return "Not recorded";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString("en-GH", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function humanizePaymentMethod(value) {
  const text = String(value || "unknown").replaceAll("_", " ").trim();

  return text
    .split(" ")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function resolveSalePayable(sale) {
  return Number(
    sale?.totalDebtPayable ??
      Number(sale?.outstandingBalance ?? 0) +
        Number(sale?.overdueCharge ?? 0),
  );
}

function reportFilename(business, extension) {
  const businessName = safeFilename(business?.name) || "business";
  const date = new Date().toISOString().slice(0, 10);

  return `${businessName}-report-${date}.${extension}`;
}

function reportSummaryRows(report) {
  const averageSale = report.selectedSales.length
    ? report.revenue / report.selectedSales.length
    : 0;

  return [
    ["Sales count", String(report.selectedSales.length)],
    ["Sales revenue", formatReportCurrency(report.revenue)],
    ["Estimated stock cost", formatReportCurrency(report.cost)],
    ["Estimated gross profit", formatReportCurrency(report.profit)],
    ["Average sale value", formatReportCurrency(averageSale)],
    ["Customer debt", formatReportCurrency(report.customerDebt)],
    ["Active products", String(report.activeProducts.length)],
    ["Low-stock products", String(report.lowStockProducts.length)],
    ["Stock cost value", formatReportCurrency(report.stockCostValue)],
    ["Potential retail value", formatReportCurrency(report.potentialRetailValue)],
  ];
}

function reportSalesRows(report) {
  return report.selectedSales.map((sale) => [
    `${sale.saleNumber || "-"}\n${sale.invoiceNumber || "-"}`,
    formatReportDate(sale.createdAt),
    sale.customerName || "Walk-in customer",
    humanizePaymentMethod(sale.paymentMethod),
    formatReportNumber(sale.amountPaid),
    formatReportNumber(sale.outstandingBalance),
    formatReportNumber(sale.overdueCharge),
    formatReportNumber(resolveSalePayable(sale)),
    formatReportNumber(sale.total),
  ]);
}

function addPdfSectionHeading(pdf, title, y, margin) {
  pdf.setTextColor(39, 56, 47);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(9);
  pdf.text(title.toUpperCase(), margin, y);
}

function addReportPdfFooters(pdf, businessName) {
  const pageCount = pdf.getNumberOfPages();
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 30;

  for (let pageNumber = 1; pageNumber <= pageCount; pageNumber += 1) {
    pdf.setPage(pageNumber);
    pdf.setDrawColor(220, 230, 224);
    pdf.line(margin, pageHeight - 24, pageWidth - margin, pageHeight - 24);

    pdf.setTextColor(105, 119, 111);
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(7);
    pdf.text(`${businessName} • Generated by StockFlow`, margin, pageHeight - 11);
    pdf.text(
      `Page ${pageNumber} of ${pageCount}`,
      pageWidth - margin,
      pageHeight - 11,
      { align: "right" },
    );
  }
}

export function exportBusinessReportPdf({
  business,
  rangeLabel,
  report,
}) {
  if (!business) {
    throw new Error("Select a business before exporting the report.");
  }

  const pdf = new jsPDF({
    orientation: "landscape",
    unit: "pt",
    format: "a4",
  });

  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 30;
  const businessName = String(business.name || "Business");
  const generatedAt = new Date();

  pdf.setFillColor(15, 42, 30);
  pdf.rect(0, 0, pageWidth, 72, "F");

  pdf.setTextColor(255, 255, 255);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(17);
  pdf.text(businessName, margin, 30);

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(8);
  pdf.text(
    [
      String(business.location || "Location not recorded"),
      String(business.phone || "Phone not recorded"),
    ],
    margin,
    46,
  );

  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(12);
  pdf.text("BUSINESS REPORT", pageWidth - margin, 28, { align: "right" });

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(8);
  pdf.text(rangeLabel || "Selected period", pageWidth - margin, 44, {
    align: "right",
  });
  pdf.text(
    `Generated ${formatReportDate(generatedAt)}`,
    pageWidth - margin,
    57,
    { align: "right" },
  );

  addPdfSectionHeading(pdf, "Executive summary", 96, margin);

  autoTable(pdf, {
    startY: 105,
    head: [["Metric", "Value"]],
    body: reportSummaryRows(report),
    theme: "grid",
    margin: { left: margin, right: margin },
    tableWidth: 365,
    styles: {
      font: "helvetica",
      fontSize: 8,
      textColor: [47, 64, 55],
      cellPadding: 5,
      lineColor: [220, 230, 224],
      lineWidth: 0.5,
    },
    headStyles: {
      fillColor: [31, 107, 79],
      textColor: [255, 255, 255],
      fontStyle: "bold",
    },
    alternateRowStyles: { fillColor: [248, 251, 249] },
    columnStyles: {
      0: { cellWidth: 230 },
      1: { cellWidth: 135, halign: "right", fontStyle: "bold" },
    },
  });

  const summaryBottom = pdf.lastAutoTable?.finalY ?? 260;
  const sideX = 430;

  addPdfSectionHeading(pdf, "Payments received", 96, sideX);

  autoTable(pdf, {
    startY: 105,
    head: [["Method", "Amount received"]],
    body:
      Object.entries(report.paymentTotals).length > 0
        ? Object.entries(report.paymentTotals).map(([method, amount]) => [
            humanizePaymentMethod(method),
            formatReportCurrency(amount),
          ])
        : [["No payments recorded", "GHS 0"]],
    theme: "grid",
    margin: { left: sideX, right: margin },
    tableWidth: pageWidth - sideX - margin,
    styles: {
      font: "helvetica",
      fontSize: 8,
      textColor: [47, 64, 55],
      cellPadding: 5,
      lineColor: [220, 230, 224],
      lineWidth: 0.5,
    },
    headStyles: {
      fillColor: [31, 107, 79],
      textColor: [255, 255, 255],
      fontStyle: "bold",
    },
    alternateRowStyles: { fillColor: [248, 251, 249] },
    columnStyles: {
      1: { halign: "right", fontStyle: "bold" },
    },
  });

  let sideBottom = pdf.lastAutoTable?.finalY ?? 180;
  addPdfSectionHeading(pdf, "Top-selling products", sideBottom + 22, sideX);

  autoTable(pdf, {
    startY: sideBottom + 30,
    head: [["Product", "Quantity sold"]],
    body:
      report.topProducts.length > 0
        ? report.topProducts.map(([name, quantity]) => [
            name,
            formatReportNumber(quantity),
          ])
        : [["No product sales recorded", "0"]],
    theme: "grid",
    margin: { left: sideX, right: margin },
    tableWidth: pageWidth - sideX - margin,
    styles: {
      font: "helvetica",
      fontSize: 8,
      textColor: [47, 64, 55],
      cellPadding: 5,
      lineColor: [220, 230, 224],
      lineWidth: 0.5,
    },
    headStyles: {
      fillColor: [31, 107, 79],
      textColor: [255, 255, 255],
      fontStyle: "bold",
    },
    alternateRowStyles: { fillColor: [248, 251, 249] },
    columnStyles: {
      1: { halign: "right", fontStyle: "bold" },
    },
  });

  sideBottom = pdf.lastAutoTable?.finalY ?? sideBottom + 100;
  let salesStartY = Math.max(summaryBottom, sideBottom) + 28;

  if (salesStartY > pageHeight - 125) {
    pdf.addPage();
    salesStartY = 42;
  }

  addPdfSectionHeading(pdf, "Sales included", salesStartY, margin);

  autoTable(pdf, {
    startY: salesStartY + 9,
    head: [[
      "Sale / Invoice",
      "Date",
      "Customer",
      "Payment",
      "Amount paid\n(GHS)",
      "Balance due\n(GHS)",
      "Overdue\n(GHS)",
      "Total payable\n(GHS)",
      "Sale total\n(GHS)",
    ]],
    body:
      report.selectedSales.length > 0
        ? reportSalesRows(report)
        : [["No sales", "-", "-", "-", "0", "0", "0", "0", "0"]],
    theme: "grid",
    margin: { left: margin, right: margin, bottom: 34 },
    styles: {
      font: "helvetica",
      fontSize: 6.7,
      textColor: [47, 64, 55],
      cellPadding: 4,
      lineColor: [220, 230, 224],
      lineWidth: 0.45,
      valign: "middle",
      overflow: "linebreak",
    },
    headStyles: {
      fillColor: [31, 107, 79],
      textColor: [255, 255, 255],
      fontStyle: "bold",
      halign: "center",
      valign: "middle",
    },
    alternateRowStyles: { fillColor: [248, 251, 249] },
    columnStyles: {
      0: { cellWidth: 78 },
      1: { cellWidth: 88 },
      2: { cellWidth: 95 },
      3: { cellWidth: 70 },
      4: { cellWidth: 74, halign: "right" },
      5: { cellWidth: 74, halign: "right" },
      6: { cellWidth: 62, halign: "right" },
      7: { cellWidth: 76, halign: "right" },
      8: { cellWidth: 70, halign: "right", fontStyle: "bold" },
    },
  });

  addReportPdfFooters(pdf, businessName);

  const filename = reportFilename(business, "pdf");
  pdf.save(filename);
  return filename;
}

function styleExcelHeading(cell) {
  cell.font = { bold: true, color: { argb: "FFFFFFFF" } };
  cell.fill = {
    type: "pattern",
    pattern: "solid",
    fgColor: { argb: "FF1F6B4F" },
  };
  cell.alignment = { vertical: "middle", horizontal: "left" };
  cell.border = {
    top: { style: "thin", color: { argb: "FFDCE6E0" } },
    left: { style: "thin", color: { argb: "FFDCE6E0" } },
    bottom: { style: "thin", color: { argb: "FFDCE6E0" } },
    right: { style: "thin", color: { argb: "FFDCE6E0" } },
  };
}

function styleExcelDataRows(sheet, startRow, endRow) {
  for (let rowNumber = startRow; rowNumber <= endRow; rowNumber += 1) {
    const row = sheet.getRow(rowNumber);

    row.eachCell({ includeEmpty: true }, (cell) => {
      cell.border = {
        top: { style: "thin", color: { argb: "FFE5ECE8" } },
        left: { style: "thin", color: { argb: "FFE5ECE8" } },
        bottom: { style: "thin", color: { argb: "FFE5ECE8" } },
        right: { style: "thin", color: { argb: "FFE5ECE8" } },
      };
      cell.alignment = { vertical: "middle", wrapText: true };
    });
  }
}

function addExcelTitle(sheet, business, rangeLabel, width) {
  sheet.mergeCells(1, 1, 1, width);
  const title = sheet.getCell(1, 1);
  title.value = "StockFlow Business Report";
  title.font = {
    bold: true,
    size: 16,
    color: { argb: "FFFFFFFF" },
  };
  title.fill = {
    type: "pattern",
    pattern: "solid",
    fgColor: { argb: "FF0F2A1E" },
  };
  title.alignment = { vertical: "middle", horizontal: "left" };
  sheet.getRow(1).height = 28;

  sheet.mergeCells(2, 1, 2, width);
  sheet.getCell(2, 1).value =
    `${business?.name || "Business"} • ${rangeLabel || "Selected period"}`;
  sheet.getCell(2, 1).font = {
    bold: true,
    color: { argb: "FF24382E" },
  };

  sheet.mergeCells(3, 1, 3, width);
  sheet.getCell(3, 1).value = `Generated ${formatReportDate(new Date())}`;
  sheet.getCell(3, 1).font = {
    color: { argb: "FF6A786F" },
    size: 10,
  };
}

function triggerWorkbookDownload(filename, buffer) {
  const blob = new Blob([buffer], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);

  return filename;
}

export async function exportBusinessReportExcel({
  business,
  rangeLabel,
  report,
}) {
  if (!business) {
    throw new Error("Select a business before exporting the report.");
  }

  const excelModule = await import("exceljs");
  const Workbook =
    excelModule.Workbook || excelModule.default?.Workbook;

  if (!Workbook) {
    throw new Error("Excel export is unavailable in this browser.");
  }

  const workbook = new Workbook();
  workbook.creator = "StockFlow";
  workbook.company = String(business.name || "Business");
  workbook.created = new Date();

  const summarySheet = workbook.addWorksheet("Summary", {
    views: [{ state: "frozen", ySplit: 5 }],
  });
  summarySheet.columns = [{ width: 30 }, { width: 24 }];
  addExcelTitle(summarySheet, business, rangeLabel, 2);
  summarySheet.addRow([]);
  summarySheet.addRow(["Metric", "Value"]);
  summarySheet.getRow(5).eachCell(styleExcelHeading);
  reportSummaryRows(report).forEach(([metric, value]) => {
    summarySheet.addRow([metric, value]);
  });
  styleExcelDataRows(summarySheet, 6, summarySheet.rowCount);

  const paymentsSheet = workbook.addWorksheet("Payments", {
    views: [{ state: "frozen", ySplit: 5 }],
  });
  paymentsSheet.columns = [{ width: 30 }, { width: 22 }];
  addExcelTitle(paymentsSheet, business, rangeLabel, 2);
  paymentsSheet.addRow([]);
  paymentsSheet.addRow(["Payment method", "Amount received (GHS)"]);
  paymentsSheet.getRow(5).eachCell(styleExcelHeading);

  const paymentRows = Object.entries(report.paymentTotals);
  if (paymentRows.length) {
    paymentRows.forEach(([method, amount]) => {
      paymentsSheet.addRow([
        humanizePaymentMethod(method),
        Number(amount || 0),
      ]);
    });
  } else {
    paymentsSheet.addRow(["No payments recorded", 0]);
  }
  styleExcelDataRows(paymentsSheet, 6, paymentsSheet.rowCount);
  paymentsSheet.getColumn(2).numFmt = "#,##0.00";

  const productsSheet = workbook.addWorksheet("Top Products", {
    views: [{ state: "frozen", ySplit: 5 }],
  });
  productsSheet.columns = [{ width: 38 }, { width: 18 }];
  addExcelTitle(productsSheet, business, rangeLabel, 2);
  productsSheet.addRow([]);
  productsSheet.addRow(["Product", "Quantity sold"]);
  productsSheet.getRow(5).eachCell(styleExcelHeading);

  if (report.topProducts.length) {
    report.topProducts.forEach(([name, quantity]) => {
      productsSheet.addRow([name, Number(quantity || 0)]);
    });
  } else {
    productsSheet.addRow(["No product sales recorded", 0]);
  }
  styleExcelDataRows(productsSheet, 6, productsSheet.rowCount);

  const salesSheet = workbook.addWorksheet("Sales", {
    views: [{ state: "frozen", ySplit: 5 }],
  });
  salesSheet.columns = [
    { width: 18 },
    { width: 19 },
    { width: 22 },
    { width: 28 },
    { width: 20 },
    { width: 18 },
    { width: 18 },
    { width: 18 },
    { width: 18 },
    { width: 18 },
  ];
  addExcelTitle(salesSheet, business, rangeLabel, 10);
  salesSheet.addRow([]);
  salesSheet.addRow([
    "Sale",
    "Invoice",
    "Date",
    "Customer",
    "Payment method",
    "Amount paid (GHS)",
    "Balance due (GHS)",
    "Overdue charge (GHS)",
    "Total payable (GHS)",
    "Sale total (GHS)",
  ]);
  salesSheet.getRow(5).eachCell(styleExcelHeading);

  if (report.selectedSales.length) {
    report.selectedSales.forEach((sale) => {
      salesSheet.addRow([
        sale.saleNumber || "",
        sale.invoiceNumber || "",
        formatReportDate(sale.createdAt),
        sale.customerName || "Walk-in customer",
        humanizePaymentMethod(sale.paymentMethod),
        Number(sale.amountPaid || 0),
        Number(sale.outstandingBalance || 0),
        Number(sale.overdueCharge || 0),
        resolveSalePayable(sale),
        Number(sale.total || 0),
      ]);
    });
  } else {
    salesSheet.addRow(["No sales", "", "", "", "", 0, 0, 0, 0, 0]);
  }

  styleExcelDataRows(salesSheet, 6, salesSheet.rowCount);
  for (let column = 6; column <= 10; column += 1) {
    salesSheet.getColumn(column).numFmt = "#,##0.00";
  }

  salesSheet.autoFilter = {
    from: { row: 5, column: 1 },
    to: { row: 5, column: 10 },
  };

  const buffer = await workbook.xlsx.writeBuffer();
  const filename = reportFilename(business, "xlsx");

  return triggerWorkbookDownload(filename, buffer);
}
