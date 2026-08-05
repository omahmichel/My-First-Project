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
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import PageHeader from "../../components/ui/PageHeader";
import { useStore } from "../../context/StoreContext";
import { formatCurrency } from "../../utils/formatters";

const MOBILE_MONEY_NETWORK_LABELS = {
  mtn: "MTN Mobile Money",
  atl: "AirtelTigo Money",
  vod: "Telecel Cash",
};

function resolvePendingMobileMoneySale(sale) {
  if (!sale || sale.status !== "pending_payment") return null;

  const payment = (sale.payments ?? []).find(
    (record) =>
      record.paymentMethod === "mobile_money" &&
      record.status === "pending" &&
      record.gatewayReference,
  );

  if (!payment) return null;

  return {
    sale,
    payment,
    reference: payment.gatewayReference,
    networkLabel:
      MOBILE_MONEY_NETWORK_LABELS[payment.mobileMoneyNetwork] ??
      payment.mobileMoneyNetwork,
  };
}


export default function NewSalePage() {
  const navigate = useNavigate();
  const {
    products,
    customers,
    inventoryLoading,
    inventoryError,
    customersLoading,
    customersError,
    sales,
    salesLoading,
    salesError,
    completeSale,
    verifyMobileMoneySale,
  } = useStore();

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [cart, setCart] = useState([]);
  const [customerId, setCustomerId] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [amountPaidMethod, setAmountPaidMethod] = useState("cash");
  const [discount, setDiscount] = useState(0);
  const [amountPaid, setAmountPaid] = useState(0);
  const [debtDueDate, setDebtDueDate] = useState("");
  const [error, setError] = useState("");
  const [saleSaving, setSaleSaving] = useState(false);
  const [completedSale, setCompletedSale] = useState(null);
  const [mobileMoneyNetwork, setMobileMoneyNetwork] = useState("");
  const [mobileMoneyNumber, setMobileMoneyNumber] = useState("");
  const [pendingMobileMoneySale, setPendingMobileMoneySale] =
    useState(null);
  const [mobileMoneyModalOpen, setMobileMoneyModalOpen] =
    useState(false);
  const [paymentVerifying, setPaymentVerifying] = useState(false);
  const [paymentStatusMessage, setPaymentStatusMessage] =
    useState("");
  const checkoutKeyRef = useRef(null);

  const customerDebtById = useMemo(() => {
    // Combines customer principal with current invoice overdue charges.
    const totals = new Map(
      customers.map((customer) => [
        String(customer.id),
        Number(customer.outstandingBalance ?? 0),
      ]),
    );

    sales.forEach((sale) => {
      if (!sale.customerId) return;

      const customerKey = String(sale.customerId);
      totals.set(
        customerKey,
        Number(totals.get(customerKey) ?? 0) +
          Number(sale.overdueCharge ?? 0),
      );
    });

    return totals;
  }, [customers, sales]);

  const activeProducts = products.filter(
    (product) =>
      product.status === "active" &&
      Number(product.availableStock ?? product.stock ?? 0) > 0,
  );
  const categories = [
    ...new Set(activeProducts.map((product) => product.category)),
  ].sort();
  const filteredProducts = activeProducts.filter((product) => {
    const query = search.trim().toLowerCase();
    const matchesQuery =
      !query ||
      [
        product.name,
        product.sku,
        product.designCode,
        product.styleCode,
        product.brand,
      ]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(query));

    return matchesQuery &&
      (category === "all" || product.category === category);
  });

  const subtotal = useMemo(
    () =>
      cart.reduce(
        (sum, item) =>
          sum + Number(item.quantity) * Number(item.unitPrice),
        0,
      ),
    [cart],
  );
  const total = Math.max(0, subtotal - (Number(discount) || 0));
  const outstanding = Math.max(
    0,
    total - (Number(amountPaid) || 0),
  );
  const pageLoading =
    inventoryLoading || customersLoading || salesLoading;
  const pageError = inventoryError || customersError || salesError;

  useEffect(() => {
    if (pendingMobileMoneySale) return;

    const pendingRecord = sales
      .map(resolvePendingMobileMoneySale)
      .find(Boolean);

    if (!pendingRecord) return;

    setPendingMobileMoneySale(pendingRecord);
    setPaymentStatusMessage(
      "A previous Mobile Money sale is still waiting for approval.",
    );
  }, [pendingMobileMoneySale, sales]);

  function resetCheckoutKey() {
    checkoutKeyRef.current = null;
  }

  function getCheckoutKey() {
    if (!checkoutKeyRef.current) {
      checkoutKeyRef.current =
        typeof window.crypto?.randomUUID === "function"
          ? window.crypto.randomUUID()
          : `sale-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    return checkoutKeyRef.current;
  }

  function addToCart(product) {
    if (saleSaving) return;

    setError("");
    resetCheckoutKey();
    const availableStock = Number(
      product.availableStock ?? product.stock ?? 0,
    );

    setCart((current) => {
      const existing = current.find(
        (item) => item.productId === product.id,
      );

      if (existing) {
        if (existing.quantity >= availableStock) return current;

        return current.map((item) =>
          item.productId === product.id
            ? { ...item, quantity: item.quantity + 1 }
            : item,
        );
      }

      return [
        ...current,
        {
          productId: product.id,
          name: product.name,
          designCode: product.designCode,
          unit: product.unit,
          quantity: 1,
          unitPrice: Number(product.sellingPrice ?? 0),
          stock: availableStock,
        },
      ];
    });
  }

  function updateQuantity(productId, quantity) {
    if (saleSaving) return;

    resetCheckoutKey();
    setCart((current) =>
      current.map((item) =>
        item.productId === productId
          ? {
              ...item,
              quantity: Math.min(
                item.stock,
                Math.max(1, Number(quantity) || 1),
              ),
            }
          : item,
      ),
    );
  }

  function updatePrice(productId, unitPrice) {
    if (saleSaving) return;

    resetCheckoutKey();
    setCart((current) =>
      current.map((item) =>
        item.productId === productId
          ? {
              ...item,
              unitPrice: Math.max(0, Number(unitPrice) || 0),
            }
          : item,
      ),
    );
  }

  function removeItem(productId) {
    if (saleSaving) return;

    resetCheckoutKey();
    setCart((current) =>
      current.filter((item) => item.productId !== productId),
    );
  }

  function clearCart() {
    if (saleSaving) return;

    resetCheckoutKey();
    setCart([]);
  }

  function choosePaymentMethod(method) {
    if (saleSaving || pendingMobileMoneySale) return;

    resetCheckoutKey();
    setError("");
    setPaymentMethod(method);

    if (method === "credit") {
      setAmountPaid(0);
      setAmountPaidMethod("cash");
    } else {
      setAmountPaid(total);
      setAmountPaidMethod("");
      setDebtDueDate("");
    }

    if (method !== "mobile_money") {
      setMobileMoneyNetwork("");
      setMobileMoneyNumber("");
    }
  }

  async function handleCompleteSale() {
    if (saleSaving) return;

    if (pendingMobileMoneySale) {
      setMobileMoneyModalOpen(true);
      return;
    }

    setError("");
    setSaleSaving(true);

    try {
      const sale = await completeSale({
        cartItems: cart,
        customerId: customerId || null,
        discount,
        amountPaid:
          paymentMethod === "cash" ||
          paymentMethod === "bank_transfer" ||
          paymentMethod === "mobile_money"
            ? total
            : amountPaid,
        paymentMethod,
        amountPaidMethod:
          paymentMethod === "credit" && Number(amountPaid) > 0
            ? amountPaidMethod
            : "",
        debtDueDate:
          paymentMethod === "credit" && outstanding > 0
            ? debtDueDate
            : "",
        mobileMoneyNetwork:
          paymentMethod === "mobile_money"
            ? mobileMoneyNetwork
            : "",
        mobileMoneyNumber:
          paymentMethod === "mobile_money"
            ? mobileMoneyNumber
            : "",
        idempotencyKey: getCheckoutKey(),
      });

      if (sale.status === "pending_payment") {
        const pendingRecord = resolvePendingMobileMoneySale(sale);

        if (!pendingRecord) {
          throw new Error(
            "The Mobile Money prompt started, but its payment reference is missing.",
          );
        }

        setPendingMobileMoneySale(pendingRecord);
        setPaymentStatusMessage(
          "Ask the customer to approve the prompt on their phone, then verify the payment.",
        );
        setMobileMoneyModalOpen(true);
      } else {
        setCompletedSale(sale);
      }

      setCart([]);
      setCustomerId("");
      setPaymentMethod("cash");
      setAmountPaidMethod("cash");
      setDiscount(0);
      setAmountPaid(0);
      setDebtDueDate("");
      setMobileMoneyNetwork("");
      setMobileMoneyNumber("");
      resetCheckoutKey();
    } catch (saleError) {
      setError(saleError.message);
    } finally {
      setSaleSaving(false);
    }
  }

  async function handleVerifyMobileMoneySale() {
    if (!pendingMobileMoneySale || paymentVerifying) return;

    setError("");
    setPaymentStatusMessage("");
    setPaymentVerifying(true);

    try {
      const sale = await verifyMobileMoneySale(
        pendingMobileMoneySale.reference,
      );

      setPendingMobileMoneySale(null);
      setMobileMoneyModalOpen(false);
      setCompletedSale(sale);
    } catch (verificationError) {
      const errorCode = verificationError.data?.code;

      if (errorCode === "mobile_money_payment_pending") {
        setPaymentStatusMessage(
          "Payment is still waiting for approval. Approve the prompt on the customer's phone, then verify again.",
        );
      } else {
        setError(verificationError.message);
        setPaymentStatusMessage(verificationError.message);

        if (
          errorCode === "mobile_money_payment_failed" ||
          errorCode === "mobile_money_sale_not_pending" ||
          errorCode === "mobile_money_reservation_invalid"
        ) {
          setPendingMobileMoneySale(null);
          setMobileMoneyModalOpen(false);
        }
      }
    } finally {
      setPaymentVerifying(false);
    }
  }

  return (
    <div className="page-stack sale-page-stack">
      <PageHeader
        eyebrow="Point of sale"
        title="New sale"
        description="Select products, confirm payment and generate the customer invoice."
      />

      {pageLoading ? (
        <div className="form-alert">
          Loading real products, customers and sales...
        </div>
      ) : null}

      {pageError || error ? (
        <div className="form-alert form-alert-error">
          {error || pageError}
        </div>
      ) : null}

      {pendingMobileMoneySale ? (
        <section className="mobile-money-pending-banner">
          <div>
            <strong>Mobile Money approval pending</strong>
            <span>
              {pendingMobileMoneySale.networkLabel} -{" "}
              {pendingMobileMoneySale.payment.mobileMoneyNumber}
            </span>
            <small>
              Stock is reserved until the payment is verified or expires.
            </small>
          </div>
          <Button
            variant="secondary"
            onClick={() => setMobileMoneyModalOpen(true)}
          >
            Review payment
          </Button>
        </section>
      ) : null}

      <section className="new-sale-layout">
        <div className="sale-product-panel panel-card">
          <div className="sale-product-toolbar">
            <label className="table-search">
              <Search size={18} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search product, SKU or tile design..."
                disabled={saleSaving}
              />
            </label>
            <select
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              disabled={saleSaving}
            >
              <option value="all">All categories</option>
              {categories.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </div>

          <div className="pos-product-grid">
            {filteredProducts.map((product) => (
              <button
                type="button"
                className="pos-product-card"
                key={product.id}
                onClick={() => addToCart(product)}
                disabled={saleSaving}
              >
                <span
                  className={`pos-product-image ${
                    product.imageStyle || "product-generic"
                  }`}
                >
                  {product.designCode ? (
                    <b>{product.designCode}</b>
                  ) : null}
                </span>
                <div>
                  <strong>{product.name}</strong>
                  <span>
                    {product.designCode
                      ? `Design ${product.designCode} · `
                      : ""}
                    {product.availableStock ?? product.stock} {product.unit}(s)
                  </span>
                </div>
                <b>{formatCurrency(product.sellingPrice)}</b>
                <i>
                  <Plus size={17} />
                </i>
              </button>
            ))}
          </div>
        </div>

        <aside className="sale-cart-panel">
          <div className="sale-cart-heading">
            <div>
              <span>Current sale</span>
              <h2>{cart.length} item type(s)</h2>
            </div>
            <button
              type="button"
              onClick={clearCart}
              disabled={!cart.length || saleSaving}
            >
              Clear
            </button>
          </div>

          <div className="sale-customer-select">
            <label>Customer</label>
            <div>
              <select
                value={customerId}
                onChange={(event) => {
                  resetCheckoutKey();
                  setCustomerId(event.target.value);
                }}
                disabled={saleSaving}
              >
                <option value="">Walk-in customer</option>
                {customers.map((customer) => (
                  <option value={customer.id} key={customer.id}>
                    {customer.name} — {formatCurrency(
                      customerDebtById.get(String(customer.id)) ?? 0,
                    )} owed
                  </option>
                ))}
              </select>
              <button
                type="button"
                title="Add customer"
                onClick={() => navigate("/app/customers")}
                disabled={saleSaving}
              >
                <UserPlus size={18} />
              </button>
            </div>
          </div>

          <div className="cart-item-list">
            {!cart.length ? (
              <div className="cart-empty-state">
                <ShoppingBag size={29} />
                <strong>No products selected</strong>
                <span>Select a product from the catalogue to begin.</span>
              </div>
            ) : (
              cart.map((item) => (
                <article className="cart-item" key={item.productId}>
                  <div className="cart-item-heading">
                    <div>
                      <strong>{item.name}</strong>
                      {item.designCode ? (
                        <span>Design {item.designCode}</span>
                      ) : null}
                    </div>
                    <button
                      type="button"
                      onClick={() => removeItem(item.productId)}
                      disabled={saleSaving}
                    >
                      <Trash2 size={17} />
                    </button>
                  </div>
                  <div className="cart-item-controls">
                    <div className="quantity-control">
                      <button
                        type="button"
                        onClick={() =>
                          updateQuantity(
                            item.productId,
                            item.quantity - 1,
                          )
                        }
                        disabled={saleSaving}
                      >
                        <Minus size={15} />
                      </button>
                      <input
                        type="number"
                        min="1"
                        max={item.stock}
                        value={item.quantity}
                        onChange={(event) =>
                          updateQuantity(
                            item.productId,
                            event.target.value,
                          )
                        }
                        disabled={saleSaving}
                      />
                      <button
                        type="button"
                        onClick={() =>
                          updateQuantity(
                            item.productId,
                            item.quantity + 1,
                          )
                        }
                        disabled={saleSaving}
                      >
                        <Plus size={15} />
                      </button>
                    </div>
                    <label>
                      GHS
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={item.unitPrice}
                        onChange={(event) =>
                          updatePrice(
                            item.productId,
                            event.target.value,
                          )
                        }
                        disabled={saleSaving}
                      />
                    </label>
                    <strong>
                      {formatCurrency(item.quantity * item.unitPrice)}
                    </strong>
                  </div>
                </article>
              ))
            )}
          </div>

          <div className="sale-payment-area">
            <div className="sale-totals">
              <div>
                <span>Subtotal</span>
                <strong>{formatCurrency(subtotal)}</strong>
              </div>
              <label>
                <span>Discount</span>
                <div>
                  GHS
                  <input
                    type="number"
                    min="0"
                    max={subtotal}
                    step="0.01"
                    value={discount}
                    onChange={(event) => {
                      resetCheckoutKey();
                      setDiscount(event.target.value);
                    }}
                    disabled={saleSaving}
                  />
                </div>
              </label>
              <div className="sale-grand-total">
                <span>Total</span>
                <strong>{formatCurrency(total)}</strong>
              </div>
            </div>

            <div className="payment-method-grid">
              {[
                ["cash", "Cash"],
                ["mobile_money", "Mobile Money"],
                ["bank_transfer", "Bank transfer"],
                ["credit", "Credit / part payment"],
              ].map(([value, label]) => (
                <button
                  type="button"
                  className={
                    paymentMethod === value
                      ? "payment-method-active"
                      : ""
                  }
                  onClick={() => choosePaymentMethod(value)}
                  key={value}
                  disabled={saleSaving || Boolean(pendingMobileMoneySale)}
                >
                  {label}
                </button>
              ))}
            </div>

            {paymentMethod === "mobile_money" ? (
              <div className="mobile-money-payment-fields">
                <label>
                  Mobile Money network
                  <select
                    value={mobileMoneyNetwork}
                    onChange={(event) => {
                      resetCheckoutKey();
                      setMobileMoneyNetwork(event.target.value);
                    }}
                    disabled={saleSaving}
                  >
                    <option value="">Select network</option>
                    <option value="mtn">MTN Mobile Money</option>
                    <option value="atl">AirtelTigo Money</option>
                    <option value="vod">Telecel Cash</option>
                  </select>
                </label>

                <label>
                  Customer Mobile Money number
                  <input
                    type="tel"
                    inputMode="tel"
                    placeholder="0241234567"
                    value={mobileMoneyNumber}
                    onChange={(event) => {
                      resetCheckoutKey();
                      setMobileMoneyNumber(event.target.value);
                    }}
                    disabled={saleSaving}
                  />
                </label>

                <div className="mobile-money-payment-note">
                  The customer approves the secure Paystack prompt on
                  their phone. Stock is reduced only after backend
                  verification succeeds.
                </div>
              </div>
            ) : null}

            {paymentMethod === "credit" ? (
              <div className="credit-payment-fields">
                <label>
                  Amount paid now
                  <div>
                    GHS
                    <input
                      type="number"
                      min="0"
                      max={total}
                      step="0.01"
                      value={amountPaid}
                      onChange={(event) => {
                        resetCheckoutKey();
                        setAmountPaid(event.target.value);
                      }}
                      disabled={saleSaving}
                    />
                  </div>
                </label>

                {Number(amountPaid) > 0 ? (
                  <label>
                    Initial payment method
                    <select
                      value={amountPaidMethod}
                      onChange={(event) => {
                        resetCheckoutKey();
                        setAmountPaidMethod(event.target.value);
                      }}
                      disabled={saleSaving}
                    >
                      <option value="cash">Cash</option>
                      <option value="bank_transfer">
                        Bank transfer
                      </option>
                    </select>
                  </label>
                ) : null}

                {outstanding > 0 ? (
                  <label>
                    Debt due date
                    <input
                      type="date"
                      value={debtDueDate}
                      min={new Date().toISOString().slice(0, 10)}
                      onChange={(event) => {
                        resetCheckoutKey();
                        setDebtDueDate(event.target.value);
                      }}
                      disabled={saleSaving}
                      required
                    />
                  </label>
                ) : null}

                <div>
                  <span>Outstanding balance</span>
                  <strong>{formatCurrency(outstanding)}</strong>
                </div>
              </div>
            ) : null}

            <Button
              size="large"
              className="full-width-button"
              onClick={handleCompleteSale}
              disabled={
                !cart.length ||
                saleSaving ||
                pageLoading ||
                Boolean(pendingMobileMoneySale)
              }
            >
              {saleSaving
                ? paymentMethod === "mobile_money"
                  ? "Sending Mobile Money prompt..."
                  : "Completing sale..."
                : paymentMethod === "mobile_money"
                  ? "Send Mobile Money prompt"
                  : "Complete sale and invoice"}
              <Check size={18} />
            </Button>
          </div>
        </aside>
      </section>

      <Modal
        open={
          Boolean(pendingMobileMoneySale) && mobileMoneyModalOpen
        }
        onClose={() => {
          if (!paymentVerifying) setMobileMoneyModalOpen(false);
        }}
        title="Mobile Money approval pending"
        description="The sale is not complete until StockFlow verifies Paystack."
      >
        {pendingMobileMoneySale ? (
          <div className="mobile-money-pending-content">
            <div className="mobile-money-pending-icon">
              <ShoppingBag size={28} />
            </div>

            <strong>
              {formatCurrency(pendingMobileMoneySale.sale.total)}
            </strong>
            <span>{pendingMobileMoneySale.networkLabel}</span>
            <small>
              {pendingMobileMoneySale.payment.mobileMoneyNumber}
            </small>

            <div className="mobile-money-pending-details">
              <div>
                <span>Payment reference</span>
                <strong>{pendingMobileMoneySale.reference}</strong>
              </div>
              <div>
                <span>Reservation expires</span>
                <strong>
                  {pendingMobileMoneySale.sale.reservationExpiresAt
                    ? new Date(
                        pendingMobileMoneySale.sale.reservationExpiresAt,
                      ).toLocaleString()
                    : "Pending verification"}
                </strong>
              </div>
            </div>

            {paymentStatusMessage ? (
              <div className="form-alert">
                {paymentStatusMessage}
              </div>
            ) : null}

            <div className="success-action-grid">
              <Button
                variant="secondary"
                onClick={() => setMobileMoneyModalOpen(false)}
                disabled={paymentVerifying}
              >
                Close for now
              </Button>
              <Button
                onClick={handleVerifyMobileMoneySale}
                disabled={paymentVerifying}
              >
                {paymentVerifying
                  ? "Verifying payment..."
                  : "Verify payment"}
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={Boolean(completedSale)}
        onClose={() => setCompletedSale(null)}
        title="Sale completed"
        description="Stock has been reduced and the invoice has been generated."
      >
        {completedSale ? (
          <div className="sale-success-content">
            <div className="success-icon">
              <Check size={28} />
            </div>
            <strong>{completedSale.invoiceNumber}</strong>
            <span>{completedSale.customerName}</span>
            <div className="success-total">
              <span>Invoice total</span>
              <strong>{formatCurrency(completedSale.total)}</strong>
            </div>
            {completedSale.latestReceiptNumber ? (
              <small>
                Receipt: {completedSale.latestReceiptNumber}
              </small>
            ) : null}
            <div className="success-action-grid">
              <Button
                variant="secondary"
                onClick={() => window.print()}
              >
                <Printer size={18} />
                Print
              </Button>
              <Button onClick={() => setCompletedSale(null)}>
                Done
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
