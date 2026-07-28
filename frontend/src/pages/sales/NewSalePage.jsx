import {
  Check,
  Minus,
  Plus,
  Printer,
  Search,
  ShoppingBag,
  Trash2,
  UserPlus,
} from "lucide-react";
import { useMemo, useState } from "react";

import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import PageHeader from "../../components/ui/PageHeader";
import { useStore } from "../../context/StoreContext";
import { formatCurrency } from "../../utils/formatters";

export default function NewSalePage() {
  const { products, customers, completeSale } = useStore();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [cart, setCart] = useState([]);
  const [customerId, setCustomerId] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [discount, setDiscount] = useState(0);
  const [amountPaid, setAmountPaid] = useState(0);
  const [error, setError] = useState("");
  const [completedSale, setCompletedSale] = useState(null);

  const activeProducts = products.filter((product) => product.status === "active" && product.stock > 0);
  const categories = [...new Set(activeProducts.map((product) => product.category))].sort();
  const filteredProducts = activeProducts.filter((product) => {
    const query = search.trim().toLowerCase();
    const matchesQuery = !query || [product.name, product.sku, product.designCode, product.styleCode, product.brand]
      .filter(Boolean)
      .some((value) => value.toLowerCase().includes(query));
    return matchesQuery && (category === "all" || product.category === category);
  });

  const subtotal = useMemo(() => cart.reduce((sum, item) => sum + item.quantity * item.unitPrice, 0), [cart]);
  const total = Math.max(0, subtotal - (Number(discount) || 0));
  const outstanding = Math.max(0, total - (Number(amountPaid) || 0));

  function addToCart(product) {
    setError("");
    setCart((current) => {
      const existing = current.find((item) => item.productId === product.id);
      if (existing) {
        if (existing.quantity >= product.stock) return current;
        return current.map((item) => item.productId === product.id ? { ...item, quantity: item.quantity + 1 } : item);
      }
      return [...current, { productId: product.id, name: product.name, designCode: product.designCode, unit: product.unit, quantity: 1, unitPrice: product.sellingPrice, stock: product.stock }];
    });
  }

  function updateQuantity(productId, quantity) {
    setCart((current) => current.map((item) => item.productId === productId ? { ...item, quantity: Math.min(item.stock, Math.max(1, Number(quantity) || 1)) } : item));
  }

  function updatePrice(productId, unitPrice) {
    setCart((current) => current.map((item) => item.productId === productId ? { ...item, unitPrice: Math.max(0, Number(unitPrice) || 0) } : item));
  }

  function removeItem(productId) {
    setCart((current) => current.filter((item) => item.productId !== productId));
  }

  function choosePaymentMethod(method) {
    setPaymentMethod(method);
    if (method !== "credit") setAmountPaid(total);
    else setAmountPaid(0);
  }

  function handleCompleteSale() {
    setError("");
    try {
      const sale = completeSale({
        cartItems: cart,
        customerId: customerId || null,
        discount,
        amountPaid: paymentMethod === "cash" || paymentMethod === "mobile_money" || paymentMethod === "bank_transfer" ? total : amountPaid,
        paymentMethod,
      });
      setCompletedSale(sale);
      setCart([]);
      setCustomerId("");
      setPaymentMethod("cash");
      setDiscount(0);
      setAmountPaid(0);
    } catch (saleError) {
      setError(saleError.message);
    }
  }

  return (
    <div className="page-stack sale-page-stack">
      <PageHeader eyebrow="Point of sale" title="New sale" description="Select products, confirm payment and generate the customer invoice." />

      {error ? <div className="form-alert form-alert-error">{error}</div> : null}

      <section className="new-sale-layout">
        <div className="sale-product-panel panel-card">
          <div className="sale-product-toolbar">
            <label className="table-search"><Search size={18} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search product, SKU or tile design..." /></label>
            <select value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">All categories</option>{categories.map((item) => <option key={item}>{item}</option>)}</select>
          </div>

          <div className="pos-product-grid">
            {filteredProducts.map((product) => (
              <button type="button" className="pos-product-card" key={product.id} onClick={() => addToCart(product)}>
                <span className={`pos-product-image ${product.imageStyle || "product-generic"}`}>
                  {product.designCode ? <b>{product.designCode}</b> : null}
                </span>
                <div><strong>{product.name}</strong><span>{product.designCode ? `Design ${product.designCode} · ` : ""}{product.stock} {product.unit}(s)</span></div>
                <b>{formatCurrency(product.sellingPrice)}</b>
                <i><Plus size={17} /></i>
              </button>
            ))}
          </div>
        </div>

        <aside className="sale-cart-panel">
          <div className="sale-cart-heading">
            <div><span>Current sale</span><h2>{cart.length} item type(s)</h2></div>
            <button type="button" onClick={() => setCart([])} disabled={!cart.length}>Clear</button>
          </div>

          <div className="sale-customer-select">
            <label>Customer</label>
            <div><select value={customerId} onChange={(event) => setCustomerId(event.target.value)}><option value="">Walk-in customer</option>{customers.map((customer) => <option value={customer.id} key={customer.id}>{customer.name} — {formatCurrency(customer.outstandingBalance)} owed</option>)}</select><button type="button" title="Add customer"><UserPlus size={18} /></button></div>
          </div>

          <div className="cart-item-list">
            {!cart.length ? (
              <div className="cart-empty-state"><ShoppingBag size={29} /><strong>No products selected</strong><span>Select a product from the catalogue to begin.</span></div>
            ) : cart.map((item) => (
              <article className="cart-item" key={item.productId}>
                <div className="cart-item-heading"><div><strong>{item.name}</strong>{item.designCode ? <span>Design {item.designCode}</span> : null}</div><button type="button" onClick={() => removeItem(item.productId)}><Trash2 size={17} /></button></div>
                <div className="cart-item-controls">
                  <div className="quantity-control"><button type="button" onClick={() => updateQuantity(item.productId, item.quantity - 1)}><Minus size={15} /></button><input type="number" min="1" max={item.stock} value={item.quantity} onChange={(event) => updateQuantity(item.productId, event.target.value)} /><button type="button" onClick={() => updateQuantity(item.productId, item.quantity + 1)}><Plus size={15} /></button></div>
                  <label>GH₵<input type="number" min="0" step="0.01" value={item.unitPrice} onChange={(event) => updatePrice(item.productId, event.target.value)} /></label>
                  <strong>{formatCurrency(item.quantity * item.unitPrice)}</strong>
                </div>
              </article>
            ))}
          </div>

          <div className="sale-payment-area">
            <div className="sale-totals">
              <div><span>Subtotal</span><strong>{formatCurrency(subtotal)}</strong></div>
              <label><span>Discount</span><div>GH₵<input type="number" min="0" max={subtotal} step="0.01" value={discount} onChange={(event) => setDiscount(event.target.value)} /></div></label>
              <div className="sale-grand-total"><span>Total</span><strong>{formatCurrency(total)}</strong></div>
            </div>

            <div className="payment-method-grid">
              {[["cash", "Cash"], ["mobile_money", "Mobile Money"], ["bank_transfer", "Bank transfer"], ["credit", "Credit / part payment"]].map(([value, label]) => (
                <button type="button" className={paymentMethod === value ? "payment-method-active" : ""} onClick={() => choosePaymentMethod(value)} key={value}>{label}</button>
              ))}
            </div>

            {paymentMethod === "credit" ? (
              <div className="credit-payment-fields">
                <label>Amount paid now<div>GH₵<input type="number" min="0" max={total} step="0.01" value={amountPaid} onChange={(event) => setAmountPaid(event.target.value)} /></div></label>
                <div><span>Outstanding balance</span><strong>{formatCurrency(outstanding)}</strong></div>
              </div>
            ) : null}

            <Button size="large" className="full-width-button" onClick={handleCompleteSale} disabled={!cart.length}>Complete sale and invoice <Check size={18} /></Button>
          </div>
        </aside>
      </section>

      <Modal open={Boolean(completedSale)} onClose={() => setCompletedSale(null)} title="Sale completed" description="Stock has been reduced and the invoice has been generated.">
        {completedSale ? (
          <div className="sale-success-content">
            <div className="success-icon"><Check size={28} /></div>
            <strong>{completedSale.invoiceNumber}</strong>
            <span>{completedSale.customerName}</span>
            <div className="success-total"><span>Invoice total</span><strong>{formatCurrency(completedSale.total)}</strong></div>
            <div className="success-action-grid"><Button variant="secondary" onClick={() => window.print()}><Printer size={18} /> Print</Button><Button onClick={() => setCompletedSale(null)}>Done</Button></div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
