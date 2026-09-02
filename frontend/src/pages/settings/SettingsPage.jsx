import {
  BadgePercent,
  Building2,
  CreditCard,
  FileText,
  Save,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";

import DealerItemsSelector from "../../components/business/DealerItemsSelector";
import Button from "../../components/ui/Button";
import PageHeader from "../../components/ui/PageHeader";
import { useStore } from "../../context/StoreContext";

import "../../styles/vat-settings.css";
import "../../styles/payment-account-settings.css";

function emptyPaymentAccountForm() {
  return {
    accountType: "bank",
    displayName: "",
    bankName: "",
    accountName: "",
    network: "",
    accountNumber: "",
    isDefault: false,
    isActive: true,
  };
}

function paymentAccountFormFromRecord(account) {
  return {
    accountType: account?.accountType || "bank",
    displayName: account?.displayName || "",
    bankName: account?.bankName || "",
    accountName: account?.accountName || "",
    network: account?.network || "",
    accountNumber: "",
    isDefault: Boolean(account?.isDefault),
    isActive: account?.isActive !== false,
  };
}

function formFromBusiness(business) {
  return {
    id: business?.id || "",
    name: business?.name || "",
    type: business?.type || "building_materials",
    dealsIn: Array.isArray(business?.dealsIn)
      ? business.dealsIn
      : [],
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
    paymentAccounts,
    paymentAccountsLoading,
    paymentAccountsError,
    createPaymentAccount,
    updatePaymentAccount,
    setDefaultPaymentAccount,
    deactivatePaymentAccount,
    reactivatePaymentAccount,
  } = useStore();

  const [form, setForm] = useState(() =>
    formFromBusiness(business),
  );
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saving, setSaving] = useState(false);

  // Keeps receiving-account editing separate from general business settings.
  const [paymentAccountForm, setPaymentAccountForm] = useState(
    emptyPaymentAccountForm,
  );
  const [editingPaymentAccountId, setEditingPaymentAccountId] =
    useState("");
  const [paymentAccountSaving, setPaymentAccountSaving] =
    useState(false);
  const [paymentAccountMessage, setPaymentAccountMessage] =
    useState("");
  const [
    paymentAccountActionError,
    setPaymentAccountActionError,
  ] = useState("");

  const canManagePaymentAccounts = ["owner", "manager"].includes(
    business?.currentUserRole,
  );

  // Keeps both settings areas synchronized after switching businesses.
  useEffect(() => {
    setForm(formFromBusiness(business));
    setSaved(false);
    setSaveError("");
    setPaymentAccountForm(emptyPaymentAccountForm());
    setEditingPaymentAccountId("");
    setPaymentAccountMessage("");
    setPaymentAccountActionError("");
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

  function handlePaymentAccountChange(event) {
    const { name, value, type, checked } = event.target;

    setPaymentAccountForm((current) => ({
      ...current,
      [name]: type === "checkbox" ? checked : value,
    }));
    setPaymentAccountMessage("");
    setPaymentAccountActionError("");
  }

  function resetPaymentAccountEditor() {
    setEditingPaymentAccountId("");
    setPaymentAccountForm(emptyPaymentAccountForm());
    setPaymentAccountMessage("");
    setPaymentAccountActionError("");
  }

  function startEditingPaymentAccount(account) {
    setEditingPaymentAccountId(String(account.id));
    setPaymentAccountForm(paymentAccountFormFromRecord(account));
    setPaymentAccountMessage("");
    setPaymentAccountActionError("");
  }

  async function savePaymentAccount() {
    if (paymentAccountSaving || !canManagePaymentAccounts) return;

    if (!paymentAccountForm.displayName.trim()) {
      setPaymentAccountActionError(
        "Enter a display name for the receiving account.",
      );
      return;
    }

    if (!paymentAccountForm.accountName.trim()) {
      setPaymentAccountActionError(
        "Enter the receiving account name.",
      );
      return;
    }

    if (
      paymentAccountForm.accountType === "bank" &&
      !paymentAccountForm.bankName.trim()
    ) {
      setPaymentAccountActionError(
        "Enter the receiving bank name.",
      );
      return;
    }

    if (
      paymentAccountForm.accountType === "mobile_money" &&
      !paymentAccountForm.network.trim()
    ) {
      setPaymentAccountActionError(
        "Select the receiving Mobile Money network.",
      );
      return;
    }

    if (
      !editingPaymentAccountId &&
      !paymentAccountForm.accountNumber.trim()
    ) {
      setPaymentAccountActionError(
        "Enter the receiving account or wallet number.",
      );
      return;
    }

    setPaymentAccountSaving(true);
    setPaymentAccountMessage("");
    setPaymentAccountActionError("");

    try {
      if (editingPaymentAccountId) {
        await updatePaymentAccount(
          editingPaymentAccountId,
          paymentAccountForm,
        );
        setPaymentAccountMessage("Receiving account updated.");
      } else {
        await createPaymentAccount(paymentAccountForm);
        setPaymentAccountMessage("Receiving account added.");
      }

      setEditingPaymentAccountId("");
      setPaymentAccountForm(emptyPaymentAccountForm());
    } catch (error) {
      setPaymentAccountActionError(error.message);
    } finally {
      setPaymentAccountSaving(false);
    }
  }

  async function makePaymentAccountDefault(account) {
    if (paymentAccountSaving || !canManagePaymentAccounts) return;

    setPaymentAccountSaving(true);
    setPaymentAccountMessage("");
    setPaymentAccountActionError("");

    try {
      await setDefaultPaymentAccount(account.id);
      setPaymentAccountMessage(
        `${account.displayName} is now the default receiving account.`,
      );
    } catch (error) {
      setPaymentAccountActionError(error.message);
    } finally {
      setPaymentAccountSaving(false);
    }
  }

  async function togglePaymentAccountStatus(account) {
    if (paymentAccountSaving || !canManagePaymentAccounts) return;

    setPaymentAccountSaving(true);
    setPaymentAccountMessage("");
    setPaymentAccountActionError("");

    try {
      if (account.isActive === false) {
        await reactivatePaymentAccount(account.id);
        setPaymentAccountMessage("Receiving account reactivated.");
      } else {
        await deactivatePaymentAccount(account.id);
        setPaymentAccountMessage("Receiving account deactivated.");
      }

      if (String(account.id) === editingPaymentAccountId) {
        setEditingPaymentAccountId("");
        setPaymentAccountForm(emptyPaymentAccountForm());
      }
    } catch (error) {
      setPaymentAccountActionError(error.message);
    } finally {
      setPaymentAccountSaving(false);
    }
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
          <a href="#payment-accounts">
            <CreditCard size={18} />
            Receiving accounts
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

            <DealerItemsSelector
              businessType={form.type}
              value={form.dealsIn}
              onChange={(dealsIn) => {
                setForm((current) => ({ ...current, dealsIn }));
                setSaved(false);
                setSaveError("");
              }}
              compact
            />
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
            className="panel-card settings-section payment-account-settings"
            id="payment-accounts"
          >
            <header>
              <div>
                <span>Payment destinations</span>
                <h2>Receiving accounts</h2>
              </div>
            </header>

            <p className="settings-note">
              Receiving accounts are isolated to the active business.
              StockFlow encrypts the full number and shows only the
              masked final four digits after saving.
            </p>

            {paymentAccountsError || paymentAccountActionError ? (
              <div
                className="form-alert form-alert-error payment-account-alert"
                role="alert"
              >
                {paymentAccountActionError || paymentAccountsError}
              </div>
            ) : null}

            {paymentAccountMessage ? (
              <div
                className="form-alert form-alert-success payment-account-alert"
                role="status"
              >
                {paymentAccountMessage}
              </div>
            ) : null}

            {paymentAccountsLoading ? (
              <div
                className="form-alert payment-account-alert"
                role="status"
              >
                Loading receiving accounts...
              </div>
            ) : null}

            <div className="payment-account-list">
              {!paymentAccountsLoading && !paymentAccounts.length ? (
                <div className="payment-account-empty">
                  No receiving accounts have been added for this
                  business yet.
                </div>
              ) : null}

              {paymentAccounts.map((account) => (
                <article
                  className={`payment-account-card ${
                    account.isActive === false ? "is-inactive" : ""
                  }`}
                  key={account.id}
                >
                  <div className="payment-account-card-main">
                    <div>
                      <strong>{account.displayName}</strong>
                      <span>
                        {account.accountType === "bank"
                          ? account.bankName
                          : account.network || "Mobile Money"}
                      </span>
                    </div>

                    <div className="payment-account-number">
                      <strong>{account.maskedNumber}</strong>
                      <span>{account.accountName}</span>
                    </div>
                  </div>

                  <div className="payment-account-badges">
                    <span>
                      {account.accountType === "bank"
                        ? "Bank account"
                        : "Mobile Money"}
                    </span>
                    {account.isDefault ? <strong>Default</strong> : null}
                    <span>
                      {account.isActive === false
                        ? "Inactive"
                        : "Active"}
                    </span>
                  </div>

                  {canManagePaymentAccounts ? (
                    <div className="payment-account-actions">
                      <Button
                        type="button"
                        variant="secondary"
                        size="small"
                        onClick={() =>
                          startEditingPaymentAccount(account)
                        }
                        disabled={paymentAccountSaving}
                      >
                        Edit
                      </Button>

                      {!account.isDefault &&
                      account.isActive !== false ? (
                        <Button
                          type="button"
                          variant="secondary"
                          size="small"
                          onClick={() =>
                            makePaymentAccountDefault(account)
                          }
                          disabled={paymentAccountSaving}
                        >
                          Make default
                        </Button>
                      ) : null}

                      <Button
                        type="button"
                        variant="secondary"
                        size="small"
                        onClick={() =>
                          togglePaymentAccountStatus(account)
                        }
                        disabled={paymentAccountSaving}
                      >
                        {account.isActive === false
                          ? "Reactivate"
                          : "Deactivate"}
                      </Button>
                    </div>
                  ) : null}
                </article>
              ))}
            </div>

            {canManagePaymentAccounts ? (
              <div
                className="payment-account-editor"
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter" &&
                    event.target.tagName !== "BUTTON"
                  ) {
                    event.preventDefault();
                    savePaymentAccount();
                  }
                }}
              >
                <div className="payment-account-editor-heading">
                  <div>
                    <span>
                      {editingPaymentAccountId
                        ? "Update receiving account"
                        : "New receiving account"}
                    </span>
                    <h3>
                      {editingPaymentAccountId
                        ? "Edit account"
                        : "Add account"}
                    </h3>
                  </div>

                  {editingPaymentAccountId ? (
                    <Button
                      type="button"
                      variant="secondary"
                      size="small"
                      onClick={resetPaymentAccountEditor}
                      disabled={paymentAccountSaving}
                    >
                      Cancel edit
                    </Button>
                  ) : null}
                </div>

                <div className="settings-form-grid payment-account-form-grid">
                  <label>
                    Account type
                    <select
                      name="accountType"
                      value={paymentAccountForm.accountType}
                      onChange={handlePaymentAccountChange}
                      disabled={paymentAccountSaving}
                    >
                      <option value="bank">Bank account</option>
                      <option value="mobile_money">
                        Mobile Money wallet
                      </option>
                    </select>
                  </label>

                  <label>
                    Display name
                    <input
                      name="displayName"
                      value={paymentAccountForm.displayName}
                      onChange={handlePaymentAccountChange}
                      placeholder="e.g. Main GCB Account"
                      maxLength="120"
                      disabled={paymentAccountSaving}
                    />
                  </label>

                  {paymentAccountForm.accountType === "bank" ? (
                    <label>
                      Bank name
                      <input
                        name="bankName"
                        value={paymentAccountForm.bankName}
                        onChange={handlePaymentAccountChange}
                        placeholder="e.g. GCB Bank"
                        maxLength="120"
                        disabled={paymentAccountSaving}
                      />
                    </label>
                  ) : (
                    <label>
                      Mobile Money network
                      <select
                        name="network"
                        value={paymentAccountForm.network}
                        onChange={handlePaymentAccountChange}
                        disabled={paymentAccountSaving}
                      >
                        <option value="">Select network</option>
                        <option value="mtn">
                          MTN Mobile Money
                        </option>
                        <option value="telecel">
                          Telecel Cash
                        </option>
                        <option value="airteltigo">
                          AirtelTigo Money
                        </option>
                      </select>
                    </label>
                  )}

                  <label>
                    Account name
                    <input
                      name="accountName"
                      value={paymentAccountForm.accountName}
                      onChange={handlePaymentAccountChange}
                      placeholder="Name registered on the account"
                      maxLength="150"
                      disabled={paymentAccountSaving}
                    />
                  </label>

                  <label>
                    {editingPaymentAccountId
                      ? "Replace account number (optional)"
                      : "Account or wallet number"}
                    <input
                      name="accountNumber"
                      value={paymentAccountForm.accountNumber}
                      onChange={handlePaymentAccountChange}
                      placeholder={
                        editingPaymentAccountId
                          ? "Leave blank to keep the current number"
                          : "Enter account or wallet number"
                      }
                      maxLength="40"
                      autoComplete="off"
                      disabled={paymentAccountSaving}
                    />
                  </label>

                  <label className="payment-account-default-field">
                    <input
                      type="checkbox"
                      name="isDefault"
                      checked={paymentAccountForm.isDefault}
                      onChange={handlePaymentAccountChange}
                      disabled={paymentAccountSaving}
                    />
                    <span>Use as the default receiving account</span>
                  </label>
                </div>

                <div className="payment-account-editor-actions">
                  <Button
                    type="button"
                    onClick={savePaymentAccount}
                    disabled={paymentAccountSaving}
                  >
                    {paymentAccountSaving
                      ? "Saving account..."
                      : editingPaymentAccountId
                        ? "Update account"
                        : "Add receiving account"}
                  </Button>
                </div>
              </div>
            ) : (
              <p className="settings-note">
                Only the business owner or a manager can change
                receiving accounts. Active accounts remain available
                to authorized checkout staff.
              </p>
            )}
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
