// Central delivery and sharing rules for StockFlow-generated documents.

function isMobileDevice() {
  if (typeof navigator.userAgentData?.mobile === "boolean") {
    return navigator.userAgentData.mobile;
  }

  return /Android|iPhone|iPad|iPod|Mobile/i.test(
    navigator.userAgent || "",
  );
}

function shouldPreviewPdf() {
  return isMobileDevice() && !window.isSecureContext;
}

function openExternalUrl(url) {
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.target = "_blank";
  anchor.rel = "noopener noreferrer";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

export function deliverPdfDocument(pdf, filename) {
  if (!shouldPreviewPdf()) {
    pdf.save(filename);

    return {
      filename,
      deliveryMode: "download",
    };
  }

  const blob = pdf.output("blob");
  const url = URL.createObjectURL(blob);

  openExternalUrl(url);

  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);

  return {
    filename,
    deliveryMode: "preview",
  };
}

export function documentDeliveryMessage(result) {
  if (typeof result === "string") {
    return `${result} downloaded successfully.`;
  }

  if (result?.deliveryMode === "preview") {
    return `${result.filename} opened in the phone PDF viewer. Use the viewer to save, print or share it.`;
  }

  return `${result?.filename || "Document"} downloaded successfully.`;
}

export function preparePdfShare({
  pdf,
  filename,
  title,
  label = "Document",
}) {
  const blob = pdf.output("blob");
  const file = new File(
    [blob],
    filename,
    { type: "application/pdf" },
  );

  return {
    file,
    filename,
    title,
    label,
  };
}

export async function sharePreparedPdfDocument({
  file,
  title,
  label = "Document",
}) {
  if (!window.isSecureContext) {
    throw new Error(
      `${label} file sharing requires StockFlow to be opened over HTTPS. `
      + "The current local HTTP connection can download or preview the PDF, "
      + "but the browser will not securely attach it to WhatsApp.",
    );
  }

  if (
    !navigator.share ||
    !navigator.canShare?.({ files: [file] })
  ) {
    throw new Error(
      `This browser cannot share the ${label.toLowerCase()} PDF file directly. `
      + "Download the PDF and share the file manually, or use a supported "
      + "mobile browser on the secure StockFlow site.",
    );
  }

  // Invoke the native share API immediately from the final click.
  await navigator.share({
    title,
    files: [file],
  });

  return `${label} PDF shared successfully.`;
}

export async function sharePdfDocument(options) {
  return sharePreparedPdfDocument(preparePdfShare(options));
}
