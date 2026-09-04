import {
  ArrowLeft,
  KeyRound,
  MailCheck,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import Button from "../../components/ui/Button";
import { useAuth } from "../../context/AuthContext";
import { useStore } from "../../context/StoreContext";

function remainingSeconds(timestamp) {
  if (!timestamp) return 0;
  return Math.max(0, Math.ceil((Number(timestamp) - Date.now()) / 1000));
}

export default function LoginOTPPage() {
  const {
    isAuthenticated,
    pendingLogin,
    deliverLoginOtp,
    resendLoginOtp,
    verifyLoginOtp,
  } = useAuth();
  const { loadBusinesses } = useStore();
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState(
    pendingLogin?.emailDeliveryRequired
      ? "Sending your security code..."
      : "Enter the six-digit security code sent to your email.",
  );
  const [submitting, setSubmitting] = useState(false);
  const [delivering, setDelivering] = useState(
    Boolean(pendingLogin?.emailDeliveryRequired),
  );
  const [resending, setResending] = useState(false);
  const deliveryStartedRef = useRef(false);
  const [secondsRemaining, setSecondsRemaining] = useState(() =>
    remainingSeconds(pendingLogin?.resendAvailableAt),
  );
  const navigate = useNavigate();

  useEffect(() => {
    if (secondsRemaining <= 0) return undefined;

    const timer = window.setInterval(() => {
      setSecondsRemaining((current) => Math.max(0, current - 1));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [secondsRemaining]);

  useEffect(() => {
    if (
      !pendingLogin?.challengeId ||
      !pendingLogin?.emailDeliveryRequired ||
      deliveryStartedRef.current
    ) {
      return undefined;
    }

    deliveryStartedRef.current = true;
    let active = true;
    setDelivering(true);
    setError("");
    setMessage("Sending your security code...");

    deliverLoginOtp(pendingLogin.challengeId)
      .then((nextPendingLogin) => {
        if (!active) return;
        setSecondsRemaining(
          remainingSeconds(nextPendingLogin.resendAvailableAt),
        );
        setMessage("Security code sent. Check your email.");
      })
      .catch((deliveryError) => {
        deliveryStartedRef.current = false;
        if (!active) return;
        setMessage("");
        setError(deliveryError.message);
      })
      .finally(() => {
        if (active) setDelivering(false);
      });

    return () => {
      active = false;
    };
  }, [
    deliverLoginOtp,
    pendingLogin?.challengeId,
    pendingLogin?.emailDeliveryRequired,
  ]);

  if (isAuthenticated) {
    return <Navigate to="/businesses" replace />;
  }

  if (!pendingLogin) {
    return <Navigate to="/login" replace />;
  }

  function handleOtpChange(event) {
    setOtp(event.target.value.replace(/\D/g, "").slice(0, 6));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setMessage("");

    if (!/^\d{6}$/.test(otp)) {
      setError("Enter the complete six-digit security code.");
      return;
    }

    setSubmitting(true);

    try {
      await verifyLoginOtp({
        challengeId: pendingLogin.challengeId,
        otp,
      });
      const availableBusinesses = await loadBusinesses();
      navigate(
        availableBusinesses.length > 0 ? "/businesses" : "/onboarding",
        { replace: true },
      );
    } catch (verificationError) {
      setError(verificationError.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResend() {
    const needsInitialDelivery = Boolean(
      pendingLogin?.emailDeliveryRequired,
    );

    if (
      (!needsInitialDelivery && secondsRemaining > 0) ||
      resending ||
      delivering
    ) {
      return;
    }

    setError("");
    setMessage("");
    setResending(true);

    try {
      const nextPendingLogin = needsInitialDelivery
        ? await deliverLoginOtp(pendingLogin.challengeId)
        : await resendLoginOtp(pendingLogin.challengeId);
      setOtp("");
      setSecondsRemaining(
        remainingSeconds(nextPendingLogin.resendAvailableAt),
      );
      setMessage(
        needsInitialDelivery
          ? "Security code sent. Check your email."
          : "A new security code was sent to your email.",
      );
    } catch (resendError) {
      setError(resendError.message);
    } finally {
      setResending(false);
    }
  }

  return (
    <main className="auth-page auth-registration-otp-page auth-login-otp-page">
      <section className="auth-visual-panel">
        <Link to="/login" className="auth-back-link">
          <ArrowLeft size={18} /> Back to login
        </Link>

        <div className="auth-visual-content">
          <span>Two-factor authentication</span>
          <h1>One more security check before your workspace opens.</h1>
          <p>
            Your password has been accepted. StockFlow now requires the
            one-time code sent to your registered email address.
          </p>
          <ul className="auth-benefit-list">
            <li>The security code expires after 10 minutes</li>
            <li>Five incorrect attempts are allowed per code</li>
            <li>JWT access is issued only after this check succeeds</li>
          </ul>
        </div>
      </section>

      <section className="auth-form-panel">
        <div className="auth-form-card">
          <Link to="/" className="auth-brand">
            <span>S</span>
            <span className="auth-brand-word">
              Stock<strong>Flow</strong>
            </span>
          </Link>

          <div className="auth-heading">
            <span>Secure sign-in</span>
            <h2>Verify your sign-in</h2>
            <p>
              {pendingLogin.emailDeliveryRequired
                ? "We are sending a security code to "
                : "We sent a security code to "}
              <strong>{pendingLogin.email}</strong>.
            </p>
          </div>

          {error ? (
            <div className="form-alert form-alert-error">{error}</div>
          ) : null}

          {message ? (
            <div className="form-alert form-alert-success">{message}</div>
          ) : null}

          <form onSubmit={handleSubmit} className="auth-form">
            <label>
              Security code
              <div className="input-with-icon registration-otp-input">
                <KeyRound size={18} />
                <input
                  name="otp"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={otp}
                  onChange={handleOtpChange}
                  maxLength={6}
                  placeholder="000000"
                  aria-label="Six-digit sign-in security code"
                  required
                />
              </div>
              <small>
                Check your inbox and spam folder for the StockFlow email.
              </small>
            </label>

            <Button
              type="submit"
              size="large"
              className="full-width-button"
              disabled={submitting || otp.length !== 6}
            >
              <ShieldCheck size={18} />
              {submitting ? "Verifying sign-in..." : "Verify and log in"}
            </Button>

            <button
              type="button"
              className="registration-otp-resend"
              onClick={handleResend}
              disabled={delivering || secondsRemaining > 0 || resending}
            >
              <RefreshCw size={16} />
              {delivering
                ? "Sending security code..."
                : resending
                  ? "Sending new code..."
                  : secondsRemaining > 0
                  ? `Resend available in ${secondsRemaining}s`
                  : "Resend security code"}
            </button>
          </form>

          <p className="auth-switch-text">
            <MailCheck size={15} /> Password accepted. Waiting for your second
            factor.
          </p>
        </div>
      </section>
    </main>
  );
}
