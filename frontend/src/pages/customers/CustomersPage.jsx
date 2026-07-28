import { CreditCard, Phone, Plus, Search, UserRound } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import PageHeader from "../../components/ui/PageHeader";
import { useStore } from "../../context/StoreContext";
import { formatCurrency, formatDate } from "../../utils/formatters";

export default function CustomersPage() {
  const navigate = useNavigate();
  const { customers, addCustomer, recordCustomerPayment } = useStore();
  const [search, setSearch] = useState("");
  const [customerModalOpen, setCustomerModalOpen] = useState(false);
  const [paymentCustomer, setPaymentCustomer] = useState(null);
  const [form, setForm] = useState({ name: "", phone: "", email: "", address: "" });
  const [paymentAmount, setPaymentAmount] = useState("");
  const [error, setError] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const filtered = useMemo(() => customers.filter((customer) => [customer.name, customer.phone, customer.email, customer.address]
    .filter(Boolean)
    .some((value) => value.toLowerCase().includes(search.trim().toLowerCase()))), [customers, search]);

  const totalPages = Math.max(
    1,
    Math.ceil(filtered.length / pageSize),
  );

  const safeCurrentPage = Math.min(currentPage, totalPages);

  const paginatedCustomers = useMemo(() => {
    const startIndex = (safeCurrentPage - 1) * pageSize;

    return filtered.slice(startIndex, startIndex + pageSize);
  }, [filtered, pageSize, safeCurrentPage]);

  const firstVisibleRecord = filtered.length
    ? (safeCurrentPage - 1) * pageSize + 1
    : 0;

  const lastVisibleRecord = filtered.length
    ? firstVisibleRecord + paginatedCustomers.length - 1
    : 0;

  // Returns to page one whenever search or page size changes.
  useEffect(() => {
    setCurrentPage(1);
  }, [search, pageSize]);

  // Keeps the selected page inside the available page range.
  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  const totalDebt = customers.reduce((sum, customer) => sum + customer.outstandingBalance, 0);

  function handleCustomerSubmit(event) {
    event.preventDefault();
    setError("");
    if (!form.name.trim() || !form.phone.trim()) {
      setError("Customer name and phone number are required.");
      return;
    }
    addCustomer(form);
    setForm({ name: "", phone: "", email: "", address: "" });
    setCustomerModalOpen(false);
  }

  function handlePaymentSubmit(event) {
    event.preventDefault();
    setError("");
    try {
      recordCustomerPayment(paymentCustomer.id, paymentAmount);
      setPaymentCustomer(null);
      setPaymentAmount("");
    } catch (paymentError) {
      setError(paymentError.message);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Customer accounts"
        title="Customers and credit"
        description="Keep customer details, purchase history and outstanding balances in one place."
        actions={<Button onClick={() => setCustomerModalOpen(true)}><Plus size={18} /> Add customer</Button>}
      />

      <section className="stats-grid stats-grid-three">
        <article className="mini-stat-card"><UserRound size={21} /><div><strong>{customers.length}</strong><span>Customers</span></div></article>
        <article className="mini-stat-card"><CreditCard size={21} /><div><strong>{formatCurrency(totalDebt)}</strong><span>Total outstanding</span></div></article>
        <article className="mini-stat-card"><Phone size={21} /><div><strong>{customers.filter((customer) => customer.outstandingBalance > 0).length}</strong><span>Customers owing</span></div></article>
      </section>

      <section className="panel-card">
        <div className="table-toolbar">
          <label className="table-search"><Search size={18} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search customer name, phone or address..." /></label>
          <span className="result-count">{filtered.length} customer(s)</span>
        </div>

        <div className="customer-card-grid">
          {paginatedCustomers.map((customer) => (
            <article className="customer-card" key={customer.id}>
              <div className="customer-card-top">
                <span className="customer-avatar">{customer.name.slice(0, 2).toUpperCase()}</span>
                <div><strong>{customer.name}</strong><small>{customer.phone}</small></div>
                <button type="button">•••</button>
              </div>
              <div className="customer-card-details">
                <div><span>Outstanding balance</span><strong className={customer.outstandingBalance > 0 ? "danger-text" : "success-text"}>{formatCurrency(customer.outstandingBalance)}</strong></div>
                <div><span>Total purchases</span><strong>{formatCurrency(customer.totalPurchases)}</strong></div>
              </div>
              <p>{customer.address || "No address entered"}</p>
              <small>Customer since {formatDate(customer.createdAt)}</small>
              <div className="customer-card-actions">
                <Button variant="secondary" size="small" onClick={() => navigate(`/app/purchases?customer=${customer.id}`)}>View statement</Button>
                <Button size="small" disabled={!customer.outstandingBalance} onClick={() => { setError(""); setPaymentCustomer(customer); setPaymentAmount(""); }}>Record payment</Button>
              </div>
            </article>
          ))}
        </div>

        <div className="customers-pagination">
          <div className="customers-pagination-summary">
            <span>
              Showing {firstVisibleRecord}-{lastVisibleRecord} of{" "}
              {filtered.length} customers
            </span>

            <label>
              Rows per page
              <select
                value={pageSize}
                onChange={(event) =>
                  setPageSize(Number(event.target.value))
                }
              >
                <option value="10">10</option>
                <option value="20">20</option>
                <option value="50">50</option>
              </select>
            </label>
          </div>

          <div className="customers-pagination-controls">
            <button
              type="button"
              onClick={() =>
                setCurrentPage((page) => Math.max(1, page - 1))
              }
              disabled={safeCurrentPage === 1}
            >
              Previous
            </button>

            <span>
              Page {safeCurrentPage} of {totalPages}
            </span>

            <button
              type="button"
              onClick={() =>
                setCurrentPage((page) =>
                  Math.min(totalPages, page + 1),
                )
              }
              disabled={safeCurrentPage === totalPages}
            >
              Next
            </button>
          </div>
        </div>
      </section>

      <Modal open={customerModalOpen} onClose={() => setCustomerModalOpen(false)} title="Add customer" description="A name and phone number are required for credit sales.">
        {error ? <div className="form-alert form-alert-error">{error}</div> : null}
        <form className="simple-form" onSubmit={handleCustomerSubmit}>
          <label>Customer name<input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} required /></label>
          <label>Phone number<input value={form.phone} onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))} required /></label>
          <label>Email address<input type="email" value={form.email} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} /></label>
          <label>Address<textarea rows="3" value={form.address} onChange={(event) => setForm((current) => ({ ...current, address: event.target.value }))} /></label>
          <div className="modal-form-actions"><Button variant="secondary" onClick={() => setCustomerModalOpen(false)}>Cancel</Button><Button type="submit">Save customer</Button></div>
        </form>
      </Modal>

      <Modal open={Boolean(paymentCustomer)} onClose={() => setPaymentCustomer(null)} title="Record debt payment" description={paymentCustomer ? `${paymentCustomer.name} owes ${formatCurrency(paymentCustomer.outstandingBalance)}.` : ""}>
        {error ? <div className="form-alert form-alert-error">{error}</div> : null}
        <form className="simple-form" onSubmit={handlePaymentSubmit}>
          <label>Amount received (GH₵)<input type="number" min="0.01" max={paymentCustomer?.outstandingBalance || 0} step="0.01" value={paymentAmount} onChange={(event) => setPaymentAmount(event.target.value)} required /></label>
          <label>Payment method<select defaultValue="mobile_money"><option value="cash">Cash</option><option value="mobile_money">Mobile Money</option><option value="bank_transfer">Bank transfer</option></select></label>
          <label>Reference or note<input placeholder="Optional payment reference" /></label>
          <div className="modal-form-actions"><Button variant="secondary" onClick={() => setPaymentCustomer(null)}>Cancel</Button><Button type="submit">Record payment</Button></div>
        </form>
      </Modal>
    </div>
  );
}
