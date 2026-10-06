import {
  ArrowLeft,
  KeyRound,
  MailCheck,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";

import "../../styles/login-otp.css";

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
    user,
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
  const [resendAt, setResendAt] = useState(() => pendingLogin?.resendAvailableAt || Date.now() + 60000);
  const [secondsRemaining, setSecondsRemaining] = useState(() =>
    remainingSeconds(pendingLogin?.resendAvailableAt),
  );
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const adminLogin = params.get("mode") === "admin";
  const loginPath = adminLogin ? "/login?mode=admin" : "/login?mode=business";

  useEffect(() => {
    const tick = () => setSecondsRemaining(remainingSeconds(resendAt));
    tick();
    const timer = window.setInterval(tick, 1000);
    window.addEventListener("focus", tick);
    return () => { window.clearInterval(timer); window.removeEventListener("focus", tick); };
  }, [resendAt]);

  useEffect(() => {
    if (!pendingLogin?.challengeId || !pendingLogin.emailDeliveryRequired) return undefined;
    let active = true;
    setDelivering(true);
    setMessage("Sending your security code…");
    deliverLoginOtp(pendingLogin.challengeId)
      .then((next) => {
        if (!active) return;
        setResendAt(next.resendAvailableAt);
        setMessage("Code submitted for delivery. Check your inbox and spam folder.");
      })
      .catch((err) => { if (active) { setMessage(""); setError(err.message); } })
      .finally(() => { if (active) setDelivering(false); });
    return () => { active = false; };
    // One shared request per challenge; completion must survive provider updates.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deliverLoginOtp, pendingLogin?.challengeId]);

  // A new login challenge must complete before reusing an older session.
  if (isAuthenticated && !pendingLogin) {
    return <Navigate to={adminLogin ? "/platform-admin" : "/businesses"} replace />;
  }

  if (!pendingLogin) {
    return <Navigate to={loginPath} replace />;
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
      const authenticatedUser = await verifyLoginOtp({
        challengeId: pendingLogin.challengeId,
        otp,
      });
      let nextPath;
      if (adminLogin) {
        nextPath = "/platform-admin";
      } else {
        const availableBusinesses = await loadBusinesses();
        nextPath =
          availableBusinesses.length > 0 || authenticatedUser?.isPlatformAdmin
            ? "/businesses"
            : "/onboarding";
      }
      const canOfferPasskey = Boolean(window.PublicKeyCredential && navigator.credentials);
      const alreadyPrompted = window.localStorage.getItem("stockflow_passkey_setup_prompted") === "1";
      navigate(
        canOfferPasskey && !alreadyPrompted ? "/setup-biometric" : nextPath,
        { replace: true, state: canOfferPasskey && !alreadyPrompted ? { nextPath } : undefined },
      );
    } catch (verificationError) {
      setError(verificationError.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResend() {
    if (secondsRemaining > 0 || resending || delivering || submitting) return;
    setError(""); setMessage(""); setOtp(""); setResending(true);
    setResendAt(Date.now() + 60000);
    try {
      const next = await resendLoginOtp(pendingLogin.challengeId);
      setResendAt(next.resendAvailableAt);
      setMessage("New code submitted for delivery. Use the latest code only.");
    } catch (err) { setError(err.message); }
    finally { setResending(false); }
  }

  return (
    <main className="auth-page auth-registration-otp-page auth-login-otp-page">
      <section className="auth-visual-panel">
        <Link to={loginPath} className="auth-back-link">
          <ArrowLeft size={18} /> Back to login
        </Link>

        <div className="auth-visual-content">
          <span>Two-factor authentication</span>
          <h1>Your account. One secure step away.</h1>
          <p>
            Your password has been accepted. StockFlow now requires the
            one-time code sent to your registered email address.
          </p>
          <ul className="auth-benefit-list">
            <li>The security code expires after 10 minutes</li>
            <li>Five incorrect attempts are allowed per code</li>
            <li>Your workspace opens after successful verification</li>
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
              Enter the six-digit code for 
              <strong>{pendingLogin.email}</strong>.
            </p>
          </div>

          {error ? (
            <div role="alert" className="form-alert form-alert-error">{error}</div>
          ) : null}

          {message ? (
            <div role="status" className="form-alert form-alert-success">{message}</div>
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
                  placeholder="••••••"
                  autoFocus
                  spellCheck={false}
                  aria-describedby="otp-help"
                  aria-label="Six-digit sign-in security code"
                  required
                />
              </div>
              <small id="otp-help">
                Check your inbox and spam folder for the StockFlow email.
              </small>
            </label>

            <Button
              type="submit"
              size="large"
              className="full-width-button"
              disabled={submitting || resending || delivering || otp.length !== 6}
            >
              <ShieldCheck size={18} />
              {submitting ? "Verifying sign-in..." : "Verify and log in"}
            </Button>

            <div className="sf-otp-resend-area">
              <span>Haven’t received your code?</span>
              {secondsRemaining > 0 ? (
                <p className="sf-otp-countdown">Request a new code in <strong>{String(Math.floor(secondsRemaining / 60)).padStart(2, "0")}:{String(secondsRemaining % 60).padStart(2, "0")}</strong></p>
              ) : (
                <button type="button" className="registration-otp-resend" onClick={handleResend} disabled={delivering || resending || submitting}>
                  <RefreshCw size={16} /> {resending ? "Sending new code…" : "Resend code"}
                </button>
              )}
            </div>
          </form>

          <p className="auth-switch-text">
            <MailCheck size={15} /> Your workspace stays locked until your code is verified.
          </p>
        </div>
      </section>
    </main>
  );
}
