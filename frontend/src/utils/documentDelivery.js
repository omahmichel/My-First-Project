// Shared PDF delivery for all StockFlow businesses and document types.
// New PDF exports should call deliverPdfDocument. Share dialogs can prepare a
// file first, then call sharePdfFile directly from their final button click.

function pdfFilename(value) {
  const name = String(value || "document.pdf")
    .replace(/[<>:"/\\|?*\u0000-\u001F]/g, "-")
    .trim();
  if (!name || name.toLowerCase() === ".pdf") return "document.pdf";
  return /\.pdf$/i.test(name) ? name : `${name}.pdf`;
}

export function canSharePdfFile(file) {
  try {
    return Boolean(window.isSecureContext && navigator.share &&
      navigator.canShare?.({ files: [file] }));
  } catch {
    return false;
  }
}

export function downloadPdfFile({ file, filename }) {
  const name = pdfFilename(filename || file?.name);
  const anchor = document.createElement("a");
  const url = URL.createObjectURL(file);
  try {
    anchor.href = url;
    anchor.download = name;
    document.body.appendChild(anchor);
    anchor.click();
  } finally {
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }
  return { filename: name, deliveryMode: "download" };
}

export function deliverPdfDocument(pdf, filename) {
  return downloadPdfFile(preparePdfShare({ pdf, filename }));
}

export function documentDeliveryMessage(result) {
  const filename = typeof result === "string" ? result : result?.filename;
  return `Download requested: ${filename || "Document"}. Check Downloads to open or share the file.`;
}

export function preparePdfShare({ pdf, filename, title, label = "Document" }) {
  const name = pdfFilename(filename);
  const file = new File([pdf.output("blob")], name, { type: "application/pdf" });
  return { file, filename: name, title, label };
}

// Strict sharing for dialogs that already offer a separate Download button.
// Do not turn cancellation or a failed native share into an unwanted download.
export function sharePdfFile({ file }) {
  if (!canSharePdfFile(file)) {
    throw new Error("Download the PDF, then attach it in WhatsApp or another app.");
  }
  return navigator.share({ files: [file] });
}

// Compatibility entry point for existing one-button share callers.
export async function sharePreparedPdfDocument(prepared) {
  if (!canSharePdfFile(prepared.file)) {
    return documentDeliveryMessage(downloadPdfFile(prepared))
      + " To send it in WhatsApp, attach it as a Document.";
  }
  await sharePdfFile(prepared);
  return `${prepared.label || "Document"} PDF handed to the selected app. Check that app to confirm delivery.`;
}

export async function sharePdfDocument(options) {
  return sharePreparedPdfDocument(preparePdfShare(options));
}
