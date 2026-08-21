import { LockKeyhole, ShieldAlert, X } from "lucide-react";

import "../../styles/access-blocked-modal.css";

function formatRole(role) {
  if (!role) return "staff";
  return String(role).replaceAll("_", " ");
}

export default function AccessBlockedModal({
  open,
  businessName,
  onClose,
  variant = "subscription",
  role,
  areaLabel,
  message,
}) {
  if (!open) return null;

  const isRoleRestriction = variant === "role";
  const Icon = isRoleRestriction ? ShieldAlert : LockKeyhole;

  return (
    <div
      className="access-blocked-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="access-blocked-modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="access-blocked-title"
        aria-describedby="access-blocked-description"
      >
        <button
          type="button"
          className="access-blocked-close"
          onClick={onClose}
          aria-label="Close access warning"
        >
          <X size={19} />
        </button>

        <div className="access-blocked-icon" aria-hidden="true">
          <Icon size={28} />
        </div>

        <span className="access-blocked-eyebrow">
          {isRoleRestriction
            ? "Permission required"
            : "Workspace access blocked"}
        </span>

        <h2 id="access-blocked-title">
          {isRoleRestriction
            ? "You do not have access to this area"
            : "Access is temporarily unavailable"}
        </h2>

        <p id="access-blocked-description">
          {isRoleRestriction ? (
            <>
              Your <strong>{formatRole(role)}</strong> role does not have
              permission to open the {areaLabel || "requested"} area
              {businessName ? (
                <>
                  {" "}for <strong>{businessName}</strong>
                </>
              ) : null}
              .
            </>
          ) : businessName ? (
            <>
              <strong>{businessName}</strong> is currently locked because its
              StockFlow subscription has expired.
            </>
          ) : (
            "This StockFlow workspace is currently locked because its subscription has expired."
          )}
        </p>

        <div className="access-blocked-notice">
          <strong>
            {isRoleRestriction ? "Access restricted" : "Staff action required"}
          </strong>
          <span>
            {isRoleRestriction
              ? message ||
                "This area is limited to authorized staff. Contact the business owner or manager if you need access."
              : "Please contact the business owner to renew the subscription and restore access. Your business records remain safe."}
          </span>
        </div>

        <button
          type="button"
          className="access-blocked-primary"
          onClick={onClose}
        >
          {isRoleRestriction ? "Return to dashboard" : "Back to My businesses"}
        </button>
      </section>
    </div>
  );
}
