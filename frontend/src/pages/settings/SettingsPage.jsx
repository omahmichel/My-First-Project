import { Bell, Building2, FileText, Save, ShieldCheck } from "lucide-react";
import { useState } from "react";

import Button from "../../components/ui/Button";
import PageHeader from "../../components/ui/PageHeader";
import { useStore } from "../../context/StoreContext";

export default function SettingsPage() {
  const { business, updateBusiness } = useStore();
  const [form, setForm] = useState(business);
  const [saved, setSaved] = useState(false);

  function handleChange(event) {
    const { name, value, type, checked } = event.target;
    setForm((current) => ({ ...current, [name]: type === "checkbox" ? checked : value }));
    setSaved(false);
  }

  function submit(event) {
    event.preventDefault();
    updateBusiness(form);
    setSaved(true);
  }

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Business configuration" title="Settings" description="Control business identity, document numbering and notification preferences." />

      {saved ? <div className="form-alert form-alert-success">Settings saved successfully.</div> : null}

      <form className="settings-layout" onSubmit={submit}>
        <aside className="settings-navigation panel-card">
          <a href="#business"><Building2 size={18} /> Business profile</a>
          <a href="#documents"><FileText size={18} /> Documents</a>
          <a href="#notifications"><Bell size={18} /> Notifications</a>
          <a href="#security"><ShieldCheck size={18} /> Security</a>
        </aside>

        <div className="settings-content-stack">
          <section className="panel-card settings-section" id="business">
            <header><div><span>Business identity</span><h2>Business profile</h2></div></header>
            <div className="settings-form-grid">
              <label>Business name<input name="name" value={form.name || ""} onChange={handleChange} /></label>
              <label>Business type<select name="type" value={form.type || "building_materials"} onChange={handleChange}><option value="building_materials">Building materials</option><option value="boutique">Boutique</option></select></label>
              <label>Owner name<input name="ownerName" value={form.ownerName || ""} onChange={handleChange} /></label>
              <label>Phone number<input name="phone" value={form.phone || ""} onChange={handleChange} /></label>
              <label>Email address<input name="email" type="email" value={form.email || ""} onChange={handleChange} /></label>
              <label>Location<input name="location" value={form.location || ""} onChange={handleChange} /></label>
              <label>GhanaPost GPS<input name="digitalAddress" value={form.digitalAddress || ""} onChange={handleChange} /></label>
            </div>
          </section>

          <section className="panel-card settings-section" id="documents">
            <header><div><span>Numbering and tax</span><h2>Invoice settings</h2></div></header>
            <div className="settings-form-grid">
              <label>Invoice prefix<input name="invoicePrefix" value={form.invoicePrefix || "INV"} onChange={handleChange} maxLength="6" /></label>
              <label>Receipt prefix<input name="receiptPrefix" value={form.receiptPrefix || "RCT"} onChange={handleChange} maxLength="6" /></label>
              <label>Currency<select name="currency" value={form.currency || "GHS"} onChange={handleChange}><option value="GHS">Ghana cedi (GHS)</option></select></label>
            </div>
            <label className="checkbox-label settings-checkbox"><input type="checkbox" /> This business is VAT registered</label>
            <p className="settings-note">Ordinary invoices must not be described as official GRA E-VAT receipts until approved integration exists.</p>
          </section>

          <section className="panel-card settings-section" id="notifications">
            <header><div><span>Alerts</span><h2>Notifications</h2></div></header>
            <label className="checkbox-label settings-checkbox"><input name="lowStockAlerts" type="checkbox" checked={Boolean(form.lowStockAlerts)} onChange={handleChange} /> Show low-stock alerts on the dashboard</label>
            <label className="checkbox-label settings-checkbox"><input type="checkbox" defaultChecked /> Notify the owner about large discounts</label>
            <label className="checkbox-label settings-checkbox"><input type="checkbox" defaultChecked /> Notify the owner about stock adjustments</label>
          </section>

          <section className="panel-card settings-section" id="security">
            <header><div><span>Access protection</span><h2>Security status</h2></div></header>
            <div className="security-status-list"><div><span>Role-based permissions</span><strong>Prepared</strong></div><div><span>JWT authentication</span><strong>Backend phase</strong></div><div><span>Audit logging</span><strong>Architecture ready</strong></div></div>
          </section>

          <div className="settings-save-row"><Button type="submit" size="large"><Save size={18} /> Save settings</Button></div>
        </div>
      </form>
    </div>
  );
}
