import {
  AlertCircle,
  Bug,
  CheckCircle2,
  Headphones,
  LoaderCircle,
  Mail,
  Send,
} from "lucide-react";
import { useState } from "react";

import { useAuth } from "../../context/AuthContext";
import { useStore } from "../../context/StoreContext";
import { apiRequest } from "../../services/api";

import "../../styles/support.css";


const ISSUE_CATEGORIES = [
  { value: "general", label: "General issue" },
  { value: "inventory", label: "Inventory or stock" },
  { value: "sales", label: "Sales" },
  {
    value: "invoice_document",
    label: "Invoice, receipt or waybill",
  },
  { value: "customer", label: "Customer records" },
  {
    value: "payment_subscription",
    label: "Payment or subscription",
  },
  { value: "account_login", label: "Account or login" },
  { value: "performance", label: "Performance or loading" },
  { value: "data_issue", label: "Incorrect or missing data" },
  { value: "other", label: "Other" },
];


export default function ReportIssuePage() {
  const { user } = useAuth();
  const { business } = useStore();
  const [form, setForm] = useState({
    category: "general",
    subject: "",
    description: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState(null);

  function handleChange(event) {
    const { name, value } = event.target;
    setForm((current) => ({
      ...current,
      [name]: value,
    }));

    if (notice) {
      setNotice(null);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();

    if (!business.id || submitting) return;

    const subject = form.subject.trim();
    const description = form.description.trim();

    if (subject.length < 5 || description.length < 10) {
      setNotice({
        tone: "error",
        message:
          "Add a clear subject and enough detail for us to investigate.",
      });
      return;
    }

    setSubmitting(true);
    setNotice(null);

    try {
      const response = await apiRequest(
        `/businesses/${business.id}/support/issues/`,
        {
          method: "POST",
          body: JSON.stringify({
            category: form.category,
            subject,
            description,
          }),
        },
      );

      setForm({
        category: "general",
        subject: "",
        description: "",
      });
      setNotice({
        tone: "success",
        message:
          response.detail ||
          "Your report has been sent. We'll respond as quickly as possible.",
      });
    } catch (error) {
      setNotice({
        tone: "error",
        message:
          error.message ||
          "Your report could not be sent right now. Please try again.",
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="support-page">
      <header className="support-page-heading">
        <span>StockFlow support</span>
        <h1>Report an issue</h1>
        <p>
          Tell us what went wrong and we will review it as quickly as
          possible.
        </p>
      </header>

      <div className="support-page-grid">
        <article className="support-form-card">
          <div className="support-card-heading">
            <div className="support-heading-icon">
              <Bug size={22} />
            </div>

            <div>
              <h2>Describe the problem</h2>
              <p>
                Give us enough detail to understand what happened and
                what you expected StockFlow to do.
              </p>
            </div>
          </div>

          {notice ? (
            <div
              className={`support-notice support-notice-${notice.tone}`}
              role={notice.tone === "error" ? "alert" : "status"}
            >
              {notice.tone === "success" ? (
                <CheckCircle2 size={20} />
              ) : (
                <AlertCircle size={20} />
              )}
              <span>{notice.message}</span>
            </div>
          ) : null}

          <form className="support-form" onSubmit={handleSubmit}>
            <label>
              <span>Issue category</span>
              <select
                name="category"
                value={form.category}
                onChange={handleChange}
                disabled={submitting}
              >
                {ISSUE_CATEGORIES.map((category) => (
                  <option key={category.value} value={category.value}>
                    {category.label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span>Subject</span>
              <input
                type="text"
                name="subject"
                value={form.subject}
                onChange={handleChange}
                placeholder="Example: Stock quantity did not update"
                maxLength={120}
                disabled={submitting}
                required
              />
              <small>{form.subject.length}/120 characters</small>
            </label>

            <label>
              <span>What happened?</span>
              <textarea
                name="description"
                value={form.description}
                onChange={handleChange}
                placeholder={
                  "Explain what you were doing, what happened, and " +
                  "what you expected to happen."
                }
                rows={8}
                maxLength={5000}
                disabled={submitting}
                required
              />
              <small>{form.description.length}/5000 characters</small>
            </label>

            <button
              type="submit"
              className="support-submit-button"
              disabled={submitting || !business.id}
            >
              {submitting ? (
                <>
                  <LoaderCircle
                    className="support-spinner"
                    size={18}
                  />
                  Sending report...
                </>
              ) : (
                <>
                  <Send size={18} />
                  Send report
                </>
              )}
            </button>
          </form>
        </article>

        <aside className="support-info-card">
          <div className="support-info-icon">
            <Headphones size={25} />
          </div>

          <span>Direct support</span>
          <h2>We receive your report by email.</h2>
          <p>
            StockFlow sends the issue securely through the backend to
            our support inbox. Your account and business context are
            attached automatically so we can investigate faster.
          </p>

          <div className="support-email-row">
            <Mail size={18} />
            <div>
              <span>Support email</span>
              <strong>stockflowghana@gmail.com</strong>
            </div>
          </div>

          <div className="support-context-box">
            <span>Included automatically</span>
            <strong>{user?.name || "Your StockFlow account"}</strong>
            <small>{user?.email || "Registered account email"}</small>
            <strong>{business.name || "Current business"}</strong>
            <small>
              {business.currentUserRole || "Business member"} ·{" "}
              {business.type === "boutique"
                ? "Boutique"
                : "Building materials"}
            </small>
          </div>

          <p className="support-privacy-note">
            Never include passwords, OTP codes, card PINs, or other
            secret credentials in a support report.
          </p>
        </aside>
      </div>
    </section>
  );
}
