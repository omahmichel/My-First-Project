import { X } from "lucide-react";
import { createPortal } from "react-dom";

export default function Modal({ open, title, description, children, onClose, size = "medium" }) {
  if (!open) return null;

  // Renders dialogs at the document root so app stacking contexts
  // cannot place the sidebar or topbar above the modal.
  return createPortal(
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className={`modal-card modal-card-${size}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <div>
            <h2>{title}</h2>
            {description ? <p>{description}</p> : null}
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close dialog">
            <X size={20} />
          </button>
        </header>
        <div className="modal-body">{children}</div>
      </section>
    </div>,
    document.body,
  );
}
