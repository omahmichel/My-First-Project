import { ArrowLeft, Eye, EyeOff, LockKeyhole, Mail } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import Button from "../../components/ui/Button";
import { useAuth } from "../../context/AuthContext";

export default function LoginPage() {
  const [form, setForm] = useState({ email: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  function handleChange(event) {
    setForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      await login(form);
      navigate("/verify-login", { replace: true });
    } catch (loginError) {
      setError(loginError.message);
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
          <span>Welcome back</span>
          <h1>Your business records are ready when you are.</h1>
          <p>
            Continue managing stock, sales, invoices, customer credit and
            staff activity.
          </p>
          <div className="auth-testimonial">
            <strong>Secure account access</strong>
            <p>
              Sign in with the email address and password registered for your
              StockFlow account.
            </p>
          </div>
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
            <span>Secure account access</span>
            <h2>Log in to StockFlow</h2>
            <p>Enter your details to continue to your business workspace.</p>
          </div>

          {error ? <div className="form-alert form-alert-error">{error}</div> : null}

          <form onSubmit={handleSubmit} className="auth-form">
            <label>
              Email address
              <div className="input-with-icon">
                <Mail size={18} />
                <input
                  name="email"
                  type="email"
                  value={form.email}
                  onChange={handleChange}
                  autoComplete="email"
                  required
                />
              </div>
            </label>

            <label>
              Password
              <div className="input-with-icon input-with-action">
                <LockKeyhole size={18} />
                <input
                  name="password"
                  type={showPassword ? "text" : "password"}
                  value={form.password}
                  onChange={handleChange}
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label="Toggle password visibility"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </label>

            <div className="auth-options-row">
              <label className="checkbox-label">
                <input type="checkbox" defaultChecked /> Remember me
              </label>
              <Link
                to="/forgot-password"
                state={{ email: form.email }}
                className="text-button"
              >
                Forgot password?
              </Link>
            </div>

            <Button
              type="submit"
              size="large"
              className="full-width-button"
              disabled={submitting}
            >
              {submitting ? "Logging in..." : "Log in"}
            </Button>
          </form>

          <p className="auth-switch-text">
            New to StockFlow? <Link to="/register">Create an account</Link>
          </p>
        </div>
      </section>
    </main>
  );
}
