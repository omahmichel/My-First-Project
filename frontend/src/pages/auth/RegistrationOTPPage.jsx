import {
  ArrowLeft,
  KeyRound,
  MailCheck,
  RefreshCw,
} from "lucide-react";
import {
  useEffect,
  useState,
} from "react";
import {
  Link,
  Navigate,
  useNavigate,
} from "react-router-dom";

import Button from "../../components/ui/Button";
import { useAuth } from "../../context/AuthContext";

const RESEND_COOLDOWN_SECONDS = 60;

export default function RegistrationOTPPage() {
  const {
    isAuthenticated,
    isInitializing,
    user,
    pendingRegistration,
    resendRegistrationOtp,
    verifyRegistrationOtp,
  } = useAuth();
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState(
    "Enter the six-digit code sent to your selected contact.",
  );
  const [submitting, setSubmitting] = useState(false);
  const [resending, setResending] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState(
    Math.max(0, Math.ceil(((Date.parse(pendingRegistration?.resendAvailableAt) || Date.now()) - Date.now()) / 1000)),
  );
  const navigate = useNavigate();
  const channel = pendingRegistration?.channel ?? "email";
  const [selectedChannel, setSelectedChannel] = useState(channel);

  // Counts down locally before the resend action becomes available.
  useEffect(() => {
    if (secondsRemaining <= 0) return undefined;

    const timer = window.setInterval(() => {
      setSecondsRemaining((current) => Math.max(0, current - 1));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [secondsRemaining]);

  if (isInitializing) {
    return <p role="status">Loading account…</p>;
  }

  if (isAuthenticated) {
    return (
      <Navigate
        to={user?.isPlatformAdmin ? "/platform-admin/overview" : "/onboarding"}
        replace
      />
    );
  }

  if (!pendingRegistration) {
    return <Navigate to="/register" replace />;
  }

  function handleOtpChange(event) {
    // Keeps only the first six digits from typed or pasted input.
    const nextValue = event.target.value
      .replace(/\D/g, "")
      .slice(0, 6);

    setOtp(nextValue);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setMessage("");

    if (!/^\d{6}$/.test(otp)) {
      setError("Enter the complete six-digit verification code.");
      return;
    }

    setSubmitting(true);

    try {
      await verifyRegistrationOtp({
        email: pendingRegistration.email,
        otp,
      });
      navigate("/onboarding", { replace: true });
    } catch (verificationError) {
      setError(verificationError.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResend() {
    if (secondsRemaining > 0 || resending || submitting) return;

    setError("");
    setMessage("");
    setResending(true);

    try {
      const delivery = await resendRegistrationOtp(pendingRegistration.email, selectedChannel);
      setOtp("");
      setSecondsRemaining(RESEND_COOLDOWN_SECONDS);
      setMessage(delivery.message);
    } catch (resendError) {
      setError(resendError.message);
    } finally {
      setResending(false);
    }
  }

  return (
    <main className="auth-page auth-registration-otp-page">
      <section className="auth-visual-panel">
        <Link to="/register" className="auth-back-link">
          <ArrowLeft size={18} /> Change registration details
        </Link>

        <div className="auth-visual-content">
          <span>Contact verification</span>
          <h1>Verify your contact. Keep your account secure.</h1>
          <p>
            StockFlow creates your account only after the verification code is
            accepted.
          </p>
          <ul className="auth-benefit-list">
            <li>The code expires after 10 minutes</li>
            <li>Five incorrect attempts are allowed per code</li>
            <li>Your password is never stored in the browser</li>
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
            <span>Verify your {channel === "sms" ? "phone number" : "email"}</span>
            <h2>Enter your six-digit code</h2>
            <p>
              We sent the code to{" "}
              <strong>{pendingRegistration.destination || pendingRegistration.email}</strong>.
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
              Verification code
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
                  aria-label="Six-digit verification code"
                  required
                />
              </div>
              <small>
                {channel === "sms" ? "Check your phone for the StockFlow SMS." : "Check your inbox and spam folder for the StockFlow email."}
              </small>
            </label>

            <Button
              type="submit"
              size="large"
              className="full-width-button"
              disabled={submitting || resending || otp.length !== 6}
            >
              <MailCheck size={18} />
              {submitting ? "Verifying code..." : "Verify and create account"}
            </Button>

            <label>
              Code not arriving? Choose a delivery method
              <select value={selectedChannel} onChange={(event) => setSelectedChannel(event.target.value)} disabled={submitting || resending}>
                <option value="email">Email</option>
                <option value="sms" disabled={!pendingRegistration.phone || !pendingRegistration.challengeId}>SMS</option>
              </select>
              <small>A new code replaces the previous code. Your registration details are kept.</small>
            </label>
            <button
              type="button"
              className="registration-otp-resend"
              onClick={handleResend}
              disabled={secondsRemaining > 0 || resending || submitting}
            >
              <RefreshCw size={16} />
              {resending
                ? "Sending new code..."
                : secondsRemaining > 0
                  ? `Resend available in ${secondsRemaining}s`
                  : selectedChannel !== channel ? `Send code by ${selectedChannel === "sms" ? "SMS" : "email"}` : "Resend verification code"}
            </button>
          </form>

          <p className="auth-switch-text">
            Already verified? <Link to="/login">Log in</Link>
          </p>
        </div>
      </section>
    </main>
  );
}
