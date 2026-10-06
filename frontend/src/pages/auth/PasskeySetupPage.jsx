import { Fingerprint, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import Button from "../../components/ui/Button";
import { useAuth } from "../../context/AuthContext";
import { passkeysSupported } from "../../services/passkeys";

export default function PasskeySetupPage() {
  const { isAuthenticated, isInitializing, registerPasskey, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const nextPath = location.state?.nextPath || (user?.isPlatformAdmin ? "/platform-admin" : "/businesses");
  const supported = passkeysSupported();

  if (isInitializing) return <p role="status">Loading account…</p>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  function continueToStockFlow() {
    window.localStorage.setItem("stockflow_passkey_setup_prompted", "1");
    navigate(nextPath, { replace: true });
  }

  async function handleSetup() {
    setWorking(true);
    setError("");
    setMessage("");
    try {
      await registerPasskey("My biometric device");
      window.localStorage.setItem("stockflow_passkey_setup_prompted", "1");
      setMessage("Biometric/passkey sign-in is ready on this device.");
    } catch (setupError) {
      setError(setupError.message);
    } finally {
      setWorking(false);
    }
  }

  return (
    <main className="auth-page auth-passkey-setup-page">
      <section className="auth-visual-panel">
        <div className="auth-visual-content">
          <span>Faster secure sign-in</span>
          <h1>Use your device security next time.</h1>
          <p>
            StockFlow can use your fingerprint, Face ID, Windows Hello or device PIN through a passkey.
            Your biometric data stays on your device and is never sent to StockFlow.
          </p>
          <ul className="auth-benefit-list">
            <li>No fingerprint or face data is stored by StockFlow</li>
            <li>Password and email OTP remain available for recovery</li>
            <li>Each passkey is cryptographically bound to StockFlow</li>
          </ul>
        </div>
      </section>

      <section className="auth-form-panel">
        <div className="auth-form-card">
          <div className="auth-brand">
            <span>S</span><span className="auth-brand-word">Stock<strong>Flow</strong></span>
          </div>
          <div className="auth-heading">
            <span>Biometric sign-in</span>
            <h2>Secure this device</h2>
            <p>Optional. You can continue using password + OTP whenever you need to.</p>
          </div>

          {error ? <div role="alert" className="form-alert form-alert-error">{error}</div> : null}
          {message ? <div role="status" className="form-alert form-alert-success">{message}</div> : null}

          <div className="auth-passkey-setup-actions">
            {supported && !message ? (
              <Button type="button" size="large" className="full-width-button" onClick={handleSetup} disabled={working}>
                <Fingerprint size={19} /> {working ? "Opening device security…" : "Enable biometric sign-in"}
              </Button>
            ) : null}
            {!supported ? (
              <div className="form-alert">This browser cannot create a passkey here. Continue and use password + OTP.</div>
            ) : null}
            <button type="button" className="app-button app-button-secondary app-button-large full-width-button" onClick={continueToStockFlow}>
              <ShieldCheck size={18} /> {message ? "Continue to StockFlow" : "Not now"}
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}
