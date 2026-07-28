import { jsPDF } from "jspdf";
import { autoTable } from "jspdf-autotable";

function safeText(value, fallback = "Not recorded") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function safeFilename(value) {
  return safeText(value, "document")
    .replace(/[<>:"/\\\\|?*\\u0000-\\u001F]/g, "-")
    .replace(/\\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

function formatPdfCurrency(value) {
  const amount = Number(value || 0);

  return `GHS ${amount.toLocaleString("en-GH", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatPaymentMethod(value) {
  return safeText(value)
    .replaceAll("_", " ")
    .replace(/\\b\\w/g, (letter) => letter.toUpperCase());
}

function formatDocumentDate(value) {
  const date = value ? new Date(value) : new Date();

  if (Number.isNaN(date.getTime())) {
    return safeText(value);
  }

  return date.toLocaleDateString("en-GH", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function escapeCsvCell(value) {
  const text = String(value ?? "");

  if (/[",\\r\\n]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`;
  }

  return text;
}

function downloadBlob(blob, filename) {
  const downloadUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");

  anchor.href = downloadUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();

  window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
}

export function exportInvoiceList(invoices, business) {
  if (!invoices.length) {
    throw new Error("There are no invoice records to export.");
  }

  const header = [
    "Invoice number",
    "Sale number",
    "Date",
    "Customer",
    "Payment method",
    "Item types",
    "Subtotal",
    "Discount",
    "Amount paid",
    "Outstanding balance",
    "Total",
    "Status",
  ];

  const rows = invoices.map((invoice) => [
    invoice.invoiceNumber,
    invoice.saleNumber,
    formatDocumentDate(invoice.createdAt),
    invoice.customerName,
    formatPaymentMethod(invoice.paymentMethod),
    invoice.items?.length ?? 0,
    Number(invoice.subtotal || 0).toFixed(2),
    Number(invoice.discount || 0).toFixed(2),
    Number(invoice.amountPaid || 0).toFixed(2),
    Number(invoice.outstandingBalance || 0).toFixed(2),
    Number(invoice.total || 0).toFixed(2),
    Number(invoice.outstandingBalance || 0) > 0 ? "Balance due" : "Paid",
  ]);

  const csv = [header, ...rows]
    .map((row) => row.map(escapeCsvCell).join(","))
    .join("\\r\\n");

  const dateStamp = new Date().toISOString().slice(0, 10);
  const filename = `${safeFilename(business?.name)}-invoice-list-${dateStamp}.csv`;
  const blob = new Blob(["\\uFEFF", csv], {
    type: "text/csv;charset=utf-8",
  });

  downloadBlob(blob, filename);
  return filename;
}

export function createInvoicePdf(invoice, business) {
  if (!invoice) {
    throw new Error("Select an invoice before creating a PDF.");
  }

  const pdf = new jsPDF({
    orientation: "portrait",
    unit: "pt",
    format: "a4",
  });

  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 42;
  const businessName = safeText(business?.name, "Business");
  const invoiceNumber = safeText(invoice.invoiceNumber, "Invoice");
  const customerName = safeText(invoice.customerName, "Walk-in customer");

  pdf.setFillColor(15, 42, 30);
  pdf.rect(0, 0, pageWidth, 104, "F");

  pdf.setTextColor(255, 255, 255);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(19);
  pdf.text(businessName, margin, 43);

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9);
  pdf.text(
    [
      safeText(business?.location, "Location not recorded"),
      safeText(business?.phone, "Phone not recorded"),
    ],
    margin,
    62,
  );

  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(11);
  pdf.text("INVOICE", pageWidth - margin, 36, { align: "right" });

  pdf.setFontSize(14);
  pdf.text(invoiceNumber, pageWidth - margin, 57, { align: "right" });

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9);
  pdf.text(
    formatDocumentDate(invoice.createdAt),
    pageWidth - margin,
    75,
    { align: "right" },
  );

  pdf.setTextColor(36, 55, 46);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(8);
  pdf.text("BILL TO", margin, 133);
  pdf.text("PAYMENT METHOD", pageWidth - 210, 133);

  pdf.setFontSize(11);
  pdf.text(customerName, margin, 151);
  pdf.text(
    formatPaymentMethod(invoice.paymentMethod),
    pageWidth - 210,
    151,
  );

  const itemRows = (invoice.items ?? []).map((item) => [
    safeText(item.name, "Unnamed item"),
    `${Number(item.quantity || 0)} ${safeText(item.unit, "unit")}(s)`,
    formatPdfCurrency(item.unitPrice),
    formatPdfCurrency(item.total),
  ]);

  autoTable(pdf, {
    startY: 177,
    head: [["Item", "Quantity", "Unit price", "Total"]],
    body: itemRows.length
      ? itemRows
      : [["No items recorded", "-", "-", "-"]],
    theme: "grid",
    margin: { left: margin, right: margin },
    styles: {
      cellPadding: 7,
      font: "helvetica",
      fontSize: 8.5,
      lineColor: [220, 230, 224],
      lineWidth: 0.5,
      textColor: [44, 60, 52],
      overflow: "linebreak",
    },
    headStyles: {
      fillColor: [25, 74, 52],
      textColor: [255, 255, 255],
      fontStyle: "bold",
    },
    alternateRowStyles: {
      fillColor: [247, 250, 248],
    },
    columnStyles: {
      0: { cellWidth: 225 },
      1: { cellWidth: 90 },
      2: { cellWidth: 100, halign: "right" },
      3: { cellWidth: 100, halign: "right" },
    },
  });

  let totalsY = (pdf.lastAutoTable?.finalY ?? 205) + 24;

  if (totalsY > pageHeight - 175) {
    pdf.addPage();
    totalsY = 60;
  }

  const totalsLabelX = pageWidth - 215;
  const totalsValueX = pageWidth - margin;

  function drawTotal(label, value, options = {}) {
    const { prominent = false } = options;

    if (prominent) {
      pdf.setFillColor(237, 247, 241);
      pdf.roundedRect(
        totalsLabelX - 12,
        totalsY - 15,
        totalsValueX - totalsLabelX + 24,
        27,
        5,
        5,
        "F",
      );
    }

    pdf.setTextColor(91, 106, 98);
    pdf.setFont("helvetica", prominent ? "bold" : "normal");
    pdf.setFontSize(prominent ? 10 : 8.5);
    pdf.text(label, totalsLabelX, totalsY);

    pdf.setTextColor(25, 43, 34);
    pdf.setFont("helvetica", "bold");
    pdf.text(formatPdfCurrency(value), totalsValueX, totalsY, {
      align: "right",
    });

    totalsY += prominent ? 35 : 22;
  }

  drawTotal("Subtotal", invoice.subtotal);
  drawTotal("Discount", invoice.discount);
  drawTotal("Amount paid", invoice.amountPaid);
  drawTotal("Total", invoice.total, { prominent: true });

  if (Number(invoice.outstandingBalance || 0) > 0) {
    pdf.setTextColor(170, 67, 44);
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(9);
    pdf.text("Balance due", totalsLabelX, totalsY);
    pdf.text(
      formatPdfCurrency(invoice.outstandingBalance),
      totalsValueX,
      totalsY,
      { align: "right" },
    );
  }

  const pageCount = pdf.getNumberOfPages();

  for (let pageNumber = 1; pageNumber <= pageCount; pageNumber += 1) {
    pdf.setPage(pageNumber);
    pdf.setDrawColor(220, 230, 224);
    pdf.line(margin, pageHeight - 52, pageWidth - margin, pageHeight - 52);

    pdf.setTextColor(104, 119, 111);
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(8);
    pdf.text(
      "Thank you for doing business with us.",
      margin,
      pageHeight - 33,
    );
    pdf.text(
      `Page ${pageNumber} of ${pageCount}`,
      pageWidth - margin,
      pageHeight - 33,
      { align: "right" },
    );
  }

  return pdf;
}

export function downloadInvoicePdf(invoice, business) {
  const pdf = createInvoicePdf(invoice, business);
  const filename = `${safeFilename(invoice.invoiceNumber)}.pdf`;

  pdf.save(filename);
  return filename;
}

function buildInvoiceShareText(invoice, business) {
  return [
    `${safeText(business?.name, "Business")} invoice`,
    `Invoice: ${safeText(invoice.invoiceNumber)}`,
    `Customer: ${safeText(invoice.customerName, "Walk-in customer")}`,
    `Date: ${formatDocumentDate(invoice.createdAt)}`,
    `Total: ${formatPdfCurrency(invoice.total)}`,
    `Payment: ${formatPaymentMethod(invoice.paymentMethod)}`,
    Number(invoice.outstandingBalance || 0) > 0
      ? `Balance due: ${formatPdfCurrency(invoice.outstandingBalance)}`
      : "Status: Paid",
  ].join("\\n");
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textArea = document.createElement("textarea");
  textArea.value = text;
  textArea.style.position = "fixed";
  textArea.style.opacity = "0";
  document.body.appendChild(textArea);
  textArea.focus();
  textArea.select();

  const copied = document.execCommand("copy");
  textArea.remove();

  if (!copied) {
    throw new Error("The invoice details could not be copied.");
  }
}

export async function shareInvoice(invoice, business) {
  if (!invoice) {
    throw new Error("Select an invoice before sharing.");
  }

  const title = `${safeText(invoice.invoiceNumber)} - ${safeText(
    business?.name,
    "Invoice",
  )}`;
  const text = buildInvoiceShareText(invoice, business);

  if (navigator.share) {
    const pdf = createInvoicePdf(invoice, business);
    const pdfBlob = pdf.output("blob");
    const pdfFile = new File(
      [pdfBlob],
      `${safeFilename(invoice.invoiceNumber)}.pdf`,
      { type: "application/pdf" },
    );

    const shareData = {
      title,
      text,
    };

    if (navigator.canShare?.({ files: [pdfFile] })) {
      shareData.files = [pdfFile];
    }

    await navigator.share(shareData);

    return shareData.files
      ? "Invoice PDF shared successfully."
      : "Invoice details shared successfully.";
  }

  await copyText(text);
  return "Sharing is unavailable on this device, so the invoice details were copied.";
}



// Creates a branded receipt for one payment made against a sale.
export function createReceiptPdf(receipt, sale, business) {
  if (!receipt) {
    throw new Error("Select a receipt before creating a PDF.");
  }

  const pdf = new jsPDF({
    orientation: "portrait",
    unit: "pt",
    format: "a5",
  });

  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 34;

  pdf.setFillColor(15, 42, 30);
  pdf.rect(0, 0, pageWidth, 92, "F");

  pdf.setTextColor(255, 255, 255);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(17);
  pdf.text(safeText(business?.name, "Business"), margin, 37);

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(8.5);
  pdf.text(
    safeText(business?.phone, "Phone not recorded"),
    margin,
    55,
  );

  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(11);
  pdf.text("PAYMENT RECEIPT", pageWidth - margin, 32, {
    align: "right",
  });

  pdf.setFontSize(13);
  pdf.text(
    safeText(receipt.receiptNumber, "Receipt"),
    pageWidth - margin,
    52,
    { align: "right" },
  );

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(8.5);
  pdf.text(
    formatDocumentDate(receipt.createdAt),
    pageWidth - margin,
    69,
    { align: "right" },
  );

  pdf.setTextColor(35, 53, 44);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(8);
  pdf.text("RECEIVED FROM", margin, 122);
  pdf.text("PAYMENT METHOD", pageWidth - margin, 122, {
    align: "right",
  });

  pdf.setFontSize(11);
  pdf.text(
    safeText(receipt.customerName, "Walk-in customer"),
    margin,
    141,
  );
  pdf.text(
    formatPaymentMethod(receipt.paymentMethod),
    pageWidth - margin,
    141,
    { align: "right" },
  );

  const amountY = 183;
  pdf.setFillColor(237, 247, 241);
  pdf.roundedRect(margin, amountY - 22, pageWidth - margin * 2, 55, 7, 7, "F");

  pdf.setTextColor(82, 99, 90);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(8);
  pdf.text("AMOUNT RECEIVED", margin + 15, amountY - 2);

  pdf.setTextColor(15, 77, 61);
  pdf.setFontSize(18);
  pdf.text(
    formatPdfCurrency(receipt.amount),
    pageWidth - margin - 15,
    amountY + 7,
    { align: "right" },
  );

  const detailRows = [
    ["Receipt number", safeText(receipt.receiptNumber)],
    ["Invoice number", safeText(receipt.invoiceNumber)],
    ["Sale number", safeText(receipt.saleNumber)],
    ["Reference", safeText(receipt.reference, "Not provided")],
    ["Received by", safeText(receipt.cashier, "Not recorded")],
  ];

  autoTable(pdf, {
    startY: amountY + 55,
    body: detailRows,
    theme: "plain",
    margin: { left: margin, right: margin },
    styles: {
      cellPadding: 6,
      font: "helvetica",
      fontSize: 8.5,
      textColor: [45, 61, 53],
    },
    columnStyles: {
      0: {
        cellWidth: 105,
        fontStyle: "bold",
        textColor: [92, 108, 99],
      },
      1: {
        cellWidth: pageWidth - margin * 2 - 105,
      },
    },
  });

  if (sale?.items?.length) {
    autoTable(pdf, {
      startY: (pdf.lastAutoTable?.finalY ?? 290) + 15,
      head: [["Items covered by this sale", "Qty"]],
      body: sale.items.map((item) => [
        safeText(item.name, "Unnamed item"),
        `${Number(item.quantity || 0)} ${safeText(item.unit, "unit")}(s)`,
      ]),
      theme: "grid",
      margin: { left: margin, right: margin },
      styles: {
        cellPadding: 5,
        font: "helvetica",
        fontSize: 7.8,
        lineColor: [220, 230, 224],
        lineWidth: 0.5,
        textColor: [44, 60, 52],
      },
      headStyles: {
        fillColor: [25, 74, 52],
        textColor: [255, 255, 255],
        fontStyle: "bold",
      },
    });
  }

  pdf.setDrawColor(220, 230, 224);
  pdf.line(margin, pageHeight - 45, pageWidth - margin, pageHeight - 45);

  pdf.setTextColor(104, 119, 111);
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(7.5);
  pdf.text(
    "This receipt confirms payment received.",
    margin,
    pageHeight - 27,
  );

  return pdf;
}

export function downloadReceiptPdf(receipt, sale, business) {
  const pdf = createReceiptPdf(receipt, sale, business);
  const filename = `${safeFilename(receipt.receiptNumber)}.pdf`;

  pdf.save(filename);
  return filename;
}

// Creates one waybill containing every item in the selected sale.
export function createWaybillPdf(sale, business) {
  if (!sale?.waybill) {
    throw new Error("Create the waybill before downloading it.");
  }

  const waybill = sale.waybill;
  const pdf = new jsPDF({
    orientation: "portrait",
    unit: "pt",
    format: "a4",
  });

  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 42;

  pdf.setFillColor(15, 42, 30);
  pdf.rect(0, 0, pageWidth, 104, "F");

  pdf.setTextColor(255, 255, 255);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(19);
  pdf.text(safeText(business?.name, "Business"), margin, 43);

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9);
  pdf.text(
    [
      safeText(business?.location, "Location not recorded"),
      safeText(business?.phone, "Phone not recorded"),
    ],
    margin,
    62,
  );

  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(11);
  pdf.text("WAYBILL", pageWidth - margin, 36, {
    align: "right",
  });

  pdf.setFontSize(14);
  pdf.text(
    safeText(waybill.waybillNumber, "Waybill"),
    pageWidth - margin,
    57,
    { align: "right" },
  );

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9);
  pdf.text(
    formatDocumentDate(waybill.dispatchDate),
    pageWidth - margin,
    75,
    { align: "right" },
  );

  const deliveryRows = [
    ["Recipient", safeText(waybill.recipientName)],
    ["Phone", safeText(waybill.recipientPhone)],
    ["Delivery address", safeText(waybill.deliveryAddress)],
    ["Driver", safeText(waybill.driverName)],
    ["Vehicle number", safeText(waybill.vehicleNumber)],
    ["Delivery status", safeText(waybill.status)],
    ["Invoice number", safeText(sale.invoiceNumber)],
    ["Sale number", safeText(sale.saleNumber)],
  ];

  autoTable(pdf, {
    startY: 130,
    body: deliveryRows,
    theme: "plain",
    margin: { left: margin, right: margin },
    styles: {
      cellPadding: 5.5,
      font: "helvetica",
      fontSize: 8.5,
      textColor: [44, 60, 52],
    },
    columnStyles: {
      0: {
        cellWidth: 115,
        fontStyle: "bold",
        textColor: [92, 108, 99],
      },
      1: {
        cellWidth: pageWidth - margin * 2 - 115,
      },
    },
  });

  const itemRows = (sale.items ?? []).map((item, index) => [
    String(index + 1),
    safeText(item.name, "Unnamed item"),
    `${Number(item.quantity || 0)} ${safeText(item.unit, "unit")}(s)`,
  ]);

  autoTable(pdf, {
    startY: (pdf.lastAutoTable?.finalY ?? 240) + 18,
    head: [["#", "Item description", "Quantity dispatched"]],
    body: itemRows.length
      ? itemRows
      : [["1", "No items recorded", "-"]],
    theme: "grid",
    margin: { left: margin, right: margin },
    styles: {
      cellPadding: 7,
      font: "helvetica",
      fontSize: 8.5,
      lineColor: [220, 230, 224],
      lineWidth: 0.5,
      textColor: [44, 60, 52],
      overflow: "linebreak",
    },
    headStyles: {
      fillColor: [25, 74, 52],
      textColor: [255, 255, 255],
      fontStyle: "bold",
    },
    columnStyles: {
      0: { cellWidth: 35, halign: "center" },
      1: { cellWidth: 320 },
      2: { cellWidth: 155 },
    },
  });

  let notesY = (pdf.lastAutoTable?.finalY ?? 360) + 24;

  if (notesY > pageHeight - 170) {
    pdf.addPage();
    notesY = 60;
  }

  pdf.setTextColor(87, 103, 94);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(8);
  pdf.text("DELIVERY NOTES", margin, notesY);

  pdf.setTextColor(44, 60, 52);
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(8.5);
  pdf.text(
    pdf.splitTextToSize(
      safeText(waybill.deliveryNotes, "No delivery notes recorded."),
      pageWidth - margin * 2,
    ),
    margin,
    notesY + 18,
  );

  const signatureY = pageHeight - 90;
  pdf.setDrawColor(170, 184, 176);
  pdf.line(margin, signatureY, margin + 180, signatureY);
  pdf.line(pageWidth - margin - 180, signatureY, pageWidth - margin, signatureY);

  pdf.setTextColor(95, 110, 102);
  pdf.setFontSize(8);
  pdf.text("Dispatched by", margin, signatureY + 15);
  pdf.text(
    "Received by",
    pageWidth - margin - 180,
    signatureY + 15,
  );

  return pdf;
}

