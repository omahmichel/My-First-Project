// Compatibility names for invoice and purchase-record pages.
// All file delivery is implemented in the shared documentDelivery module.
import {
  canSharePdfFile,
  downloadPdfFile,
  documentDeliveryMessage,
  sharePdfFile,
} from "./documentDelivery";

export const canShareInvoiceFile = canSharePdfFile;
export const shareInvoiceFile = sharePdfFile;

export function downloadInvoiceFile(prepared) {
  return documentDeliveryMessage(downloadPdfFile(prepared));
}
