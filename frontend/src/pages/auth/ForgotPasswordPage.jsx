import {
  ArrowLeft,
  CheckCircle2,
  Mail,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";
import {
  Link,
  useLocation,
} from "react-router-dom";

import Button from "../../components/ui/Button";
import { apiRequest } from "../../services/api";

export default function ForgotPasswordPage() {
  const location = useLocation();
  const [email, setEmail] = useState(
    location.state?.email?.trim().toLowerCase() ?? "",
  );
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();

    if (submitting) return;

    setError("");
    setMessage("");
    setSubmitting(true);

    try {
      const response = await apiRequest(
        "/auth/password-reset/request/",
        {
          method: "POST",
          body: JSON.stringify({
            email: email.trim().toLowerCase(),
          }),
          skipAuthRefresh: true,
        },
      );

      setMessage(response.message);
    } catch (requestError) {
      setError(
        requestError.message ||
          "StockFlow could not process the reset request.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-visual-panel">
        <Link to="/" className="auth-back-link">
          <ArrowLeft size={18} /> Back to website
        </Link>

        <div className="auth-visual-content">
          <span>Account recovery</span>
          <h1>Recover access without exposing your account.</h1>
          <p>
            StockFlow sends the same response whether an email exists or not,
            helping protect every account from unwanted discovery.
          </p>

          <div className="auth-testimonial">
            <strong>Secure reset link</strong>
            <p>
              The link expires after one hour and becomes unusable once the
              password is changed.
            </p>
          </div>
        </div>
      </section>

      <section className="auth-form-panel">
        <div className="auth-form-card">
          <Link to="/" className="auth-brand">
            <span>S</span>Stock<strong>Flow</strong>
          </Link>

          <div className="auth-heading">
            <span>Forgot password</span>
            <h2>Request a reset link</h2>
            <p>
              Enter the email address registered for your StockFlow account.
            </p>
          </div>

          {error ? (
            <div className="form-alert form-alert-error" role="alert">
              {error}
            </div>
          ) : null}

          {message ? (
            <div
              className="form-alert form-alert-success password-reset-message"
              role="status"
            >
              <CheckCircle2 size={19} />
              <span>{message}</span>
            </div>
          ) : null}

          {!message ? (
            <form onSubmit={handleSubmit} className="auth-form">
              <label>
                Email address
                <div className="input-with-icon">
                  <Mail size={18} />
                  <input
                    name="email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    autoComplete="email"
                    required
                  />
                </div>
              </label>

              <div className="password-reset-security-note">
                <ShieldCheck size={18} />
                <span>
                  For security, StockFlow never confirms whether an email
                  belongs to an account.
                </span>
              </div>

              <Button
                type="submit"
                size="large"
                className="full-width-button"
                disabled={submitting}
              >
                {submitting ? "Sending reset link..." : "Send reset link"}
              </Button>
            </form>
          ) : (
            <Button
              type="button"
              size="large"
              className="full-width-button"
              onClick={() => setMessage("")}
            >
              Send another request
            </Button>
          )}

          <p className="auth-switch-text">
            Remembered your password? <Link to="/login">Return to login</Link>
          </p>
        </div>
      </section>
    </main>
  );
}
