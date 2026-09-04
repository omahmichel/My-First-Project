import {
  CheckCircle2,
  CircleDollarSign,
  Edit3,
  LoaderCircle,
  PackagePlus,
  Plus,
  Search,
  Truck,
  UserPlus,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

import PageHeader from "../../components/ui/PageHeader";
import { useStore } from "../../context/StoreContext";
import { apiRequest } from "../../services/api";
import { formatCurrency } from "../../utils/formatters";
import "../../styles/restocking.css";

const METHODS = [
  ["cash", "Cash"],
  ["mobile_money", "Mobile Money"],
  ["bank_transfer", "Bank transfer"],
];

const blankSupplier = () => ({
  name: "", phone: "", email: "", address: "", notes: "",
});

const blankRestock = () => ({
  supplierId: "",
  supplierReference: "",
  purchaseDate: new Date().toISOString().slice(0, 10),
  initialPayment: "",
  paymentMethod: "cash",
  items: [{ productId: "", quantity: "1", unitCost: "" }],
});

function dateLabel(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-GH", {
    day: "numeric", month: "short", year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function RestockModalPortal({ children }) {
  if (typeof document === "undefined") return null;
  return createPortal(children, document.body);
}

export default function RestockingPage() {
  const { business, products, loadInventory } = useStore();
  const [suppliers, setSuppliers] = useState([]);
  const [restocks, setRestocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState(null);
  const [search, setSearch] = useState("");
  const [supplierOpen, setSupplierOpen] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState(null);
  const [supplierForm, setSupplierForm] = useState(blankSupplier());
  const [supplierSaving, setSupplierSaving] = useState(false);
  const [restockOpen, setRestockOpen] = useState(false);
  const [restockForm, setRestockForm] = useState(blankRestock());
  const [restockSaving, setRestockSaving] = useState(false);
  const [paymentPurchase, setPaymentPurchase] = useState(null);
  const [payment, setPayment] = useState({
    amount: "", method: "cash", note: "",
  });
  const [paymentSaving, setPaymentSaving] = useState(false);

  const activeProducts = products.filter((p) => p.status === "active");
  const activeSuppliers = suppliers.filter((s) => s.isActive);

  async function loadData() {
    if (!business.id) return;
    setLoading(true);
    try {
      const [supplierData, restockData] = await Promise.all([
        apiRequest(`/businesses/${business.id}/suppliers/`),
        apiRequest(`/businesses/${business.id}/restocks/`),
      ]);
      setSuppliers(Array.isArray(supplierData) ? supplierData : []);
      setRestocks(Array.isArray(restockData) ? restockData : []);
    } catch (error) {
      setNotice({ tone: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (business.id && business.hasSystemAccess) loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [business.id, business.hasSystemAccess]);

  const totals = useMemo(() => {
    const purchased = restocks.reduce(
      (sum, row) => sum + Number(row.totalAmount || 0), 0
    );
    const paid = restocks.reduce(
      (sum, row) => sum + Number(row.amountPaid || 0), 0
    );
    return {
      purchased,
      paid,
      outstanding: Math.max(0, purchased - paid),
    };
  }, [restocks]);

  const visibleRestocks = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return restocks;
    return restocks.filter((row) =>
      [row.purchaseNumber, row.supplierName, row.supplierReference]
        .some((value) => String(value || "").toLowerCase().includes(q))
    );
  }, [restocks, search]);

  function openSupplier(supplier = null) {
    setEditingSupplier(supplier);
    setSupplierForm(
      supplier
        ? {
            name: supplier.name || "",
            phone: supplier.phone || "",
            email: supplier.email || "",
            address: supplier.address || "",
            notes: supplier.notes || "",
          }
        : blankSupplier()
    );
    setSupplierOpen(true);
  }

  async function saveSupplier(event) {
    event.preventDefault();
    setSupplierSaving(true);
    try {
      const response = await apiRequest(
        editingSupplier
          ? `/businesses/${business.id}/suppliers/${editingSupplier.id}/`
          : `/businesses/${business.id}/suppliers/`,
        {
          method: editingSupplier ? "PATCH" : "POST",
          body: JSON.stringify(supplierForm),
        },
      );
      setSupplierOpen(false);
      await loadData();
      setNotice({
        tone: "success",
        text: editingSupplier
          ? `${response.name} was updated.`
          : `${response.name} was added.`,
      });
    } catch (error) {
      setNotice({ tone: "error", text: error.message });
    } finally {
      setSupplierSaving(false);
    }
  }

  async function toggleSupplier(supplier) {
    try {
      await apiRequest(
        `/businesses/${business.id}/suppliers/${supplier.id}/`,
        supplier.isActive
          ? { method: "DELETE" }
          : {
              method: "PATCH",
              body: JSON.stringify({ isActive: true }),
            },
      );
      await loadData();
    } catch (error) {
      setNotice({ tone: "error", text: error.message });
    }
  }

  function changeLine(index, field, value) {
    setRestockForm((current) => ({
      ...current,
      items: current.items.map((line, i) => {
        if (i !== index) return line;
        const next = { ...line, [field]: value };
        if (field === "productId") {
          const product = activeProducts.find((p) => p.id === value);
          next.unitCost = product ? String(product.costPrice || 0) : "";
        }
        return next;
      }),
    }));
  }

  const restockTotal = restockForm.items.reduce(
    (sum, line) =>
      sum + Number(line.quantity || 0) * Number(line.unitCost || 0),
    0,
  );

  async function saveRestock(event) {
    event.preventDefault();
    setRestockSaving(true);
    try {
      const response = await apiRequest(
        `/businesses/${business.id}/restocks/`,
        {
          method: "POST",
          body: JSON.stringify({
            ...restockForm,
            initialPayment: Number(restockForm.initialPayment || 0),
            items: restockForm.items.map((line) => ({
              productId: line.productId,
              quantity: Number(line.quantity),
              unitCost: Number(line.unitCost),
            })),
          }),
        },
      );
      setRestockOpen(false);
      setRestockForm(blankRestock());
      await Promise.all([loadData(), loadInventory(business.id)]);
      setNotice({
        tone: "success",
        text: `${response.purchaseNumber} saved and inventory updated.`,
      });
    } catch (error) {
      setNotice({ tone: "error", text: error.message });
    } finally {
      setRestockSaving(false);
    }
  }

  async function savePayment(event) {
    event.preventDefault();
    setPaymentSaving(true);
    try {
      await apiRequest(
        `/businesses/${business.id}/restocks/${paymentPurchase.id}/payments/`,
        {
          method: "POST",
          body: JSON.stringify({
            amount: Number(payment.amount),
            method: payment.method,
            note: payment.note,
          }),
        },
      );
      setPaymentPurchase(null);
      await loadData();
      setNotice({ tone: "success", text: "Supplier payment recorded." });
    } catch (error) {
      setNotice({ tone: "error", text: error.message });
    } finally {
      setPaymentSaving(false);
    }
  }

  return (
    <div className="page-stack restock-page">
      <PageHeader
        eyebrow="Supply & inventory"
        title="Suppliers & restocking"
        description="Record stock received, supplier purchases and outstanding balances."
      />

      <div className="restock-actions">
        <button className="restock-btn secondary" onClick={() => openSupplier()}>
          <UserPlus size={17} /> Add supplier
        </button>
        <button
          className="restock-btn primary"
          onClick={() => setRestockOpen(true)}
          disabled={!activeSuppliers.length || !activeProducts.length}
        >
          <PackagePlus size={17} /> Record restock
        </button>
      </div>

      {notice && (
        <div className={`restock-notice ${notice.tone}`}>
          {notice.tone === "success"
            ? <CheckCircle2 size={18} />
            : <X size={18} />}
          {notice.text}
        </div>
      )}

      <section className="restock-metrics">
        <article><Truck /><span>Active suppliers</span><strong>{activeSuppliers.length}</strong></article>
        <article><PackagePlus /><span>Total restocked</span><strong>{formatCurrency(totals.purchased)}</strong></article>
        <article><CircleDollarSign /><span>Amount paid</span><strong>{formatCurrency(totals.paid)}</strong></article>
        <article><CircleDollarSign /><span>Supplier balance</span><strong>{formatCurrency(totals.outstanding)}</strong></article>
      </section>

      <section className="panel-card restock-panel">
        <div className="restock-panel-head">
          <div><span>Purchase history</span><h2>Restocking records</h2></div>
          <label className="restock-search">
            <Search size={16} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search supplier or reference..."
            />
          </label>
        </div>
        <div className="restock-table-wrap">
          <table className="data-table restock-table">
            <thead><tr>
              <th>Restock</th><th>Supplier</th><th>Items</th>
              <th>Total</th><th>Paid</th><th>Balance</th><th>Status</th><th />
            </tr></thead>
            <tbody>
              {!loading && !visibleRestocks.length && (
                <tr><td colSpan="8" className="restock-empty">No restocking records yet.</td></tr>
              )}
              {visibleRestocks.map((row) => (
                <tr key={row.id}>
                  <td><strong>{row.purchaseNumber}</strong><small>{dateLabel(row.purchaseDate)}</small></td>
                  <td><strong>{row.supplierName}</strong><small>{row.supplierReference || "No supplier reference"}</small></td>
                  <td>{row.items?.length || 0}</td>
                  <td>{formatCurrency(row.totalAmount)}</td>
                  <td>{formatCurrency(row.amountPaid)}</td>
                  <td><strong>{formatCurrency(row.outstandingBalance)}</strong></td>
                  <td><span className={`restock-status ${row.paymentStatus}`}>{row.paymentStatus === "partial" ? "Partially paid" : row.paymentStatus}</span></td>
                  <td>
                    {Number(row.outstandingBalance || 0) > 0 && (
                      <button className="restock-link" onClick={() => {
                        setPaymentPurchase(row);
                        setPayment({
                          amount: String(row.outstandingBalance),
                          method: "cash",
                          note: "",
                        });
                      }}>Record payment</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {loading && <div className="restock-loading"><LoaderCircle /> Loading...</div>}
      </section>

      <section className="panel-card restock-panel">
        <div className="restock-panel-head">
          <div><span>Supply network</span><h2>Suppliers</h2></div>
        </div>
        <div className="supplier-grid">
          {suppliers.map((supplier) => (
            <article key={supplier.id} className={!supplier.isActive ? "inactive" : ""}>
              <div className="supplier-title">
                <div><strong>{supplier.name}</strong><span>{supplier.phone || supplier.email || "No contact details"}</span></div>
                <span className={`restock-status ${supplier.isActive ? "paid" : "neutral"}`}>{supplier.isActive ? "Active" : "Inactive"}</span>
              </div>
              <div className="supplier-stats">
                <div><span>Purchases</span><strong>{supplier.purchaseCount}</strong></div>
                <div><span>Purchased</span><strong>{formatCurrency(supplier.totalPurchased)}</strong></div>
                <div><span>Outstanding</span><strong>{formatCurrency(supplier.outstandingBalance)}</strong></div>
              </div>
              <div className="supplier-actions">
                <button onClick={() => openSupplier(supplier)}><Edit3 size={14} /> Edit</button>
                <button onClick={() => toggleSupplier(supplier)}>{supplier.isActive ? "Deactivate" : "Reactivate"}</button>
              </div>
            </article>
          ))}
          {!loading && !suppliers.length && <div className="restock-empty supplier-empty">Add your first supplier to begin recording restocks.</div>}
        </div>
      </section>

      {supplierOpen && (
        <RestockModalPortal>
          <div className="restock-backdrop">
          <div className="restock-modal">
            <div className="restock-modal-head">
              <div><span>Supplier profile</span><h2>{editingSupplier ? "Edit supplier" : "Add supplier"}</h2></div>
              <button onClick={() => setSupplierOpen(false)}><X /></button>
            </div>
            <form onSubmit={saveSupplier} className="restock-form">
              <label className="wide"><span>Supplier name *</span><input required value={supplierForm.name} onChange={(e) => setSupplierForm({...supplierForm, name:e.target.value})} /></label>
              <label><span>Phone</span><input value={supplierForm.phone} onChange={(e) => setSupplierForm({...supplierForm, phone:e.target.value})} /></label>
              <label><span>Email</span><input type="email" value={supplierForm.email} onChange={(e) => setSupplierForm({...supplierForm, email:e.target.value})} /></label>
              <label className="wide"><span>Address</span><input value={supplierForm.address} onChange={(e) => setSupplierForm({...supplierForm, address:e.target.value})} /></label>
              <label className="wide"><span>Notes</span><textarea rows="3" value={supplierForm.notes} onChange={(e) => setSupplierForm({...supplierForm, notes:e.target.value})} /></label>
              <div className="restock-modal-actions wide">
                <button type="button" className="restock-btn secondary" onClick={() => setSupplierOpen(false)}>Cancel</button>
                <button className="restock-btn primary" disabled={supplierSaving}>{supplierSaving ? "Saving..." : "Save supplier"}</button>
              </div>
            </form>
          </div>
          </div>
        </RestockModalPortal>
      )}

      {restockOpen && (
        <RestockModalPortal>
          <div className="restock-backdrop">
          <div className="restock-modal large">
            <div className="restock-modal-head">
              <div><span>Inventory receipt</span><h2>Record new restock</h2></div>
              <button onClick={() => setRestockOpen(false)}><X /></button>
            </div>
            <form onSubmit={saveRestock} className="restock-form">
              <label><span>Supplier *</span><select required value={restockForm.supplierId} onChange={(e) => setRestockForm({...restockForm, supplierId:e.target.value})}><option value="">Select supplier</option>{activeSuppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
              <label><span>Purchase date</span><input type="date" value={restockForm.purchaseDate} onChange={(e) => setRestockForm({...restockForm, purchaseDate:e.target.value})} /></label>
              <label className="wide"><span>Supplier invoice/reference</span><input value={restockForm.supplierReference} onChange={(e) => setRestockForm({...restockForm, supplierReference:e.target.value})} /></label>

              <div className="restock-lines wide">
                <div className="restock-lines-head"><strong>Products received</strong><button type="button" onClick={() => setRestockForm({...restockForm, items:[...restockForm.items,{productId:"",quantity:"1",unitCost:""}]})}><Plus size={15} /> Add product</button></div>
                {restockForm.items.map((line, index) => (
                  <div className="restock-line" key={index}>
                    <label><span>Product</span><select required value={line.productId} onChange={(e) => changeLine(index,"productId",e.target.value)}><option value="">Select product</option>{activeProducts.map((p) => <option key={p.id} value={p.id} disabled={restockForm.items.some((other,i) => i !== index && other.productId === p.id)}>{p.name} · {p.sku}</option>)}</select></label>
                    <label><span>Quantity</span><input type="number" min="1" required value={line.quantity} onChange={(e) => changeLine(index,"quantity",e.target.value)} /></label>
                    <label><span>Unit cost (GH₵)</span><input type="number" min="0" step="0.01" required value={line.unitCost} onChange={(e) => changeLine(index,"unitCost",e.target.value)} /></label>
                    <div className="line-total"><span>Line total</span><strong>{formatCurrency(Number(line.quantity||0)*Number(line.unitCost||0))}</strong></div>
                    <button type="button" className="remove-line" disabled={restockForm.items.length === 1} onClick={() => setRestockForm({...restockForm, items:restockForm.items.filter((_,i)=>i!==index)})}><X size={16} /></button>
                  </div>
                ))}
              </div>

              <div className="restock-total wide"><span>Restock total</span><strong>{formatCurrency(restockTotal)}</strong><small>Inventory and weighted cost update only after the complete transaction saves.</small></div>
              <label><span>Amount paid now</span><input type="number" min="0" step="0.01" max={restockTotal || undefined} value={restockForm.initialPayment} onChange={(e) => setRestockForm({...restockForm, initialPayment:e.target.value})} placeholder="0.00" /></label>
              <label><span>Payment method</span><select value={restockForm.paymentMethod} onChange={(e) => setRestockForm({...restockForm, paymentMethod:e.target.value})}>{METHODS.map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label>

              <div className="restock-modal-actions wide">
                <button type="button" className="restock-btn secondary" onClick={() => setRestockOpen(false)}>Cancel</button>
                <button className="restock-btn primary" disabled={restockSaving}>{restockSaving ? "Recording..." : "Record restock"}</button>
              </div>
            </form>
          </div>
          </div>
        </RestockModalPortal>
      )}

      {paymentPurchase && (
        <RestockModalPortal>
          <div className="restock-backdrop">
          <div className="restock-modal">
            <div className="restock-modal-head">
              <div><span>Supplier payment</span><h2>Record payment</h2></div>
              <button onClick={() => setPaymentPurchase(null)}><X /></button>
            </div>
            <div className="payment-summary">
              <strong>{paymentPurchase.supplierName}</strong>
              <span>Outstanding {formatCurrency(paymentPurchase.outstandingBalance)}</span>
            </div>
            <form onSubmit={savePayment} className="restock-form">
              <label><span>Amount *</span><input required type="number" min="0.01" step="0.01" max={paymentPurchase.outstandingBalance} value={payment.amount} onChange={(e) => setPayment({...payment, amount:e.target.value})} /></label>
              <label><span>Method</span><select value={payment.method} onChange={(e) => setPayment({...payment, method:e.target.value})}>{METHODS.map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label>
              <label className="wide"><span>Note</span><input value={payment.note} onChange={(e) => setPayment({...payment, note:e.target.value})} /></label>
              <div className="restock-modal-actions wide">
                <button type="button" className="restock-btn secondary" onClick={() => setPaymentPurchase(null)}>Cancel</button>
                <button className="restock-btn primary" disabled={paymentSaving}>{paymentSaving ? "Recording..." : "Record payment"}</button>
              </div>
            </form>
          </div>
          </div>
        </RestockModalPortal>
      )}
    </div>
  );
}
