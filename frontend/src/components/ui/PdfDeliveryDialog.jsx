import { useRef, useState } from "react";
import { Download, Share2 } from "lucide-react";
import Button from "./Button";
import Modal from "./Modal";
import {
  canSharePdfFile,
  downloadPdfFile,
  documentDeliveryMessage,
  sharePdfFile,
} from "../../utils/documentDelivery";

// Prepare the file before mounting this dialog so Share retains user activation.
export default function PdfDeliveryDialog({ prepared, title = "Share your PDF", onClose }) {
  const pending = useRef(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function handleShare() {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setMessage("");
    setError("");
    try {
      await sharePdfFile(prepared);
      setMessage("PDF handed to the selected app. Check that app to confirm delivery.");
    } catch (shareError) {
      if (shareError?.name !== "AbortError") {
        setError("Sharing could not open. Download the PDF, then attach it in your chosen app.");
      }
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  function handleDownload() {
    if (pending.current) return;
    setError("");
    setMessage("");
    try {
      setMessage(documentDeliveryMessage(downloadPdfFile(prepared)));
    } catch (downloadError) {
      setError(downloadError.message || "The PDF download could not start.");
    }
  }

  return (
    <Modal open={true} title={title} onClose={() => { if (!pending.current) onClose(); }}>
      <div className="page-stack">
        <p>{prepared.filename}</p>
        {canSharePdfFile(prepared.file) ? (
          <>
            <p>Choose WhatsApp or another app, then select your recipient. Your document is attached as a PDF.</p>
            <Button onClick={handleShare} disabled={busy}>
              <Share2 size={17} /> {busy ? "Sharing..." : "Share PDF file"}
            </Button>
          </>
        ) : (
          <p>Download the PDF, then attach it in WhatsApp or another app.</p>
        )}
        <Button variant="secondary" onClick={handleDownload} disabled={busy}>
          <Download size={17} /> Download PDF
        </Button>
        {message ? <p role="status">{message}</p> : null}
        {error ? <p role="alert" className="danger-text">{error}</p> : null}
      </div>
    </Modal>
  );
}
