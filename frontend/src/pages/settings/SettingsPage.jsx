import {
  BadgePercent,
  Building2,
  FileText,
  Save,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";

import Button from "../../components/ui/Button";
import PageHeader from "../../components/ui/PageHeader";
import { useStore } from "../../context/StoreContext";

import "../../styles/vat-settings.css";

function formFromBusiness(business) {
  return {
    id: business?.id || "",
    name: business?.name || "",
    type: business?.type || "building_materials",
    phone: business?.phone || "",
    email: business?.email || "",
    location: business?.location || "",
    invoicePrefix: business?.invoicePrefix || "INV",
    receiptPrefix: business?.receiptPrefix || "RCT",
    vatRegistered: Boolean(business?.vatRegistered),
    vatRegistrationNumber:
      business?.vatRegistrationNumber || "",
  };
}

export default function SettingsPage() {
  const {
    business,
    businessesLoading,
    businessesError,
    updateBusiness,
  } = useStore();

  const [form, setForm] = useState(() =>
    formFromBusiness(business),
  );
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saving, setSaving] = useState(false);

  // Keeps the form synchronized after switching businesses.
  useEffect(() => {
    setForm(formFromBusiness(business));
    setSaved(false);
    setSaveError("");
  }, [business]);

  function handleChange(event) {
    const { name, value } = event.target;

    setForm((current) => ({
      ...current,
      [name]: event.target.type === "checkbox"
        ? event.target.checked
        : value,
    }));
    setSaved(false);
    setSaveError("");
  }

  async function submit(event) {
    event.preventDefault();

    if (saving) return;

    if (
      form.vatRegistered &&
      !form.vatRegistrationNumber.trim()
    ) {
      setSaved(false);
      setSaveError(
        "Enter the VAT registration number before enabling VAT.",
      );
      return;
    }

    setSaving(true);
    setSaved(false);
    setSaveError("");

    try {
      const updatedBusiness = await updateBusiness(form);
      setForm(formFromBusiness(updatedBusiness));
      setSaved(true);
    } catch (error) {
      setSaveError(error.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Business configuration"
        title="Settings"
        description="Update the active business identity and document numbering stored in Django."
      />

      {businessesLoading ? (
        <div className="form-alert" role="status">
          Loading business settings...
        </div>
      ) : null}

      {businessesError || saveError ? (
        <div className="form-alert form-alert-error" role="alert">
          {saveError || businessesError}
        </div>
      ) : null}

      {saved ? (
        <div className="form-alert form-alert-success" role="status">
          Settings saved successfully.
        </div>
      ) : null}

      <form className="settings-layout" onSubmit={submit}>
        <aside className="settings-navigation panel-card">
          <a href="#business">
            <Building2 size={18} />
            Business profile
          </a>
          <a href="#documents">
            <FileText size={18} />
            Documents
          </a>
          <a href="#vat">
            <BadgePercent size={18} />
            VAT
          </a>
          <a href="#security">
            <ShieldCheck size={18} />
            Security
          </a>
        </aside>

        <div className="settings-content-stack">
          <section
            className="panel-card settings-section"
            id="business"
          >
            <header>
              <div>
                <span>Business identity</span>
                <h2>Business profile</h2>
              </div>
            </header>

            <div className="settings-form-grid">
              <label>
                Business name
                <input
                  name="name"
                  value={form.name}
                  onChange={handleChange}
                  required
                />
              </label>

              <label>
                Business type
                <select
                  name="type"
                  value={form.type}
                  onChange={handleChange}
                >
                  <option value="building_materials">
                    Building materials
                  </option>
                  <option value="boutique">Boutique</option>
                </select>
              </label>

              <label>
                Owner
                <input
                  value={business?.ownerName || ""}
                  readOnly
                />
              </label>

              <label>
                Owner account
                <input
                  value={business?.ownerEmail || ""}
                  readOnly
                />
              </label>

              <label>
                Business phone
                <input
                  name="phone"
                  value={form.phone}
                  onChange={handleChange}
                />
              </label>

              <label>
                Business email
                <input
                  name="email"
                  type="email"
                  value={form.email}
                  onChange={handleChange}
                />
              </label>

              <label>
                Location
                <input
                  name="location"
                  value={form.location}
                  onChange={handleChange}
                />
              </label>
            </div>
          </section>

          <section
            className="panel-card settings-section"
            id="documents"
          >
            <header>
              <div>
                <span>Numbering and currency</span>
                <h2>Invoice settings</h2>
              </div>
            </header>

            <div className="settings-form-grid">
              <label>
                Invoice prefix
                <input
                  name="invoicePrefix"
                  value={form.invoicePrefix}
                  onChange={handleChange}
                  maxLength="12"
                  required
                />
              </label>

              <label>
                Receipt prefix
                <input
                  name="receiptPrefix"
                  value={form.receiptPrefix}
                  onChange={handleChange}
                  maxLength="12"
                  required
                />
              </label>

              <label>
                Currency
                <select value="GHS" disabled>
                  <option value="GHS">
                    Ghana cedi (GHS)
                  </option>
                </select>
              </label>
            </div>

            <p className="settings-note">
              Prefixes allow letters, numbers and hyphens. New documents use
              the updated prefixes; existing invoices and receipts keep their
              original numbers.
            </p>
          </section>

          <section
            className="panel-card settings-section settings-vat-section"
            id="vat"
          >
            <header>
              <div>
                <span>Tax registration</span>
                <h2>VAT settings</h2>
              </div>
            </header>

            <div className="settings-vat-card">
              <div>
                <strong>VAT registered business</strong>
                <p>
                  Enable this when the active business is registered
                  for VAT. This setting is stored separately for each
                  business workspace.
                </p>
              </div>

              <label className="settings-vat-toggle">
                <input
                  type="checkbox"
                  name="vatRegistered"
                  checked={form.vatRegistered}
                  onChange={handleChange}
                />
                <span aria-hidden="true" />
                <strong>
                  {form.vatRegistered ? "Enabled" : "Not enabled"}
                </strong>
              </label>
            </div>

            <div className="settings-form-grid settings-vat-fields">
              <label>
                VAT registration number
                <input
                  name="vatRegistrationNumber"
                  value={form.vatRegistrationNumber}
                  onChange={handleChange}
                  maxLength="80"
                  placeholder="Enter VAT registration number"
                  disabled={!form.vatRegistered}
                  required={form.vatRegistered}
                />
              </label>
            </div>

            <p className="settings-note">
              VAT registration is saved separately for the active
              business. This setting does not change invoice totals.
            </p>
          </section>

          <section
            className="panel-card settings-section"
            id="security"
          >
            <header>
              <div>
                <span>Access protection</span>
                <h2>Security status</h2>
              </div>
            </header>

            <div className="security-status-list">
              <div>
                <span>Role-based permissions</span>
                <strong>Active</strong>
              </div>
              <div>
                <span>JWT authentication</span>
                <strong>Active</strong>
              </div>
              <div>
                <span>Business isolation</span>
                <strong>Active</strong>
              </div>
            </div>
          </section>

          <div className="settings-save-row">
            <Button
              type="submit"
              size="large"
              disabled={saving || businessesLoading}
            >
              <Save size={18} />
              {saving ? "Saving..." : "Save settings"}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
