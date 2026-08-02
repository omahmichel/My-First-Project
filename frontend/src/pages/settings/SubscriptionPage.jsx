import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  Clock3,
  CreditCard,
  LoaderCircle,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react";

import { useStore } from "../../context/StoreContext";
import { apiRequest } from "../../services/api";

const PENDING_PAYMENT_STORAGE_KEY =
  "stockflow_pending_subscription_payment";
const SUBSCRIPTION_PRICE_LABEL = "\u20B599";
const SUBSCRIPTION_DURATION_DAYS = 40;

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

function loadPendingPayment() {
  // Restores the business and reference after returning from Paystack.
  try {
    const storedValue = window.sessionStorage.getItem(
      PENDING_PAYMENT_STORAGE_KEY,
    );

    if (!storedValue) return null;

    const parsedValue = JSON.parse(storedValue);

    if (!parsedValue?.businessId || !parsedValue?.reference) {
      return null;
    }

    return {
      businessId: String(parsedValue.businessId),
      reference: String(parsedValue.reference),
    };
  } catch {
    return null;
  }
}

function savePendingPayment(payment) {
  // Keeps only the non-secret identifiers required for verification.
  window.sessionStorage.setItem(
    PENDING_PAYMENT_STORAGE_KEY,
    JSON.stringify(payment),
  );
}

function clearPendingPayment() {
  window.sessionStorage.removeItem(PENDING_PAYMENT_STORAGE_KEY);
}

