import {
  Download,
  Eye,
  FileText,
  PackageCheck,
  ReceiptText,
  Save,
  Search,
  Share2,
  Truck,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import StickyTableScroll from "../../components/ui/StickyTableScroll";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import PageHeader from "../../components/ui/PageHeader";
import { useStore } from "../../context/StoreContext";
import {
  downloadInvoicePdf,
  downloadReceiptPdf,
  downloadWaybillPdf,
  exportCustomerStatementPdf,
  shareCustomerStatement,
} from "../../utils/invoiceDocuments";
import { formatCurrency, formatDate } from "../../utils/formatters";

import "../../styles/customer-purchase-records.css";

// Displays invoices, receipts and delivery-document status for every sale.
export default function CustomerPurchaseRecordsPage() {
  const {
    sales,
    payments,
    customers,
    business,
    saveWaybill,
  } = useStore();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [selectedSale, setSelectedSale] = useState(null);
  const [waybillSale, setWaybillSale] = useState(null);
  const [waybillForm, setWaybillForm] = useState({
    recipientName: "",
    recipientPhone: "",
    deliveryAddress: "",
    dispatchDate: "",
    driverName: "",
    vehicleNumber: "",
    deliveryNotes: "",
    status: "pending",
  });
  const [message, setMessage] = useState("");
  const [sharingStatement, setSharingStatement] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const selectedCustomerId = searchParams.get("customer") || "all";

  // Resolves the customer whose transactions will appear in one statement PDF.
  const selectedCustomer = useMemo(
    () =>
      customers.find((customer) => customer.id === selectedCustomerId) ?? null,
    [customers, selectedCustomerId],
  );

  const receiptsBySaleId = useMemo(() => {
    const groupedReceipts = new Map();

    payments.forEach((payment) => {
      const current = groupedReceipts.get(payment.saleId) || [];
      groupedReceipts.set(payment.saleId, [...current, payment]);
    });

    return groupedReceipts;
  }, [payments]);

  const filteredSales = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();

    return sales.filter((sale) => {
      const matchesCustomer =
        selectedCustomerId === "all" ||
        (selectedCustomerId === "walk_in"
          ? !sale.customerId
          : sale.customerId === selectedCustomerId);

      if (!matchesCustomer) return false;
      if (!normalizedSearch) return true;

      return [
        sale.saleNumber,
        sale.invoiceNumber,
        sale.customerName,
        ...(sale.items || []).map((item) => item.name),
      ]
        .filter(Boolean)
        .some((value) =>
          String(value).toLowerCase().includes(normalizedSearch),
        );
    });
  }, [sales, search, selectedCustomerId]);

  const totals = useMemo(
    () =>
      filteredSales.reduce(
        (summary, sale) => ({
          purchases: summary.purchases + Number(sale.total || 0),
          paid: summary.paid + Number(sale.amountPaid || 0),
          balance:
            summary.balance + Number(sale.outstandingBalance || 0),
        }),
        { purchases: 0, paid: 0, balance: 0 },
      ),
    [filteredSales],
  );

  const totalPages = Math.max(
    1,
    Math.ceil(filteredSales.length / pageSize),
  );

  const safeCurrentPage = Math.min(currentPage, totalPages);

  const paginatedSales = useMemo(() => {
    const startIndex = (safeCurrentPage - 1) * pageSize;

    return filteredSales.slice(startIndex, startIndex + pageSize);
  }, [filteredSales, pageSize, safeCurrentPage]);

  const firstVisibleRecord = filteredSales.length
    ? (safeCurrentPage - 1) * pageSize + 1
    : 0;
  const lastVisibleRecord = filteredSales.length
    ? firstVisibleRecord + paginatedSales.length - 1
    : 0;

  // Returns to the first page whenever the active filter changes.
  useEffect(() => {
    setCurrentPage(1);
  }, [search, selectedCustomerId, pageSize]);

  // Prevents the current page from exceeding the available page count.
  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  function chooseCustomer(event) {
    const customerId = event.target.value;
    const nextParams = new URLSearchParams(searchParams);

    if (customerId === "all") {
      nextParams.delete("customer");
    } else {
      nextParams.set("customer", customerId);
    }

    setSearchParams(nextParams);
  }

  function handleInvoiceDownload(sale) {
    setMessage("");

    try {
      const filename = downloadInvoicePdf(sale, business);
      setMessage(`${filename} downloaded successfully.`);
    } catch (error) {
      setMessage(error.message);
    }
  }

  function handleReceiptDownload(receipt, sale) {
    setMessage("");

    try {
      const filename = downloadReceiptPdf(receipt, sale, business);
      setMessage(`${filename} downloaded successfully.`);
    } catch (error) {
      setMessage(error.message);
    }
  }

  function openWaybillForm(sale) {
    const customer = customers.find(
      (item) => item.id === sale.customerId,
    );

    setMessage("");
    setWaybillSale(sale);
    setWaybillForm({
      recipientName:
        sale.waybill?.recipientName || sale.customerName || "",
      recipientPhone:
        sale.waybill?.recipientPhone || customer?.phone || "",
      deliveryAddress:
        sale.waybill?.deliveryAddress || customer?.address || "",
      dispatchDate:
        sale.waybill?.dispatchDate ||
        new Date().toISOString().slice(0, 10),
      driverName: sale.waybill?.driverName || "",
      vehicleNumber: sale.waybill?.vehicleNumber || "",
      deliveryNotes: sale.waybill?.deliveryNotes || "",
      status: sale.waybill?.status || "pending",
    });
  }

  async function handleWaybillSubmit(event) {
    event.preventDefault();
    setMessage("");

    try {
      const waybill = await saveWaybill(
        waybillSale.id,
        waybillForm,
      );

      setSelectedSale((current) =>
        String(current?.id) === String(waybillSale.id)
          ? { ...current, waybill }
          : current,
      );
      setWaybillSale(null);
      setMessage(`${waybill.waybillNumber} saved successfully.`);
    } catch (error) {
      setMessage(error.message);
    }
  }

  function handleWaybillDownload(sale) {
    setMessage("");

    try {
      const filename = downloadWaybillPdf(sale, business);
      setMessage(`${filename} downloaded successfully.`);
    } catch (error) {
      setMessage(error.message);
    }
  }

  function handleStatementDownload() {
    setMessage("");

    if (!selectedCustomer) {
      setMessage("Select a named customer before downloading a statement.");
      return;
    }

    try {
      const filename = exportCustomerStatementPdf(
        selectedCustomer,
        filteredSales,
        payments,
        business,
      );
      setMessage(`${filename} downloaded successfully.`);
    } catch (error) {
      setMessage(error.message);
    }
  }


  async function handleStatementShare() {
    setMessage("");

    if (!selectedCustomer) {
      setMessage(
        "Select a named customer before sharing a statement.",
      );
      return;
    }

    setSharingStatement(true);

    try {
      const result = await shareCustomerStatement(
        selectedCustomer,
        filteredSales,
        payments,
        business,
      );

      setMessage(result);
    } catch (error) {
      if (error?.name === "AbortError") {
        setMessage("Sharing was cancelled.");
      } else {
        setMessage(
          error.message ||
            "The customer statement could not be shared.",
        );
      }
    } finally {
      setSharingStatement(false);
    }
  }

  return (
    <div className="page-stack purchase-records-page">
      <PageHeader
        eyebrow="Customer documents"
        title="Purchase records"
        description="Review every customer purchase together with its invoice, receipts and waybill status."
        actions={
          <div className="purchase-statement-actions">
            <Button
              variant="secondary"
              onClick={handleStatementShare}
              disabled={
                sharingStatement ||
                !selectedCustomer ||
                !filteredSales.length
              }
            >
              <Share2 size={17} />
              {sharingStatement
                ? "Sharing..."
                : "Share statement"}
            </Button>

            <Button
              onClick={handleStatementDownload}
              disabled={
                !selectedCustomer || !filteredSales.length
              }
            >
              <Download size={17} />
              Download statement PDF
            </Button>
          </div>
        }
      />

      {message ? <div className="form-alert">{message}</div> : null}

      <section className="stats-grid stats-grid-three">
        <article className="mini-stat-card">
          <FileText size={21} />
          <div>
            <strong>{filteredSales.length}</strong>
            <span>Purchase records</span>
          </div>
        </article>

        <article className="mini-stat-card">
          <ReceiptText size={21} />
          <div>
            <strong>{formatCurrency(totals.paid)}</strong>
            <span>Total received</span>
          </div>
        </article>

        <article className="mini-stat-card">
          <PackageCheck size={21} />
          <div>
            <strong>{formatCurrency(totals.balance)}</strong>
            <span>Outstanding balance</span>
          </div>
        </article>
      </section>

      <section className="panel-card purchase-records-panel">
        <div className="purchase-records-toolbar">
          <label className="table-search">
            <Search size={18} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search sale, invoice, customer or product..."
            />
          </label>

          <select value={selectedCustomerId} onChange={chooseCustomer}>
            <option value="all">All customers</option>
            <option value="walk_in">Walk-in customers</option>
            {customers.map((customer) => (
              <option value={customer.id} key={customer.id}>
                {customer.name}
              </option>
            ))}
          </select>
        </div>

        <StickyTableScroll>
<table className="data-table purchase-records-table">
            <thead>
              <tr>
                <th>Purchase</th>
                <th>Customer</th>
                <th>Items</th>
                <th>Invoice</th>
                <th>Receipt</th>
                <th>Waybill</th>
                <th>Total</th>
                <th>Balance</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {paginatedSales.map((sale) => {
                const saleReceipts = receiptsBySaleId.get(sale.id) || [];
                const totalQuantity = (sale.items || []).reduce(
                  (sum, item) => sum + Number(item.quantity || 0),
                  0,
                );

                return (
                  <tr key={sale.id}>
                    <td>
                      <strong>{sale.saleNumber}</strong>
                      <small>{formatDate(sale.createdAt)}</small>
                    </td>

                    <td>{sale.customerName}</td>

                    <td>
                      <strong>{totalQuantity}</strong>
                      <small>{sale.items?.length || 0} item type(s)</small>
                    </td>

                    <td>
                      <strong>{sale.invoiceNumber}</strong>
                      <small>Generated</small>
                    </td>

                    <td>
                      {saleReceipts.length ? (
                        <>
                          <strong>{saleReceipts.length}</strong>
                          <small>
                            {saleReceipts
                              .map((receipt) => receipt.receiptNumber)
                              .join(", ")}
                          </small>
                        </>
                      ) : (
                        <span className="purchase-document-missing">
                          No receipt
                        </span>
                      )}
                    </td>

                    <td>
                      {sale.waybill?.waybillNumber ? (
                        <>
                          <strong>{sale.waybill.waybillNumber}</strong>
                          <small>{sale.waybill.status || "Pending"}</small>
                        </>
                      ) : (
                        <span className="purchase-document-missing">
                          Not created
                        </span>
                      )}
                    </td>

                    <td>
                      <strong>{formatCurrency(sale.total)}</strong>
                    </td>

                    <td>
                      <strong
                        className={
                          Number(sale.outstandingBalance || 0) > 0
                            ? "danger-text"
                            : "success-text"
                        }
                      >
                        {formatCurrency(sale.outstandingBalance)}
                      </strong>
                    </td>

                    <td>
                      <div className="purchase-record-actions">
                        <button
                          type="button"
                          onClick={() => setSelectedSale(sale)}
                        >
                          <Eye size={15} />
                          View
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}

              {!filteredSales.length ? (
                <tr>
                  <td colSpan="9">
                    <div className="purchase-records-empty">
                      No purchase records match the selected filters.
                    </div>
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </StickyTableScroll>

        <div className="purchase-records-pagination">
          <div className="purchase-pagination-summary">
            <span>
              Showing {firstVisibleRecord}-{lastVisibleRecord} of{" "}
              {filteredSales.length} records
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

          <div className="purchase-pagination-controls">
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

      <Modal
        open={Boolean(selectedSale)}
        onClose={() => setSelectedSale(null)}
        title={selectedSale?.saleNumber || "Purchase details"}
        description={
          selectedSale
            ? `${selectedSale.customerName} · ${formatDate(
                selectedSale.createdAt,
              )}`
            : ""
        }
      >
        {selectedSale ? (
          <div className="purchase-detail-content">
            <div className="purchase-detail-documents">
              <div>
                <span>Invoice</span>
                <strong>{selectedSale.invoiceNumber}</strong>
              </div>

              <div>
                <span>Receipt(s)</span>
                <strong>
                  {(receiptsBySaleId.get(selectedSale.id) || []).length
                    ? `${(receiptsBySaleId.get(selectedSale.id) || []).length} issued`
                    : "No receipt issued"}
                </strong>
              </div>

              <div>
                <span>Waybill</span>
                <strong>
                  {selectedSale.waybill?.waybillNumber || "Not created"}
                </strong>
              </div>
            </div>

            <section className="purchase-receipt-section">
              <div className="purchase-detail-section-heading">
                <div>
                  <span>Payment documents</span>
                  <strong>Receipts</strong>
                </div>
              </div>

              {(receiptsBySaleId.get(selectedSale.id) || []).length ? (
                <div className="purchase-receipt-list">
                  {(receiptsBySaleId.get(selectedSale.id) || []).map(
                    (receipt) => (
                      <article
                        className="purchase-receipt-row"
                        key={receipt.id}
                      >
                        <div>
                          <strong>{receipt.receiptNumber}</strong>
                          <small>
                            {formatCurrency(receipt.amount)} received
                          </small>
                        </div>

                        <button
                          type="button"
                          onClick={() =>
                            handleReceiptDownload(receipt, selectedSale)
                          }
                        >
                          <Download size={15} />
                          Receipt
                        </button>
                      </article>
                    ),
                  )}
                </div>
              ) : (
                <p className="purchase-document-note">
                  No payment receipt has been issued for this sale.
                </p>
              )}
            </section>

            <section className="purchase-waybill-section">
              <div className="purchase-detail-section-heading">
                <div>
                  <span>Delivery document</span>
                  <strong>
                    {selectedSale.waybill?.waybillNumber ||
                      "Waybill not created"}
                  </strong>
                </div>

                <div className="purchase-waybill-actions">
                  <button
                    type="button"
                    onClick={() => openWaybillForm(selectedSale)}
                  >
                    <Truck size={15} />
                    {selectedSale.waybill ? "Update" : "Create"}
                  </button>

                  {selectedSale.waybill ? (
                    <button
                      type="button"
                      onClick={() =>
                        handleWaybillDownload(selectedSale)
                      }
                    >
                      <Download size={15} />
                      Download
                    </button>
                  ) : null}
                </div>
              </div>

              {selectedSale.waybill ? (
                <div className="purchase-waybill-summary">
                  <span>
                    Recipient:{" "}
                    <strong>
                      {selectedSale.waybill.recipientName}
                    </strong>
                  </span>
                  <span>
                    Status:{" "}
                    <strong>{selectedSale.waybill.status}</strong>
                  </span>
                </div>
              ) : (
                <p className="purchase-document-note">
                  Create one waybill for all items in this sale.
                </p>
              )}
            </section>

            <div className="purchase-detail-items">
              {(selectedSale.items || []).map((item) => (
                <article key={`${selectedSale.id}-${item.productId}`}>
                  <div>
                    <strong>{item.name}</strong>
                    <small>
                      {item.quantity} {item.unit}(s) ×{" "}
                      {formatCurrency(item.unitPrice)}
                    </small>
                  </div>
                  <strong>{formatCurrency(item.total)}</strong>
                </article>
              ))}
            </div>

            <div className="purchase-detail-summary">
              <div>
                <span>Total</span>
                <strong>{formatCurrency(selectedSale.total)}</strong>
              </div>
              <div>
                <span>Amount paid</span>
                <strong>{formatCurrency(selectedSale.amountPaid)}</strong>
              </div>
              <div>
                <span>Balance</span>
                <strong>
                  {formatCurrency(selectedSale.outstandingBalance)}
                </strong>
              </div>
            </div>

            <div className="modal-form-actions">
              <Button
                variant="secondary"
                onClick={() => setSelectedSale(null)}
              >
                Close
              </Button>
              <Button onClick={() => handleInvoiceDownload(selectedSale)}>
                <Download size={17} />
                Download invoice
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={Boolean(waybillSale)}
        onClose={() => setWaybillSale(null)}
        title={waybillSale?.waybill ? "Update waybill" : "Create waybill"}
        description={
          waybillSale
            ? `One delivery document for every item in ${waybillSale.saleNumber}.`
            : ""
        }
      >
        {waybillSale ? (
          <form
            className="simple-form waybill-form"
            onSubmit={handleWaybillSubmit}
          >
            <div className="waybill-form-grid">
              <label>
                Recipient name
                <input
                  value={waybillForm.recipientName}
                  onChange={(event) =>
                    setWaybillForm((current) => ({
                      ...current,
                      recipientName: event.target.value,
                    }))
                  }
                  required
                />
              </label>

              <label>
                Recipient phone
                <input
                  value={waybillForm.recipientPhone}
                  onChange={(event) =>
                    setWaybillForm((current) => ({
                      ...current,
                      recipientPhone: event.target.value,
                    }))
                  }
                />
              </label>

              <label className="waybill-form-wide">
                Delivery address
                <textarea
                  rows="3"
                  value={waybillForm.deliveryAddress}
                  onChange={(event) =>
                    setWaybillForm((current) => ({
                      ...current,
                      deliveryAddress: event.target.value,
                    }))
                  }
                  required
                />
              </label>

              <label>
                Dispatch date
                <input
                  type="date"
                  value={waybillForm.dispatchDate}
                  onChange={(event) =>
                    setWaybillForm((current) => ({
                      ...current,
                      dispatchDate: event.target.value,
                    }))
                  }
                  required
                />
              </label>

              <label>
                Delivery status
                <select
                  value={waybillForm.status}
                  onChange={(event) =>
                    setWaybillForm((current) => ({
                      ...current,
                      status: event.target.value,
                    }))
                  }
                >
                  <option value="pending">Pending</option>
                  <option value="dispatched">Dispatched</option>
                  <option value="delivered">Delivered</option>
                </select>
              </label>

              <label>
                Driver or delivery person
                <input
                  value={waybillForm.driverName}
                  onChange={(event) =>
                    setWaybillForm((current) => ({
                      ...current,
                      driverName: event.target.value,
                    }))
                  }
                />
              </label>

              <label>
                Vehicle number
                <input
                  value={waybillForm.vehicleNumber}
                  onChange={(event) =>
                    setWaybillForm((current) => ({
                      ...current,
                      vehicleNumber: event.target.value,
                    }))
                  }
                />
              </label>

              <label className="waybill-form-wide">
                Delivery notes
                <textarea
                  rows="3"
                  value={waybillForm.deliveryNotes}
                  onChange={(event) =>
                    setWaybillForm((current) => ({
                      ...current,
                      deliveryNotes: event.target.value,
                    }))
                  }
                />
              </label>
            </div>

            <div className="modal-form-actions">
              <Button
                variant="secondary"
                onClick={() => setWaybillSale(null)}
              >
                Cancel
              </Button>

              <Button type="submit">
                <Save size={17} />
                Save waybill
              </Button>
            </div>
          </form>
        ) : null}
      </Modal>
    </div>
  );
}