export function downloadWaybillPdf(sale, business) {
  const pdf = createWaybillPdf(sale, business);
  const filename = `${safeFilename(sale.waybill.waybillNumber)}.pdf`;

  pdf.save(filename);
  return filename;
}



// Downloads one consolidated PDF containing every transaction for one customer.
export function exportCustomerStatementPdf(
  customer,
  sales,
  payments,
  business,
) {
  if (!customer) {
    throw new Error("Select a customer before creating a statement.");
  }

  if (!sales.length) {
    throw new Error("This customer has no purchase records to include.");
  }

  // Uses A5 landscape to reduce unnecessary empty space for short statements.
  const document = new jsPDF({
    orientation: "landscape",
    unit: "pt",
    format: "a5",
  });

  const pageWidth = document.internal.pageSize.getWidth();
  const pageHeight = document.internal.pageSize.getHeight();
  const margin = 22;
  const generatedAt = new Date();

  const totalPurchases = sales.reduce(
    (sum, sale) => sum + Number(sale.total || 0),
    0,
  );
  const totalPaid = sales.reduce(
    (sum, sale) => sum + Number(sale.amountPaid || 0),
    0,
  );
  const totalBalance = sales.reduce(
    (sum, sale) => sum + Number(sale.outstandingBalance || 0),
    0,
  );

  document.setFillColor(15, 42, 30);
  document.rect(0, 0, pageWidth, 68, "F");

  document.setTextColor(255, 255, 255);
  document.setFont("helvetica", "bold");
  document.setFontSize(15);
  document.text(safeText(business?.name, "Business"), margin, 29);

  document.setFont("helvetica", "normal");
  document.setFontSize(7.2);
  document.text(
    `${safeText(business?.location, "Location not recorded")} · ${safeText(
      business?.phone,
      "Phone not recorded",
    )}`,
    margin,
    45,
  );

  document.setFont("helvetica", "bold");
  document.setFontSize(10.5);
  document.text(
    "CONSOLIDATED CUSTOMER STATEMENT",
    pageWidth - margin,
    27,
    { align: "right" },
  );

  document.setFont("helvetica", "normal");
  document.setFontSize(7.2);
  document.text(
    `Generated ${formatDocumentDate(generatedAt)}`,
    pageWidth - margin,
    44,
    { align: "right" },
  );

  document.setTextColor(39, 56, 47);
  document.setFont("helvetica", "bold");
  document.setFontSize(7);
  document.text("CUSTOMER", margin, 88);
  document.text("CONTACT", 210, 88);
  document.text("ADDRESS", 344, 88);

  document.setFontSize(9.2);
  document.text(safeText(customer.name), margin, 103);
  document.text(safeText(customer.phone), 210, 103);

  document.setFont("helvetica", "normal");
  document.setFontSize(8);
  document.text(
    document.splitTextToSize(
      safeText(customer.address),
      pageWidth - 344 - margin,
    ),
    344,
    103,
  );

  const summaryY = 124;
  const summaryGap = 8;
  const summaryWidth = (pageWidth - margin * 2 - summaryGap * 2) / 3;
  const summaryItems = [
    ["Total purchases", formatPdfCurrency(totalPurchases)],
    ["Total received", formatPdfCurrency(totalPaid)],
    ["Outstanding balance", formatPdfCurrency(totalBalance)],
  ];

  summaryItems.forEach(([label, value], index) => {
    const x = margin + index * (summaryWidth + summaryGap);

    document.setFillColor(241, 248, 244);
    document.roundedRect(x, summaryY, summaryWidth, 35, 5, 5, "F");

    document.setTextColor(91, 106, 98);
    document.setFont("helvetica", "normal");
    document.setFontSize(6.4);
    document.text(label, x + 9, summaryY + 12);

    document.setTextColor(22, 52, 38);
    document.setFont("helvetica", "bold");
    document.setFontSize(9.5);
    document.text(value, x + 9, summaryY + 27);
  });

  // Combines sale and invoice references and payment figures to keep the table compact.
  const purchaseRows = sales.flatMap((sale) =>
    (sale.items ?? []).map((item) => [
      formatDocumentDate(sale.createdAt),
      `${safeText(sale.invoiceNumber)}\n${safeText(sale.saleNumber)}`,
      safeText(item.name, "Unnamed item"),
      `${Number(item.quantity || 0)} ${safeText(item.unit, "unit")}(s)`,
      formatPdfCurrency(item.unitPrice),
      formatPdfCurrency(item.total),
      `Paid: ${formatPdfCurrency(sale.amountPaid)}\nBalance: ${formatPdfCurrency(
        sale.outstandingBalance,
      )}`,
    ]),
  );

  autoTable(document, {
    startY: 176,
    head: [[
      "Date",
      "Reference",
      "Product",
      "Quantity",
      "Unit price",
      "Line total",
      "Payment",
    ]],
    body: purchaseRows,
    theme: "grid",
    margin: {
      left: margin,
      right: margin,
      bottom: 30,
    },
    styles: {
      cellPadding: 3.6,
      font: "helvetica",
      fontSize: 6.4,
      lineColor: [220, 230, 224],
      lineWidth: 0.4,
      textColor: [44, 60, 52],
      overflow: "linebreak",
      valign: "middle",
    },
    headStyles: {
      fillColor: [25, 74, 52],
      textColor: [255, 255, 255],
      fontStyle: "bold",
      fontSize: 6.3,
    },
    alternateRowStyles: {
      fillColor: [247, 250, 248],
    },
    // A5 landscape printable width is about 551pt after margins.
    // These widths total exactly 551pt, so no column can run off the page.
    columnStyles: {
      0: { cellWidth: 50 },
      1: { cellWidth: 62 },
      2: { cellWidth: 145 },
      3: { cellWidth: 60 },
      4: { cellWidth: 66, halign: "right" },
      5: { cellWidth: 70, halign: "right" },
      6: {
        cellWidth: 98,
        halign: "right",
        fontSize: 6,
      },
    },
  });

  const saleIds = new Set(sales.map((sale) => sale.id));
  const statementPayments = payments.filter((payment) =>
    saleIds.has(payment.saleId),
  );

  if (statementPayments.length) {
    let receiptStartY = (document.lastAutoTable?.finalY ?? 230) + 13;

    if (receiptStartY > pageHeight - 88) {
      document.addPage();
      receiptStartY = 30;
    }

    document.setTextColor(39, 56, 47);
    document.setFont("helvetica", "bold");
    document.setFontSize(8);
    document.text("PAYMENT RECEIPTS", margin, receiptStartY);

    autoTable(document, {
      startY: receiptStartY + 8,
      head: [[
        "Date",
        "Receipt",
        "Invoice",
        "Method",
        "Reference",
        "Amount",
      ]],
      body: statementPayments.map((payment) => [
        formatDocumentDate(payment.createdAt),
        safeText(payment.receiptNumber),
        safeText(payment.invoiceNumber),
        formatPaymentMethod(payment.paymentMethod),
        safeText(payment.reference, "Not provided"),
        formatPdfCurrency(payment.amount),
      ]),
      theme: "grid",
      margin: {
        left: margin,
        right: margin,
        bottom: 30,
      },
      styles: {
        cellPadding: 3.4,
        font: "helvetica",
        fontSize: 6.3,
        lineColor: [220, 230, 224],
        lineWidth: 0.4,
        textColor: [44, 60, 52],
      },
      headStyles: {
        fillColor: [25, 74, 52],
        textColor: [255, 255, 255],
        fontStyle: "bold",
      },
      // Keeps the receipts table inside the same 551pt printable width.
      columnStyles: {
        0: { cellWidth: 60 },
        1: { cellWidth: 77 },
        2: { cellWidth: 77 },
        3: { cellWidth: 75 },
        4: { cellWidth: 185 },
        5: { cellWidth: 77, halign: "right" },
      },
    });
  }

  const pageCount = document.getNumberOfPages();

  for (let pageNumber = 1; pageNumber <= pageCount; pageNumber += 1) {
    document.setPage(pageNumber);
    document.setDrawColor(220, 230, 224);
    document.line(
      margin,
      pageHeight - 22,
      pageWidth - margin,
      pageHeight - 22,
    );

    document.setTextColor(105, 119, 111);
    document.setFont("helvetica", "normal");
    document.setFontSize(6.2);
    document.text(
      `${safeText(customer.name)} purchase statement`,
      margin,
      pageHeight - 10,
    );
    document.text(
      `Page ${pageNumber} of ${pageCount}`,
      pageWidth - margin,
      pageHeight - 10,
      { align: "right" },
    );
  }

  const dateStamp = generatedAt.toISOString().slice(0, 10);
  const filename =
    `${safeFilename(customer.name)}-customer-statement-${dateStamp}.pdf`;

  document.save(filename);
  return filename;
}