export default function SubscriptionPage() {
  const { business, loadBusinesses } = useStore();
  const [searchParams, setSearchParams] = useSearchParams();
  const [pendingPayment, setPendingPayment] = useState(
    loadPendingPayment,
  );
  const [initializing, setInitializing] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [paymentNotice, setPaymentNotice] = useState(null);
  const autoVerificationReference = useRef("");

  const state = resolveSubscriptionState(business);
  const StatusIcon = state.icon;
  const isOwner = business.currentUserRole === "owner";
  const callbackReference =
    searchParams.get("reference") ??
    searchParams.get("trxref") ??
    "";

  const matchingPendingPayment =
    pendingPayment &&
    (
      !callbackReference ||
      pendingPayment.reference === callbackReference
    )
      ? pendingPayment
      : null;

  const paymentReference =
    callbackReference ||
    matchingPendingPayment?.reference ||
    "";
  const paymentBusinessId =
    matchingPendingPayment?.businessId ||
    business.id;

  const clearCallbackParameters = useCallback(() => {
    // Removes payment references from the address bar after fulfillment.
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("reference");
    nextParams.delete("trxref");
    setSearchParams(nextParams, { replace: true });
  }, [searchParams, setSearchParams]);

  const verifyPayment = useCallback(
    async (reference, businessId) => {
      if (!reference || !businessId) return;

      setVerifying(true);
      setPaymentNotice({
        tone: "info",
        title: "Verifying payment",
        message:
          "StockFlow is confirming the transaction directly with Paystack.",
        canRetry: false,
      });

      try {
        const response = await apiRequest(
          (
            `/businesses/${businessId}/subscription/payments/` +
            `${encodeURIComponent(reference)}/verify/`
          ),
          {
            method: "POST",
            body: JSON.stringify({}),
          },
        );

        await loadBusinesses(businessId);
        clearPendingPayment();
        setPendingPayment(null);
        clearCallbackParameters();

        setPaymentNotice({
          tone: "success",
          title: "Payment verified",
          message: response.activated
            ? (
                `Your ${SUBSCRIPTION_PRICE_LABEL} payment was verified. ` +
                `${SUBSCRIPTION_DURATION_DAYS} days of StockFlow access ` +
                "have been added."
              )
            : (
                "This payment was already verified. Your current " +
                "subscription access remains active."
              ),
          canRetry: false,
        });
      } catch (error) {
        const errorCode = error.data?.code;

        setPaymentNotice({
          tone: "error",
          title:
            errorCode === "subscription_payment_not_successful"
              ? "Payment is not complete yet"
              : "Payment verification could not finish",
          message:
            errorCode === "subscription_payment_not_successful"
              ? (
                  "Complete the OTP, PIN, or Mobile Money approval in " +
                  "Paystack, then verify the payment again."
                )
              : (
                  error.message ||
                  "StockFlow could not confirm the payment right now."
                ),
          canRetry: true,
        });
      } finally {
        setVerifying(false);
      }
    },
    [clearCallbackParameters, loadBusinesses],
  );

  useEffect(() => {
    // Automatically verifies the reference returned by Paystack once.
    if (
      !callbackReference ||
      !paymentBusinessId ||
      autoVerificationReference.current === callbackReference
    ) {
      return;
    }

    autoVerificationReference.current = callbackReference;
    verifyPayment(callbackReference, paymentBusinessId);
  }, [
    callbackReference,
    paymentBusinessId,
    verifyPayment,
  ]);

  async function handleStartPayment() {
    if (!business.id || !isOwner) return;

    setInitializing(true);
    setPaymentNotice(null);

    try {
      const response = await apiRequest(
        (
          `/businesses/${business.id}/subscription/` +
          "payments/initialize/"
        ),
        {
          method: "POST",
          body: JSON.stringify({}),
        },
      );

      if (!response.authorizationUrl || !response.reference) {
        throw new Error(
          "StockFlow did not receive a valid Paystack checkout link.",
        );
      }

      const nextPendingPayment = {
        businessId: business.id,
        reference: response.reference,
      };

      savePendingPayment(nextPendingPayment);
      setPendingPayment(nextPendingPayment);

      // Paystack securely handles OTP, PIN, card and Mobile Money approval.
      window.location.assign(response.authorizationUrl);
    } catch (error) {
      setPaymentNotice({
        tone: "error",
        title: "Payment could not start",
        message:
          error.message ||
          "StockFlow could not open Paystack checkout.",
        canRetry: false,
      });
      setInitializing(false);
    }
  }

  const paymentButtonLabel = business.hasActiveSubscription
    ? `Renew for ${SUBSCRIPTION_PRICE_LABEL}`
    : business.hasSystemAccess
      ? `Subscribe for ${SUBSCRIPTION_PRICE_LABEL}`
      : `Pay ${SUBSCRIPTION_PRICE_LABEL} to restore access`;

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
          className={
            `subscription-status-card ` +
            `subscription-status-${state.tone}`
          }
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

      {paymentNotice && (
        <article
          className={
            "subscription-payment-message " +
            `subscription-payment-message-${paymentNotice.tone}`
          }
          role={paymentNotice.tone === "error" ? "alert" : "status"}
        >
          <div>
            <strong>{paymentNotice.title}</strong>
            <p>{paymentNotice.message}</p>
          </div>

          {paymentNotice.canRetry && paymentReference && (
            <button
              type="button"
              onClick={() =>
                verifyPayment(
                  paymentReference,
                  paymentBusinessId,
                )
              }
              disabled={verifying}
            >
              {verifying ? "Verifying..." : "Verify payment again"}
            </button>
          )}
        </article>
      )}

      <article className="subscription-action-card">
        <div className="subscription-action-icon">
          <CreditCard size={25} />
        </div>

        <div className="subscription-action-content">
          <span>
            {isOwner
              ? "StockFlow subscription"
              : "Owner action required"}
          </span>

          <h2>
            {isOwner
              ? `${SUBSCRIPTION_PRICE_LABEL} gives you 40 days of access.`
              : "Contact the business owner to renew this workspace."}
          </h2>

          <p>
            {isOwner
              ? (
                  "Pay securely through Paystack. Your OTP, card PIN, " +
                  "or Mobile Money approval is handled by Paystack, " +
                  "your bank, or your network—not by StockFlow."
                )
              : (
                  "Only the business owner can activate or renew the " +
                  "StockFlow subscription. Your account and business " +
                  "records remain safe until access is restored."
                )}
          </p>

          {isOwner && (
            <>
              <div className="subscription-payment-plan">
                <div>
                  <span>One payment</span>
                  <strong>{SUBSCRIPTION_PRICE_LABEL}</strong>
                </div>

                <div>
                  <span>Access period</span>
                  <strong>{SUBSCRIPTION_DURATION_DAYS} days</strong>
                </div>

                <div>
                  <span>Payment security</span>
                  <strong>Paystack verified</strong>
                </div>
              </div>

              <div className="subscription-payment-actions">
                <button
                  type="button"
                  className="subscription-pay-button"
                  onClick={handleStartPayment}
                  disabled={
                    initializing ||
                    verifying ||
                    !business.id
                  }
                >
                  {initializing ? (
                    <>
                      <LoaderCircle
                        className="subscription-spinner"
                        size={18}
                      />
                      Opening Paystack...
                    </>
                  ) : (
                    <>
                      {paymentButtonLabel}
                      <ArrowRight size={18} />
                    </>
                  )}
                </button>

                <p className="subscription-security-note">
                  StockFlow activates access only after the backend
                  verifies the exact payment with Paystack.
                </p>
              </div>
            </>
          )}
        </div>
      </article>
    </section>
  );
}
