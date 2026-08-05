import {
  Download,
  Eye,
  FileText,
  Printer,
  Search,
  Share2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import PageHeader from "../../components/ui/PageHeader";
import { useStore } from "../../context/StoreContext";
import {
  downloadInvoicePdf,
  exportInvoiceList,
  formatPaymentMethod,
  shareInvoice,
} from "../../utils/invoiceDocuments";
import { formatCurrency, formatDate } from "../../utils/formatters";

import "../../styles/invoice-document-actions.css";
import "../../styles/invoices-compact.css";

export default function InvoicesPage() {
  const { sales, business, salesLoading, salesError } = useStore();
  const [search, setSearch] = useState("");
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [sharingInvoiceId, setSharingInvoiceId] = useState(null);
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const query = search.trim().toLowerCase();

  const invoices = useMemo(
    () =>
      sales.filter((sale) =>
        [sale.invoiceNumber, sale.customerName, sale.saleNumber]
          .filter(Boolean)
          .some((value) =>
            String(value).toLowerCase().includes(query),
          ),
      ),
    [query, sales],
  );

  const totalPages = Math.max(
    1,
    Math.ceil(invoices.length / pageSize),
  );

  const safeCurrentPage = Math.min(currentPage, totalPages);

  const paginatedInvoices = useMemo(() => {
    const startIndex = (safeCurrentPage - 1) * pageSize;

    return invoices.slice(startIndex, startIndex + pageSize);
  }, [invoices, pageSize, safeCurrentPage]);

  const firstVisibleRecord = invoices.length
    ? (safeCurrentPage - 1) * pageSize + 1
    : 0;

  const lastVisibleRecord = invoices.length
    ? firstVisibleRecord + paginatedInvoices.length - 1
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

  function clearActionFeedback() {
    setActionMessage("");
    setActionError("");
  }

  function handleExportList() {
    clearActionFeedback();

    try {
      const filename = exportInvoiceList(invoices, business);
      setActionMessage(`${filename} downloaded successfully.`);
    } catch (error) {
      setActionError(error.message || "The invoice list could not be exported.");
    }
  }

  function handleDownloadPdf(invoice) {
    clearActionFeedback();

    try {
      const filename = downloadInvoicePdf(invoice, business);
      setActionMessage(`${filename} downloaded successfully.`);
    } catch (error) {
      setActionError(error.message || "The invoice PDF could not be created.");
    }
  }

  async function handleShareInvoice(invoice) {
    clearActionFeedback();
    setSharingInvoiceId(invoice.id);

    try {
      const message = await shareInvoice(invoice, business);
      setActionMessage(message);
    } catch (error) {
      if (error?.name === "AbortError") {
        setActionMessage("Sharing was cancelled.");
      } else {
        setActionError(error.message || "The invoice could not be shared.");
      }
    } finally {
      setSharingInvoiceId(null);
    }
  }

  return (
    <div className="page-stack invoices-page">
      <PageHeader
        eyebrow="Sales documents"
        title="Invoices and receipts"
        description="Find, review, download and share every document generated from a completed sale."
        actions={
          <Button
            variant="secondary"
            onClick={handleExportList}
            disabled={salesLoading || !invoices.length}
          >
            <Download size={18} />
            Export list
          </Button>
        }
      />

      {actionMessage ? (
        <div className="invoice-action-feedback" role="status">
          {actionMessage}
        </div>
      ) : null}

      {actionError ? (
        <div
          className="invoice-action-feedback invoice-action-feedback-error"
          role="alert"
        >
          {actionError}
        </div>
      ) : null}

      <section className="panel-card">
        <div className="table-toolbar">
          <label className="table-search">
            <Search size={18} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search invoice or customer..."
            />
          </label>

          <span className="result-count">{invoices.length} document(s)</span>
        </div>

        <div className="invoice-card-list">
          {paginatedInvoices.map((invoice) => (
            <article key={invoice.id}>
              <div className="invoice-list-icon">
                <FileText size={22} />
              </div>

              <div className="invoice-list-main">
                <strong>{invoice.invoiceNumber}</strong>
                <span>{invoice.customerName}</span>
                <small>
                  {formatDate(invoice.createdAt)} · {invoice.items?.length ?? 0}{" "}
                  item type(s)
                </small>
              </div>

              <div className="invoice-list-payment">
                <span>Payment</span>
                <strong>{formatPaymentMethod(invoice.paymentMethod)}</strong>
              </div>

              <div className="invoice-list-total">
                <span>Total</span>
                <strong>{formatCurrency(invoice.total)}</strong>
                {Number(invoice.overdueCharge ?? 0) > 0 ? (
                  <small className="danger-text">
                    {formatCurrency(invoice.overdueCharge)} overdue charge
                  </small>
                ) : invoice.debtDueDate ? (
                  <small>Due {formatDate(invoice.debtDueDate)}</small>
                ) : null}
              </div>

              <Badge
                tone={
                  Number(
                    invoice.totalDebtPayable ??
                      invoice.outstandingBalance ??
                      0,
                  ) > 0
                    ? "warning"
                    : "success"
                }
              >
                {Number(
                  invoice.totalDebtPayable ??
                    invoice.outstandingBalance ??
                    0,
                ) > 0
                  ? `${formatCurrency(
                      invoice.totalDebtPayable ??
                        invoice.outstandingBalance ??
                        0,
                    )} payable`
                  : "Paid"}
              </Badge>

              <div className="invoice-list-actions">
                <button
                  type="button"
                  onClick={() => {
                    clearActionFeedback();
                    setSelectedInvoice(invoice);
                  }}
                >
                  <Eye size={17} />
                  View
                </button>

                <button
                  type="button"
                  className="invoice-share-button"
                  onClick={() => handleShareInvoice(invoice)}
                  disabled={sharingInvoiceId === invoice.id}
                  aria-label={`Share invoice ${invoice.invoiceNumber}`}
                  title={`Share invoice ${invoice.invoiceNumber}`}
                >
                  <Share2 size={17} />
                  <span className="sr-only">
                    {sharingInvoiceId === invoice.id ? "Sharing" : "Share"}
                  </span>
                </button>
              </div>
            </article>
          ))}

          {salesLoading ? (
            <div className="invoice-list-empty" role="status">
              <FileText size={24} />
              <strong>Loading invoice records...</strong>
            </div>
          ) : null}

          {salesError ? (
            <div
              className="invoice-list-empty danger-text"
              role="alert"
            >
              <FileText size={24} />
              <strong>{salesError}</strong>
            </div>
          ) : null}

          {!salesLoading && !salesError && !invoices.length ? (
            <div className="invoice-list-empty">
              <FileText size={24} />
              <strong>No invoice records found.</strong>
              <span>Change the search or complete a new sale.</span>
            </div>
          ) : null}
        </div>

        <div className="invoices-pagination">
          <div className="invoices-pagination-summary">
            <span>
              Showing {firstVisibleRecord}-{lastVisibleRecord} of{" "}
              {invoices.length} documents
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

          <div className="invoices-pagination-controls">
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
        open={Boolean(selectedInvoice)}
        onClose={() => setSelectedInvoice(null)}
        title="Invoice preview"
        size="large"
      >
        {selectedInvoice ? (
          <div className="invoice-document">
            <header>
              <div>
                <span className="invoice-document-logo">S</span>
                <div>
                  <strong>{business.name}</strong>
                  <small>
                    {business.location}
                    <br />
                    {business.phone}
                  </small>
                </div>
              </div>

              <div>
                <span>INVOICE</span>
                <strong>{selectedInvoice.invoiceNumber}</strong>
                <small>{formatDate(selectedInvoice.createdAt)}</small>
              </div>
            </header>

            <section className="invoice-customer-row">
              <div>
                <span>Bill to</span>
                <strong>{selectedInvoice.customerName}</strong>
              </div>

              <div>
                <span>Payment method</span>
                <strong>
                  {formatPaymentMethod(selectedInvoice.paymentMethod)}
                </strong>
              </div>
            </section>

            <table>
              <thead>
                <tr>
                  <th>Item</th>
                  <th>Quantity</th>
                  <th>Unit price</th>
                  <th>Total</th>
                </tr>
              </thead>

              <tbody>
                {(selectedInvoice.items ?? []).map((item, index) => (
                  <tr key={`${item.productId}-${index}`}>
                    <td>{item.name}</td>
                    <td>
                      {item.quantity} {item.unit}(s)
                    </td>
                    <td>{formatCurrency(item.unitPrice)}</td>
                    <td>{formatCurrency(item.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="invoice-document-totals">
              <div>
                <span>Subtotal</span>
                <strong>{formatCurrency(selectedInvoice.subtotal)}</strong>
              </div>

              <div>
                <span>Discount</span>
                <strong>{formatCurrency(selectedInvoice.discount)}</strong>
              </div>

              <div>
                <span>Principal paid</span>
                <strong>{formatCurrency(selectedInvoice.amountPaid)}</strong>
              </div>

              <div>
                <span>Principal balance</span>
                <strong>
                  {formatCurrency(selectedInvoice.outstandingBalance)}
                </strong>
              </div>

              <div>
                <span>Overdue charge</span>
                <strong>
                  {formatCurrency(selectedInvoice.overdueCharge ?? 0)}
                </strong>
              </div>

              <div>
                <span>Debt due date</span>
                <strong>{formatDate(selectedInvoice.debtDueDate)}</strong>
              </div>

              <div className="invoice-document-grand">
                <span>Sale total</span>
                <strong>{formatCurrency(selectedInvoice.total)}</strong>
              </div>

              {Number(
                selectedInvoice.totalDebtPayable ??
                  selectedInvoice.outstandingBalance ??
                  0,
              ) > 0 ? (
                <div className="invoice-balance-due">
                  <span>Total payable</span>
                  <strong>
                    {formatCurrency(
                      selectedInvoice.totalDebtPayable ??
                        selectedInvoice.outstandingBalance ??
                        0,
                    )}
                  </strong>
                  {Number(selectedInvoice.daysOverdue ?? 0) > 0 ? (
                    <small>
                      {selectedInvoice.daysOverdue} day(s) overdue at{" "}
                      {selectedInvoice.overduePercentage}% tier
                    </small>
                  ) : null}
                </div>
              ) : null}
            </div>

            <footer>
              <span>Thank you for doing business with us.</span>

              <div>
                <Button
                  variant="secondary"
                  onClick={() => window.print()}
                >
                  <Printer size={17} />
                  Print
                </Button>

                <Button
                  onClick={() => handleDownloadPdf(selectedInvoice)}
                >
                  <Download size={17} />
                  Download PDF
                </Button>
              </div>
            </footer>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
