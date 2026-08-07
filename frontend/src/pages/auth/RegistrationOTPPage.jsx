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
    pendingRegistration,
    resendRegistrationOtp,
    verifyRegistrationOtp,
  } = useAuth();
  const [otp, setOtp] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState(
    "Enter the six-digit code sent to your email.",
  );
  const [submitting, setSubmitting] = useState(false);
  const [resending, setResending] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState(
    RESEND_COOLDOWN_SECONDS,
  );
  const navigate = useNavigate();

  // Counts down locally before the resend action becomes available.
  useEffect(() => {
    if (secondsRemaining <= 0) return undefined;

    const timer = window.setInterval(() => {
      setSecondsRemaining((current) => Math.max(0, current - 1));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [secondsRemaining]);

  if (!pendingRegistration) {
    return <Navigate to="/register" replace />;
  }

  if (isAuthenticated) {
    return <Navigate to="/onboarding" replace />;
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
    if (secondsRemaining > 0 || resending) return;

    setError("");
    setMessage("");
    setResending(true);

    try {
      await resendRegistrationOtp(pendingRegistration.email);
      setOtp("");
      setSecondsRemaining(RESEND_COOLDOWN_SECONDS);
      setMessage("A new verification code was sent to your email.");
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
          <span>Email verification</span>
          <h1>Confirm that this email belongs to you.</h1>
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
            <span>S</span>Stock<strong>Flow</strong>
          </Link>

          <div className="auth-heading">
            <span>Verify your email</span>
            <h2>Enter your six-digit code</h2>
            <p>
              We sent the code to{" "}
              <strong>{pendingRegistration.email}</strong>.
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
                Check your inbox and spam folder for the StockFlow email.
              </small>
            </label>

            <Button
              type="submit"
              size="large"
              className="full-width-button"
              disabled={submitting || otp.length !== 6}
            >
              <MailCheck size={18} />
              {submitting ? "Verifying code..." : "Verify and create account"}
            </Button>

            <button
              type="button"
              className="registration-otp-resend"
              onClick={handleResend}
              disabled={secondsRemaining > 0 || resending}
            >
              <RefreshCw size={16} />
              {resending
                ? "Sending new code..."
                : secondsRemaining > 0
                  ? `Resend available in ${secondsRemaining}s`
                  : "Resend verification code"}
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
