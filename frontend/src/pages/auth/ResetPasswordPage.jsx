import {
  ArrowLeft,
  CheckCircle2,
  Eye,
  EyeOff,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";
import {
  Link,
  useSearchParams,
} from "react-router-dom";

import Button from "../../components/ui/Button";
import { apiRequest } from "../../services/api";

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const uid = searchParams.get("uid") ?? "";
  const token = searchParams.get("token") ?? "";
  const hasResetLink = Boolean(uid && token);

  const [form, setForm] = useState({
    password: "",
    passwordConfirm: "",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showPasswordConfirm, setShowPasswordConfirm] =
    useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function handleChange(event) {
    setForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();

    if (submitting) return;

    setError("");
    setMessage("");

    if (!hasResetLink) {
      setError(
        "This password reset link is incomplete. Request a new link.",
      );
      return;
    }

    if (form.password.length < 8) {
      setError("Password must contain at least 8 characters.");
      return;
    }

    if (form.password !== form.passwordConfirm) {
      setError("The passwords do not match.");
      return;
    }

    setSubmitting(true);

    try {
      const response = await apiRequest(
        "/auth/password-reset/confirm/",
        {
          method: "POST",
          body: JSON.stringify({
            uid,
            token,
            password: form.password,
            password_confirm: form.passwordConfirm,
          }),
          skipAuthRefresh: true,
        },
      );

      window.localStorage.removeItem("stockflow_access_token");
      window.localStorage.removeItem("stockflow_refresh_token");
      setMessage(response.message);
      setForm({
        password: "",
        passwordConfirm: "",
      });
    } catch (resetError) {
      setError(
        resetError.message ||
          "StockFlow could not reset the password.",
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
          <span>Secure password change</span>
          <h1>Create a new password for your StockFlow account.</h1>
          <p>
            After the reset succeeds, existing login sessions are invalidated
            and the new password remains valid until it is changed again.
          </p>

          <div className="auth-testimonial">
            <strong>Protected account recovery</strong>
            <p>
              The signed reset link is time-limited and cannot be reused after
              your password changes.
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
            <span>Reset password</span>
            <h2>Choose a new password</h2>
            <p>
              Use at least eight characters and keep the password private.
            </p>
          </div>

          {!hasResetLink && !message ? (
            <div className="form-alert form-alert-error" role="alert">
              This password reset link is incomplete. Request a new link.
            </div>
          ) : null}

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
                New password
                <div className="input-with-icon input-with-action">
                  <LockKeyhole size={18} />
                  <input
                    name="password"
                    type={showPassword ? "text" : "password"}
                    value={form.password}
                    onChange={handleChange}
                    autoComplete="new-password"
                    minLength={8}
                    required
                    disabled={!hasResetLink}
                  />
                  <button
                    type="button"
                    onClick={() =>
                      setShowPassword((value) => !value)
                    }
                    aria-label="Toggle new password visibility"
                    disabled={!hasResetLink}
                  >
                    {showPassword ? (
                      <EyeOff size={18} />
                    ) : (
                      <Eye size={18} />
                    )}
                  </button>
                </div>
              </label>

              <label>
                Confirm new password
                <div className="input-with-icon input-with-action">
                  <LockKeyhole size={18} />
                  <input
                    name="passwordConfirm"
                    type={
                      showPasswordConfirm ? "text" : "password"
                    }
                    value={form.passwordConfirm}
                    onChange={handleChange}
                    autoComplete="new-password"
                    minLength={8}
                    required
                    disabled={!hasResetLink}
                  />
                  <button
                    type="button"
                    onClick={() =>
                      setShowPasswordConfirm((value) => !value)
                    }
                    aria-label="Toggle password confirmation visibility"
                    disabled={!hasResetLink}
                  >
                    {showPasswordConfirm ? (
                      <EyeOff size={18} />
                    ) : (
                      <Eye size={18} />
                    )}
                  </button>
                </div>
              </label>

              <div className="password-reset-security-note">
                <ShieldCheck size={18} />
                <span>
                  A successful reset signs out existing sessions for this
                  account.
                </span>
              </div>

              <Button
                type="submit"
                size="large"
                className="full-width-button"
                disabled={submitting || !hasResetLink}
              >
                {submitting ? "Resetting password..." : "Reset password"}
              </Button>
            </form>
          ) : (
            <Link
              to="/login"
              className="password-reset-login-link"
            >
              Continue to login
            </Link>
          )}

          <p className="auth-switch-text">
            Need a new link?{" "}
            <Link to="/forgot-password">Request another reset</Link>
          </p>
        </div>
      </section>
    </main>
  );
}