// Downloads the visible Sales History records as a CSV file.
export function exportSalesHistoryCsv(sales, business) {
  if (!sales.length) {
    throw new Error("There are no sales records to export.");
  }

  const header = [
    "Sale number",
    "Invoice number",
    "Date",
    "Customer",
    "Cashier",
    "Items",
    "Payment method",
    "Amount paid",
    "Outstanding balance",
    "Total",
    "Status",
  ];

  const rows = sales.map((sale) => [
    sale.saleNumber,
    sale.invoiceNumber,
    formatDocumentDate(sale.createdAt),
    sale.customerName,
    sale.cashier,
    (sale.items ?? []).reduce(
      (sum, item) => sum + Number(item.quantity || 0),
      0,
    ),
    formatPaymentMethod(sale.paymentMethod),
    Number(sale.amountPaid || 0).toFixed(2),
    Number(sale.outstandingBalance || 0).toFixed(2),
    Number(sale.total || 0).toFixed(2),
    Number(sale.outstandingBalance || 0) > 0
      ? "Part paid"
      : "Completed",
  ]);

  const csv = [header, ...rows]
    .map((row) => row.map(escapeCsvCell).join(","))
    .join("\r\n");

  const dateStamp = new Date().toISOString().slice(0, 10);
  const filename =
    `${safeFilename(business?.name)}-sales-history-${dateStamp}.csv`;

  downloadBlob(
    new Blob(["\uFEFF", csv], {
      type: "text/csv;charset=utf-8",
    }),
    filename,
  );

  return filename;
}

