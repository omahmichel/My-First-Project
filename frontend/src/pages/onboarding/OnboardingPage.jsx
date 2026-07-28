import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  Layers3,
  MapPin,
  Shirt,
} from "lucide-react";
import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import Button from "../../components/ui/Button";
import { useAuth } from "../../context/AuthContext";
import { useStore } from "../../context/StoreContext";
import { apiRequest } from "../../services/api";

export default function OnboardingPage() {
  const { user, pendingRegistration, completeOnboarding } = useAuth();
  const { loadBusinesses } = useStore();
  const [step, setStep] = useState(1);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    type: "building_materials",
    name: pendingRegistration?.businessName ?? "",
    ownerName: pendingRegistration?.name ?? user?.name ?? "",
    email: pendingRegistration?.email ?? user?.email ?? "",
    phone: "",
    location: "",
    digitalAddress: "",
    invoicePrefix: "INV",
    receiptPrefix: "RCT",
  });
  const navigate = useNavigate();

  if (!pendingRegistration && !user) {
    return <Navigate to="/register" replace />;
  }

  function handleChange(event) {
    setForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  async function finishSetup() {
    if (!form.name.trim()) {
      setError("Enter the business name before finishing setup.");
      setStep(2);
      return;
    }

    setError("");
    setSubmitting(true);

    try {
      const location = [form.location.trim(), form.digitalAddress.trim()]
        .filter(Boolean)
        .join(" | ");

      const createdBusiness = await apiRequest("/businesses/", {
        method: "POST",
        body: JSON.stringify({
          name: form.name.trim(),
          business_type: form.type,
          phone: form.phone.trim(),
          email: form.email.trim(),
          location,
          invoicePrefix: form.invoicePrefix.trim().toUpperCase() || "INV",
          receiptPrefix: form.receiptPrefix.trim().toUpperCase() || "RCT",
        }),
      });

      await loadBusinesses(createdBusiness.id);
      completeOnboarding();
      navigate("/app/dashboard", { replace: true });
    } catch (setupError) {
      setError(setupError.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="onboarding-page">
      <header className="onboarding-header">
        <div className="onboarding-brand">
          <span>S</span>Stock<strong>Flow</strong>
        </div>
        <div className="onboarding-progress">
          {[1, 2, 3].map((number) => (
            <div
              className={step >= number ? "onboarding-step-active" : ""}
              key={number}
            >
              <span>{step > number ? <Check size={15} /> : number}</span>
              <strong>
                {number === 1
                  ? "Business type"
                  : number === 2
                    ? "Business details"
                    : "Invoice setup"}
              </strong>
            </div>
          ))}
        </div>
      </header>

      <section className="onboarding-card">
        {error ? <div className="form-alert form-alert-error">{error}</div> : null}

        {step === 1 ? (
          <>
            <div className="onboarding-heading">
              <span>Step 1 of 3</span>
              <h1>What kind of business are you setting up?</h1>
              <p>
                This controls the specialist product fields shown in your
                inventory.
              </p>
            </div>
            <div className="business-choice-grid">
              <button
                type="button"
                className={
                  form.type === "building_materials"
                    ? "business-choice-active"
                    : ""
                }
                onClick={() =>
                  setForm((current) => ({
                    ...current,
                    type: "building_materials",
                  }))
                }
              >
                <Layers3 size={30} />
                <strong>Building materials shop</strong>
                <span>
                  Tiles, cement, paint, plumbing, roofing and related products.
                </span>
                <small>
                  Includes tile design numbers, boxes, loose pieces and
                  coverage.
                </small>
              </button>
              <button
                type="button"
                className={
                  form.type === "boutique" ? "business-choice-active" : ""
                }
                onClick={() =>
                  setForm((current) => ({ ...current, type: "boutique" }))
                }
              >
                <Shirt size={30} />
                <strong>Boutique or fashion store</strong>
                <span>
                  Clothing, shoes, bags, accessories and related products.
                </span>
                <small>
                  Includes size, colour, style codes and product variants.
                </small>
              </button>
            </div>
          </>
        ) : null}

        {step === 2 ? (
          <>
            <div className="onboarding-heading">
              <span>Step 2 of 3</span>
              <h1>Tell us about the business.</h1>
              <p>
                This information will appear across the workspace and sales
                documents.
              </p>
            </div>
            <div className="onboarding-form-grid">
              <label>
                Business name
                <div className="input-with-icon">
                  <Building2 size={18} />
                  <input
                    name="name"
                    value={form.name}
                    onChange={handleChange}
                    required
                  />
                </div>
              </label>
              <label>
                Owner name
                <input
                  name="ownerName"
                  value={form.ownerName}
                  onChange={handleChange}
                  readOnly
                />
              </label>
              <label>
                Business phone
                <input
                  name="phone"
                  value={form.phone}
                  onChange={handleChange}
                  placeholder="+233..."
                />
              </label>
              <label>
                Email address
                <input
                  name="email"
                  type="email"
                  value={form.email}
                  onChange={handleChange}
                />
              </label>
              <label>
                Town or location
                <div className="input-with-icon">
                  <MapPin size={18} />
                  <input
                    name="location"
                    value={form.location}
                    onChange={handleChange}
                    placeholder="Kumasi, Ghana"
                  />
                </div>
              </label>
              <label>
                GhanaPost GPS address
                <input
                  name="digitalAddress"
                  value={form.digitalAddress}
                  onChange={handleChange}
                  placeholder="AK-000-0000"
                />
              </label>
            </div>
          </>
        ) : null}

        {step === 3 ? (
          <>
            <div className="onboarding-heading">
              <span>Step 3 of 3</span>
              <h1>Prepare your invoice identity.</h1>
              <p>You can edit these values later from Settings.</p>
            </div>
            <div className="invoice-setup-layout">
              <div className="invoice-setup-form">
                <label>
                  Invoice prefix
                  <input
                    name="invoicePrefix"
                    value={form.invoicePrefix}
                    onChange={handleChange}
                    maxLength={12}
                  />
                </label>
                <label>
                  Receipt prefix
                  <input
                    name="receiptPrefix"
                    value={form.receiptPrefix}
                    onChange={handleChange}
                    maxLength={12}
                  />
                </label>
                <label className="checkbox-label">
                  <input type="checkbox" defaultChecked /> Show business phone
                  on documents
                </label>
                <label className="checkbox-label">
                  <input type="checkbox" defaultChecked /> Show outstanding
                  balance on credit invoices
                </label>
                <label className="checkbox-label">
                  <input type="checkbox" /> Mark business as VAT registered
                </label>
              </div>
              <div className="invoice-paper-preview">
                <header>
                  <div>
                    <strong>{form.name || "Your business name"}</strong>
                    <span>{form.location || "Business location"}</span>
                  </div>
                  <b>{form.invoicePrefix || "INV"}-00001</b>
                </header>
                <div className="invoice-preview-lines">
                  <i />
                  <i />
                  <i />
                </div>
                <footer>
                  <span>Invoice total</span>
                  <strong>GHS 0.00</strong>
                </footer>
              </div>
            </div>
          </>
        ) : null}

        <div className="onboarding-actions">
          <Button
            variant="secondary"
            onClick={() => setStep((current) => Math.max(1, current - 1))}
            disabled={step === 1 || submitting}
          >
            <ArrowLeft size={18} /> Back
          </Button>
          {step < 3 ? (
            <Button
              onClick={() => setStep((current) => current + 1)}
              disabled={submitting}
            >
              Continue <ArrowRight size={18} />
            </Button>
          ) : (
            <Button onClick={finishSetup} disabled={submitting}>
              {submitting ? "Creating workspace..." : "Finish setup"}
              <Check size={18} />
            </Button>
          )}
        </div>
      </section>
    </main>
  );
}
