import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  Layers3,
  MapPin,
  ShieldCheck,
  Shirt,
  Smartphone,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import DealerItemsSelector from "../../components/business/DealerItemsSelector";
import Button from "../../components/ui/Button";
import { useAuth } from "../../context/AuthContext";
import { useStore } from "../../context/StoreContext";
import { apiRequest } from "../../services/api";

import "../../styles/onboarding-polish.css";

export default function OnboardingPage() {
  const { user, pendingRegistration, completeOnboarding } = useAuth();
  const { loadBusinesses } = useStore();
  const [step, setStep] = useState(1);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [createdBusinessId, setCreatedBusinessId] = useState("");
  const [createdPaymentAccountId, setCreatedPaymentAccountId] = useState("");
  const [form, setForm] = useState({
    type: "building_materials",
    dealsIn: [],
    name: pendingRegistration?.businessName ?? "",
    ownerName: pendingRegistration?.name ?? user?.name ?? "",
    email: pendingRegistration?.email ?? user?.email ?? "",
    phone: "",
    location: "",
    digitalAddress: "",
    momoNetwork: "",
    momoAccountName: pendingRegistration?.name ?? user?.name ?? "",
    momoNumber: "",
    momoNumberConfirm: "",
    invoicePrefix: "INV",
    receiptPrefix: "RCT",
    vatRegistered: false,
    vatRegistrationNumber: "",
  });
  const navigate = useNavigate();

  useEffect(() => {
    if (!error) return undefined;

    const timeoutId = window.setTimeout(() => {
      setError("");
    }, 4500);

    return () => window.clearTimeout(timeoutId);
  }, [error]);

  if (!pendingRegistration && !user) {
    return <Navigate to="/register" replace />;
  }

  function handleChange(event) {
    setForm((current) => ({
      ...current,
      [event.target.name]: event.target.type === "checkbox"
        ? event.target.checked
        : event.target.value,
    }));
  }

  function selectBusinessType(type) {
    setForm((current) => ({
      ...current,
      type,
      dealsIn: current.type === type ? current.dealsIn : [],
    }));
    setError("");
  }

  async function finishSetup() {
    if (!form.dealsIn.length) {
      setError("Select at least one item your business deals in.");
      setStep(2);
      return;
    }

    if (!form.name.trim()) {
      setError("Enter the business name before finishing setup.");
      setStep(2);
      return;
    }

    if (!form.momoNetwork) {
      setError("Select the Mobile Money network that will receive payouts.");
      setStep(3);
      return;
    }

    if (!form.momoAccountName.trim()) {
      setError("Enter the name registered on the Mobile Money account.");
      setStep(3);
      return;
    }

    const momoNumber = form.momoNumber.replace(/\s+/g, "");
    const momoNumberConfirm = form.momoNumberConfirm.replace(/\s+/g, "");

    if (!momoNumber) {
      setError("Enter the registered Mobile Money number.");
      setStep(3);
      return;
    }

    if (momoNumber !== momoNumberConfirm) {
      setError("The Mobile Money numbers do not match.");
      setStep(3);
      return;
    }

    if (
      form.vatRegistered &&
      !form.vatRegistrationNumber.trim()
    ) {
      setError(
        "Enter the VAT registration number before enabling VAT.",
      );
      setStep(4);
      return;
    }

    setError("");
    setSubmitting(true);

    try {
      const location = [form.location.trim(), form.digitalAddress.trim()]
        .filter(Boolean)
        .join(" | ");

      let businessId = createdBusinessId;

      if (!businessId) {
        const createdBusiness = await apiRequest("/businesses/", {
          method: "POST",
          body: JSON.stringify({
            name: form.name.trim(),
            business_type: form.type,
            dealsIn: form.dealsIn,
            phone: form.phone.trim(),
            email: form.email.trim(),
            location,
            invoicePrefix: form.invoicePrefix.trim().toUpperCase() || "INV",
            receiptPrefix: form.receiptPrefix.trim().toUpperCase() || "RCT",
            vatRegistered: Boolean(form.vatRegistered),
            vatRegistrationNumber:
              form.vatRegistrationNumber.trim(),
          }),
        });

        businessId = createdBusiness.id;
        setCreatedBusinessId(businessId);
      }

      const receivingAccountPayload = {
        accountType: "mobile_money",
        displayName: "Primary Mobile Money",
        bankName: "",
        accountName: form.momoAccountName.trim(),
        network: form.momoNetwork,
        accountNumber: momoNumber,
        isActive: true,
        isDefault: true,
      };

      let receivingAccount;

      if (createdPaymentAccountId) {
        receivingAccount = await apiRequest(
          `/businesses/${businessId}/payment-accounts/${createdPaymentAccountId}/`,
          {
            method: "PATCH",
            body: JSON.stringify(receivingAccountPayload),
          },
        );
      } else {
        receivingAccount = await apiRequest(
          `/businesses/${businessId}/payment-accounts/`,
          {
            method: "POST",
            body: JSON.stringify(receivingAccountPayload),
          },
        );

        if (receivingAccount?.id) {
          setCreatedPaymentAccountId(receivingAccount.id);
        }
      }

      if (!receivingAccount?.payoutReady && receivingAccount?.id) {
        receivingAccount = await apiRequest(
          `/businesses/${businessId}/payment-accounts/${receivingAccount.id}/payout-recipient/sync/`,
          {
            method: "POST",
          },
        );
      }

      if (!receivingAccount?.payoutReady) {
        throw new Error(
          "Your Mobile Money receiving account was saved, but Paystack could not connect it for payouts. Please try again.",
        );
      }

      await loadBusinesses(businessId);
      completeOnboarding();

      // Returns to the account-level business home after every workspace setup.
      navigate("/businesses", { replace: true });
    } catch (setupError) {
      setError(
        setupError.message ||
          "StockFlow could not finish the business setup.",
      );
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
          {[1, 2, 3, 4].map((number) => (
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
                    : number === 3
                      ? "Receiving account"
                      : "Invoice setup"}
              </strong>
            </div>
          ))}
        </div>
      </header>

      {error ? (
        <div
          className="onboarding-toast onboarding-toast-error"
          role="alert"
          aria-live="assertive"
        >
          <span className="onboarding-toast-icon">
            <AlertCircle size={20} />
          </span>
          <div className="onboarding-toast-copy">
            <strong>Unable to continue</strong>
            <span>{error}</span>
          </div>
          <button
            type="button"
            className="onboarding-toast-close"
            onClick={() => setError("")}
            aria-label="Dismiss error"
          >
            <X size={18} />
          </button>
        </div>
      ) : null}

      <section className="onboarding-card">
        {step === 1 ? (
          <>
            <div className="onboarding-heading">
              <span>Step 1 of 4</span>
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
                onClick={() => selectBusinessType("building_materials")}
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
                onClick={() => selectBusinessType("boutique")}
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
              <span>Step 2 of 4</span>
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

            <DealerItemsSelector
              businessType={form.type}
              value={form.dealsIn}
              onChange={(dealsIn) =>
                setForm((current) => ({ ...current, dealsIn }))
              }
            />
          </>
        ) : null}

        {step === 3 ? (
          <>
            <div className="onboarding-heading">
              <span>Step 3 of 4</span>
              <h1>Where should StockFlow send your money?</h1>
              <p>
                Add the registered Mobile Money account that will receive
                verified customer payments through Paystack.
              </p>
            </div>

            <div className="onboarding-payout-card">
              <div className="onboarding-payout-title">
                <span className="onboarding-payout-icon">
                  <Smartphone size={22} />
                </span>
                <div>
                  <strong>Primary Mobile Money receiving account</strong>
                  <p>
                    This account becomes the default payout destination for
                    this business.
                  </p>
                </div>
              </div>

              <div className="onboarding-form-grid">
                <label>
                  Mobile Money network
                  <select
                    name="momoNetwork"
                    value={form.momoNetwork}
                    onChange={handleChange}
                    required
                  >
                    <option value="">Select network</option>
                    <option value="mtn">MTN Mobile Money</option>
                    <option value="telecel">Telecel Cash</option>
                    <option value="airteltigo">ATMoney / AirtelTigo Money</option>
                  </select>
                </label>

                <label>
                  Registered account name
                  <input
                    name="momoAccountName"
                    value={form.momoAccountName}
                    onChange={handleChange}
                    placeholder="Name registered on the wallet"
                    maxLength={150}
                    autoComplete="name"
                    required
                  />
                </label>

                <label>
                  Registered Mobile Money number
                  <input
                    name="momoNumber"
                    value={form.momoNumber}
                    onChange={handleChange}
                    placeholder="e.g. 0241234567"
                    inputMode="tel"
                    autoComplete="tel"
                    maxLength={20}
                    required
                  />
                </label>

                <label>
                  Confirm Mobile Money number
                  <input
                    name="momoNumberConfirm"
                    value={form.momoNumberConfirm}
                    onChange={handleChange}
                    placeholder="Enter the number again"
                    inputMode="tel"
                    autoComplete="off"
                    maxLength={20}
                    required
                  />
                </label>
              </div>

              <div className="onboarding-payout-security">
                <ShieldCheck size={19} />
                <p>
                  The full wallet number is encrypted in StockFlow. Paystack
                  receives it only when StockFlow connects your payout
                  destination.
                </p>
              </div>
            </div>
          </>
        ) : null}

        {step === 4 ? (
          <>
            <div className="onboarding-heading">
              <span>Step 4 of 4</span>
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
              <input
                type="checkbox"
                name="vatRegistered"
                checked={form.vatRegistered}
                onChange={handleChange}
              />
              Mark business as VAT registered
            </label>
            {form.vatRegistered ? (
              <label>
                VAT registration number
                <input
                  name="vatRegistrationNumber"
                  value={form.vatRegistrationNumber}
                  onChange={handleChange}
                  maxLength={80}
                  placeholder="Enter VAT registration number"
                  required
                />
              </label>
            ) : null}
              </div>
              <div className="invoice-paper-preview">
                <header>
                  <div>
                    <strong>{form.name || "Your business name"}</strong>
                    <span>{form.location || "Business location"}</span>
                    <span>
                      {form.dealsIn.length
                        ? `Deals in: ${form.dealsIn.join(", ")}`
                        : "Deals in: Select your business items"}
                    </span>
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
          {step < 4 ? (
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