// Downloads the visible Sales History records as a branded PDF.
export function exportSalesHistoryPdf(sales, business) {
  if (!sales.length) {
    throw new Error("There are no sales records to export.");
  }

  const document = new jsPDF({
    orientation: "landscape",
    unit: "pt",
    format: "a4",
  });

  const pageWidth = document.internal.pageSize.getWidth();
  const pageHeight = document.internal.pageSize.getHeight();
  const margin = 30;

  document.setFillColor(15, 42, 30);
  document.rect(0, 0, pageWidth, 82, "F");

  document.setTextColor(255, 255, 255);
  document.setFont("helvetica", "bold");
  document.setFontSize(18);
  document.text(safeText(business?.name, "Business"), margin, 34);

  document.setFont("helvetica", "normal");
  document.setFontSize(8.5);
  document.text(
    [
      safeText(business?.location, "Location not recorded"),
      safeText(business?.phone, "Phone not recorded"),
    ],
    margin,
    50,
  );

  document.setFont("helvetica", "bold");
  document.setFontSize(13);
  document.text("SALES HISTORY", pageWidth - margin, 31, {
    align: "right",
  });

  document.setFont("helvetica", "normal");
  document.setFontSize(8.5);
  document.text(
    `${sales.length} transaction(s)`,
    pageWidth - margin,
    48,
    { align: "right" },
  );
  document.text(
    `Generated ${formatDocumentDate(new Date())}`,
    pageWidth - margin,
    63,
    { align: "right" },
  );

  const rows = sales.map((sale) => [
    safeText(sale.saleNumber),
    safeText(sale.invoiceNumber),
    formatDocumentDate(sale.createdAt),
    safeText(sale.customerName, "Walk-in customer"),
    safeText(sale.cashier, "Not recorded"),
    (sale.items ?? []).length
      ? sale.items
          .map(
            (item) =>
              `${safeText(item.name, "Unnamed item")} x ${Number(
                item.quantity || 0,
              )}`,
          )
          .join("\n")
      : "No items recorded",
    formatPaymentMethod(sale.paymentMethod),
    formatPdfCurrency(sale.amountPaid),
    formatPdfCurrency(sale.outstandingBalance),
    formatPdfCurrency(sale.total),
    Number(sale.outstandingBalance || 0) > 0
      ? "Part paid"
      : "Completed",
  ]);

  autoTable(document, {
    startY: 100,
    head: [[
      "Sale",
      "Invoice",
      "Date",
      "Customer",
      "Cashier",
      "Purchased items",
      "Payment",
      "Paid",
      "Balance",
      "Total",
      "Status",
    ]],
    body: rows,
    theme: "grid",
    margin: {
      left: margin,
      right: margin,
      bottom: 52,
    },
    styles: {
      cellPadding: 4.7,
      font: "helvetica",
      fontSize: 6.8,
      lineColor: [220, 230, 224],
      lineWidth: 0.45,
      textColor: [44, 60, 52],
      overflow: "linebreak",
      valign: "middle",
    },
    headStyles: {
      fillColor: [25, 74, 52],
      textColor: [255, 255, 255],
      fontStyle: "bold",
      fontSize: 6.8,
    },
    alternateRowStyles: {
      fillColor: [247, 250, 248],
    },
    columnStyles: {
      0: { cellWidth: 55 },
      1: { cellWidth: 55 },
      2: { cellWidth: 58 },
      3: { cellWidth: 80 },
      4: { cellWidth: 65 },
      5: { cellWidth: 110 },
      6: { cellWidth: 58 },
      7: { cellWidth: 62, halign: "right" },
      8: { cellWidth: 62, halign: "right" },
      9: { cellWidth: 62, halign: "right" },
      10: { cellWidth: 48 },
    },
  });

  const pageCount = document.getNumberOfPages();

  for (let pageNumber = 1; pageNumber <= pageCount; pageNumber += 1) {
    document.setPage(pageNumber);
    document.setDrawColor(220, 230, 224);
    document.line(
      margin,
      pageHeight - 38,
      pageWidth - margin,
      pageHeight - 38,
    );

    document.setTextColor(105, 119, 111);
    document.setFont("helvetica", "normal");
    document.setFontSize(7.5);
    document.text(
      "Generated by StockFlow.",
      margin,
      pageHeight - 22,
    );
    document.text(
      `Page ${pageNumber} of ${pageCount}`,
      pageWidth - margin,
      pageHeight - 22,
      { align: "right" },
    );
  }

  const dateStamp = new Date().toISOString().slice(0, 10);
  const filename =
    `${safeFilename(business?.name)}-sales-history-${dateStamp}.pdf`;

  document.save(filename);
  return filename;
}
