import {
  CalendarDays,
  CheckCircle2,
  Clock3,
  CreditCard,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react";

import { useStore } from "../../context/StoreContext";

function formatAccessDate(value) {
  if (!value) return "Not available";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "Not available";

  return new Intl.DateTimeFormat("en-GH", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

function resolveSubscriptionState(business) {
  if (business.hasActiveSubscription) {
    return {
      label: "Subscription active",
      description:
        "Your paid StockFlow subscription is active and this workspace has full access.",
      icon: CheckCircle2,
      tone: "success",
      endLabel: "Subscription ends",
      endDate: business.subscriptionEndsAt,
    };
  }

  if (business.isTrialActive) {
    return {
      label: "Free trial active",
      description:
        "Your 60-day StockFlow free trial is active. Subscribe before it ends to avoid interruption.",
      icon: Clock3,
      tone: business.subscriptionReminderDue ? "warning" : "success",
      endLabel: "Trial ends",
      endDate: business.trialEndsAt,
    };
  }

  return {
    label: "Access expired",
    description:
      "The free trial or paid subscription for this workspace has expired. Business records remain safe, but operational features are blocked.",
    icon: LockKeyhole,
    tone: "danger",
    endLabel: "Access ended",
    endDate: business.subscriptionEndsAt ?? business.trialEndsAt,
  };
}

export default function SubscriptionPage() {
  const { business } = useStore();
  const state = resolveSubscriptionState(business);
  const StatusIcon = state.icon;
  const isOwner = business.currentUserRole === "owner";

  return (
    <section className="subscription-page">
      <div className="subscription-page-heading">
        <span>Workspace access</span>
        <h1>Subscription</h1>
        <p>
          Review the trial and subscription status for{" "}
          <strong>{business.name || "this business"}</strong>.
        </p>
      </div>

      <div className="subscription-status-grid">
        <article
          className={`subscription-status-card subscription-status-${state.tone}`}
        >
          <div className="subscription-status-icon">
            <StatusIcon size={26} />
          </div>

          <div>
            <span>Current status</span>
            <h2>{state.label}</h2>
            <p>{state.description}</p>
          </div>
        </article>

        <article className="subscription-detail-card">
          <div>
            <CalendarDays size={20} />
            <span>{state.endLabel}</span>
          </div>
          <strong>{formatAccessDate(state.endDate)}</strong>
        </article>

        <article className="subscription-detail-card">
          <div>
            <Clock3 size={20} />
            <span>Trial days remaining</span>
          </div>
          <strong>
            {business.isTrialActive
              ? Math.max(0, business.trialDaysRemaining)
              : 0}
          </strong>
        </article>

        <article className="subscription-detail-card">
          <div>
            <ShieldCheck size={20} />
            <span>System access</span>
          </div>
          <strong>
            {business.hasSystemAccess ? "Available" : "Blocked"}
          </strong>
        </article>
      </div>

      <article className="subscription-action-card">
        <div className="subscription-action-icon">
          <CreditCard size={25} />
        </div>

        <div>
          <span>
            {isOwner ? "Subscription renewal" : "Owner action required"}
          </span>
          <h2>
            {isOwner
              ? "Secure online subscription payment is the next setup step."
              : "Contact the business owner to renew this workspace."}
          </h2>
          <p>
            {isOwner
              ? "The payment gateway will be connected next. Until then, StockFlow will not claim or record an online subscription payment."
              : "Only the business owner can activate or renew the StockFlow subscription. Your account and business records remain safe until access is restored."}
          </p>
        </div>
      </article>
    </section>
  );
}
