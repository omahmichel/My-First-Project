import { jsPDF } from "jspdf";
import { autoTable } from "jspdf-autotable";


function safeText(value, fallback = "Not recorded") {
  const text = String(value ?? "").trim();
  return (text || fallback).replaceAll("₵", "GHS ");
}


function safeFilename(value) {
  return safeText(value, "report")
    .replace(/[<>:"/\\|?*\u0000-\u001F]/g, "-")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}


function documentValue(value, format) {
  if (format === "currency") {
    return `GHS ${Number(value || 0).toLocaleString("en-GH", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }

  if (format === "percent") {
    return `${Number(value || 0).toFixed(2)}%`;
  }

  if (format === "boolean") return value ? "Yes" : "No";

  if (format === "date") {
    if (!value) return "Not recorded";
    return new Intl.DateTimeFormat("en-GH", {
      dateStyle: "medium",
    }).format(new Date(value));
  }

  if (format === "number") {
    return Number(value || 0).toLocaleString("en-GH");
  }

  return safeText(value);
}


function addWrappedSection(pdf, title, lines, y, margin, pageWidth) {
  const pageHeight = pdf.internal.pageSize.getHeight();
  let cursor = y;

  if (cursor > pageHeight - 90) {
    pdf.addPage();
    cursor = 46;
  }

  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(11);
  pdf.setTextColor(15, 23, 42);
  pdf.text(title, margin, cursor);
  cursor += 16;

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9);
  pdf.setTextColor(71, 85, 105);

  (lines || []).forEach((line) => {
    const wrapped = pdf.splitTextToSize(
      safeText(line),
      pageWidth - margin * 2 - 12,
    );

    if (cursor + wrapped.length * 12 > pageHeight - 42) {
      pdf.addPage();
      cursor = 46;
    }

    pdf.text("-", margin + 2, cursor);
    pdf.text(wrapped, margin + 12, cursor);
    cursor += wrapped.length * 12 + 6;
  });

  return cursor + 6;
}


export function exportIntelligenceReportPdf({ business, report }) {
  if (!report?.payload) {
    throw new Error("Select an Intelligence report before downloading.");
  }

  const payload = report.payload;
  const pdf = new jsPDF({
    orientation: "portrait",
    unit: "pt",
    format: "a4",
  });

  const pageWidth = pdf.internal.pageSize.getWidth();
  const margin = 44;

  pdf.setFillColor(15, 23, 42);
  pdf.rect(0, 0, pageWidth, 102, "F");

  pdf.setTextColor(255, 255, 255);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(18);
  pdf.text(safeText(report.title), margin, 45);

  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9);
  pdf.text(
    `${safeText(business?.name, "StockFlow business")}  |  ${
      safeText(payload.period?.label, "Current position")
    }`,
    margin,
    66,
  );
  pdf.text(
    `Generated ${new Intl.DateTimeFormat("en-GH", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(report.generatedAt))}`,
    margin,
    83,
  );

  let y = 130;

  autoTable(pdf, {
    startY: y,
    head: [["Metric", "Verified value"]],
    body: (payload.metrics || []).map((metric) => [
      safeText(metric.label),
      documentValue(metric.value, metric.format),
    ]),
    theme: "grid",
    margin: { left: margin, right: margin },
    styles: {
      font: "helvetica",
      fontSize: 8.5,
      cellPadding: 6,
    },
    headStyles: {
      fillColor: [37, 99, 235],
      textColor: [255, 255, 255],
    },
  });

  y = (pdf.lastAutoTable?.finalY ?? y) + 24;

  if (report.aiNarrative) {
    const wrapped = pdf.splitTextToSize(
      safeText(report.aiNarrative),
      pageWidth - margin * 2,
    );

    y = addWrappedSection(
      pdf,
      "AI management narrative",
      [wrapped.join("\n")],
      y,
      margin,
      pageWidth,
    );
  }

  const questions = payload.managementQuestions || {};

  y = addWrappedSection(
    pdf,
    "What happened?",
    questions.whatHappened,
    y,
    margin,
    pageWidth,
  );
  y = addWrappedSection(
    pdf,
    "Why?",
    questions.why,
    y,
    margin,
    pageWidth,
  );
  y = addWrappedSection(
    pdf,
    "What needs attention?",
    questions.attention,
    y,
    margin,
    pageWidth,
  );
  y = addWrappedSection(
    pdf,
    "What should I do next?",
    questions.nextActions,
    y,
    margin,
    pageWidth,
  );

  (payload.sections || []).forEach((section) => {
    if (!section.rows?.length) return;

    const pageHeight = pdf.internal.pageSize.getHeight();

    if (y > pageHeight - 120) {
      pdf.addPage();
      y = 46;
    }

    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(11);
    pdf.setTextColor(15, 23, 42);
    pdf.text(safeText(section.title), margin, y);

    autoTable(pdf, {
      startY: y + 10,
      head: [
        section.columns.map((column) => safeText(column.label)),
      ],
      body: section.rows.map((row) =>
        section.columns.map((column) =>
          documentValue(row[column.key], column.format),
        ),
      ),
      theme: "grid",
      margin: { left: margin, right: margin },
      styles: {
        font: "helvetica",
        fontSize: 7.5,
        cellPadding: 5,
      },
      headStyles: {
        fillColor: [226, 232, 240],
        textColor: [15, 23, 42],
      },
    });

    y = (pdf.lastAutoTable?.finalY ?? y) + 24;
  });

  const totalPages = pdf.getNumberOfPages();

  for (let page = 1; page <= totalPages; page += 1) {
    pdf.setPage(page);
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(7.5);
    pdf.setTextColor(100, 116, 139);
    pdf.text(
      `StockFlow Intelligence  |  Page ${page} of ${totalPages}`,
      margin,
      pdf.internal.pageSize.getHeight() - 22,
    );
  }

  const filename = `${safeFilename(
    business?.name,
  )}-${safeFilename(report.reportType)}-${
    new Date(report.generatedAt).toISOString().slice(0, 10)
  }.pdf`;

  pdf.save(filename);
  return filename;
}
