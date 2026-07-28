import { ArrowLeft, Building2, Eye, EyeOff, LockKeyhole, Mail, User } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import Button from "../../components/ui/Button";
import { useAuth } from "../../context/AuthContext";

export default function RegisterPage() {
  const [form, setForm] = useState({ name: "", businessName: "", email: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const { register } = useAuth();
  const navigate = useNavigate();

  function handleChange(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    setError("");
    try {
      register(form);
      navigate("/onboarding");
    } catch (registrationError) {
      setError(registrationError.message);
    }
  }

  return (
    <main className="auth-page auth-page-register">
      <section className="auth-visual-panel auth-register-visual">
        <Link to="/" className="auth-back-link"><ArrowLeft size={18} /> Back to website</Link>
        <div className="auth-visual-content">
          <span>Start organised</span>
          <h1>Build a reliable record of every product and sale.</h1>
          <p>Create your account, choose your shop type and prepare the workspace for your daily operations.</p>
          <ul className="auth-benefit-list">
            <li>Building materials and tile inventory</li>
            <li>Boutique size and colour variants</li>
            <li>Invoices, receipts and customer credit</li>
          </ul>
        </div>
      </section>

      <section className="auth-form-panel">
        <div className="auth-form-card auth-form-card-wide">
          <Link to="/" className="auth-brand"><span>S</span>Stock<strong>Flow</strong></Link>
          <div className="auth-heading">
            <span>14-day planned trial</span>
            <h2>Create your business account</h2>
            <p>You will configure the business type and invoice information in the next step.</p>
          </div>

          {error ? <div className="form-alert form-alert-error">{error}</div> : null}

          <form onSubmit={handleSubmit} className="auth-form">
            <div className="form-two-column">
              <label>
                Your full name
                <div className="input-with-icon"><User size={18} /><input name="name" value={form.name} onChange={handleChange} required /></div>
              </label>
              <label>
                Business name
                <div className="input-with-icon"><Building2 size={18} /><input name="businessName" value={form.businessName} onChange={handleChange} required /></div>
              </label>
            </div>

            <label>
              Email address
              <div className="input-with-icon"><Mail size={18} /><input name="email" type="email" value={form.email} onChange={handleChange} required /></div>
            </label>

            <label>
              Password
              <div className="input-with-icon input-with-action">
                <LockKeyhole size={18} />
                <input name="password" type={showPassword ? "text" : "password"} value={form.password} onChange={handleChange} required />
                <button type="button" onClick={() => setShowPassword((value) => !value)}>{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</button>
              </div>
              <small>Use at least 8 characters.</small>
            </label>

            <label className="checkbox-label terms-checkbox">
              <input type="checkbox" required />
              I agree to the planned terms of service and privacy policy.
            </label>

            <Button type="submit" size="large" className="full-width-button">Continue to business setup</Button>
          </form>

          <p className="auth-switch-text">Already have an account? <Link to="/login">Log in</Link></p>
        </div>
      </section>
    </main>
  );
}
