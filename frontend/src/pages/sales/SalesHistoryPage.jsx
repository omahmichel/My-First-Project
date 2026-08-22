import { Download, Search, ShoppingCart } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import StickyTableScroll from "../../components/ui/StickyTableScroll";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import PageHeader from "../../components/ui/PageHeader";
import { useStore } from "../../context/StoreContext";
import {
  exportSalesHistoryCsv,
  exportSalesHistoryPdf,
  formatPaymentMethod,
} from "../../utils/invoiceDocuments";
import { formatCurrency, formatDateTime } from "../../utils/formatters";

import "../../styles/sales-history-compact.css";
import "../../styles/sales-history-export.css";

export default function SalesHistoryPage() {
  const { sales, business, salesLoading, salesError } = useStore();
  const [search, setSearch] = useState("");
  const [payment, setPayment] = useState("all");
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const filtered = useMemo(
    () =>
      sales.filter((sale) => {
        const query = search.trim().toLowerCase();

        const matches =
          !query ||
          [
            sale.saleNumber,
            sale.invoiceNumber,
            sale.customerName,
            sale.cashier,

            ...(sale.items ?? []).flatMap((item) => [
              item.designCode,
              item.sku,
              item.name,
            ]),
          ]
            .filter(Boolean)
            .some((value) =>
              String(value).toLowerCase().includes(query),
            );

        return (
          matches &&
          (payment === "all" || sale.paymentMethod === payment)
        );
      }),
    [payment, sales, search],
  );

  const totalPages = Math.max(
    1,
    Math.ceil(filtered.length / pageSize),
  );

  const safeCurrentPage = Math.min(currentPage, totalPages);

  const paginatedSales = useMemo(() => {
    const startIndex = (safeCurrentPage - 1) * pageSize;

    return filtered.slice(startIndex, startIndex + pageSize);
  }, [filtered, pageSize, safeCurrentPage]);

  const firstVisibleRecord = filtered.length
    ? (safeCurrentPage - 1) * pageSize + 1
    : 0;

  const lastVisibleRecord = filtered.length
    ? firstVisibleRecord + paginatedSales.length - 1
    : 0;

  // Returns to page one whenever filters or page size change.
  useEffect(() => {
    setCurrentPage(1);
  }, [search, payment, pageSize]);

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

  function handleExportPdf() {
    clearActionFeedback();

    try {
      const filename = exportSalesHistoryPdf(filtered, business);
      setActionMessage(`${filename} downloaded successfully.`);
    } catch (error) {
      setActionError(
        error.message || "The sales PDF report could not be exported.",
      );
    }
  }

  function handleExportCsv() {
    clearActionFeedback();

    try {
      const filename = exportSalesHistoryCsv(filtered, business);
      setActionMessage(`${filename} downloaded successfully.`);
    } catch (error) {
      setActionError(
        error.message || "The sales CSV file could not be exported.",
      );
    }
  }

  return (
    <div className="page-stack sales-history-page">
      <PageHeader
        eyebrow="Transactions"
        title="Sales history"
        description="Review completed and partially paid sales without changing their original values."
        actions={
          <div className="sales-history-export-options">
            <Button
              onClick={handleExportPdf}
              disabled={salesLoading || !filtered.length}
            >
              <Download size={18} />
              Export PDF
            </Button>

            <Button
              variant="secondary"
              onClick={handleExportCsv}
              disabled={salesLoading || !filtered.length}
            >
              <Download size={18} />
              Export CSV
            </Button>
          </div>
        }
      />

      {actionMessage ? (
        <div className="sales-history-export-feedback" role="status">
          {actionMessage}
        </div>
      ) : null}

      {actionError ? (
        <div
          className="sales-history-export-feedback sales-history-export-feedback-error"
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
              placeholder="Search sale, invoice or customer..."
            />
          </label>

          <select
            value={payment}
            onChange={(event) => setPayment(event.target.value)}
          >
            <option value="all">All payments</option>
            <option value="cash">Cash</option>
            <option value="mobile_money">Mobile Money</option>
            <option value="bank_transfer">Bank transfer</option>
            <option value="credit">Credit</option>
          </select>
        </div>

        <StickyTableScroll className="sales-history-table-wrapper">
<table className="data-table stockflow-premium-table stockflow-wide-record-table sales-history-table">
            <thead>
              <tr>
                <th>Product reference</th>
                <th>Customer</th>
                <th>Items</th>
                <th>Payment</th>
                <th>Principal paid</th>
                <th>Total payable</th>
                <th>Total</th>
                <th>Status</th>
              </tr>
            </thead>

            <tbody>
              {paginatedSales.map((sale) => (
                <tr key={sale.id}>
                  <td data-label="Product reference">
                    <strong className="sales-history-product-reference">
                      {[...new Set(
                        (sale.items ?? [])
                          .map((item) => item.designCode || item.sku || item.name)
                          .filter(Boolean),
                      )].slice(0, 3).join(" · ") || "Product not recorded"}
                    </strong>
                    <small>
                      {(sale.items ?? []).length > 3
                        ? `+${sale.items.length - 3} more · `
                        : ""}
                      {sale.invoiceNumber} · {formatDateTime(sale.createdAt)}
                    </small>
                  </td>

                  <td data-label="Customer">
                    {sale.customerName}
                    <small>By {sale.cashier}</small>
                  </td>

                  <td data-label="Items">
                    <span className="table-icon-value">
                      <ShoppingCart size={15} />
                      {(sale.items ?? []).reduce(
                        (sum, item) =>
                          sum + Number(item.quantity || 0),
                        0,
                      )}
                    </span>
                  </td>

                  <td data-label="Payment">
                    {formatPaymentMethod(sale.paymentMethod)}
                  </td>

                  <td data-label="Principal paid">
                    {formatCurrency(sale.amountPaid)}
                  </td>

                  <td
                    data-label="Total payable"
                    className={
                      Number(
                        sale.totalDebtPayable ??
                          sale.outstandingBalance ??
                          0,
                      ) > 0
                        ? "danger-text"
                        : ""
                    }
                  >
                    <strong>
                      {formatCurrency(
                        sale.totalDebtPayable ??
                          sale.outstandingBalance ??
                          0,
                      )}
                    </strong>
                    {Number(sale.overdueCharge ?? 0) > 0 ? (
                      <small>
                        Includes {formatCurrency(sale.overdueCharge)} charge
                      </small>
                    ) : null}
                  </td>

                  <td data-label="Total">
                    <strong>{formatCurrency(sale.total)}</strong>
                  </td>

                  <td data-label="Status">
                    <Badge
                      tone={
                        Number(
                          sale.totalDebtPayable ??
                            sale.outstandingBalance ??
                            0,
                        ) > 0
                          ? "warning"
                          : "success"
                      }
                    >
                      {Number(sale.daysOverdue ?? 0) > 0
                        ? `Overdue ${sale.daysOverdue} day(s)`
                        : Number(
                              sale.totalDebtPayable ??
                                sale.outstandingBalance ??
                                0,
                            ) > 0
                          ? "Part paid"
                          : "Completed"}
                    </Badge>
                  </td>
                </tr>
              ))}

              {salesLoading ? (
                <tr>
                  <td className="sales-history-empty" colSpan="8">
                    Loading sales history...
                  </td>
                </tr>
              ) : null}

              {salesError ? (
                <tr>
                  <td
                    className="sales-history-empty danger-text"
                    colSpan="8"
                  >
                    {salesError}
                  </td>
                </tr>
              ) : null}

              {!salesLoading && !salesError && !filtered.length ? (
                <tr>
                  <td className="sales-history-empty" colSpan="8">
                    No sales records match the current filters.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </StickyTableScroll>

        <div className="sales-history-pagination">
          <div className="sales-history-pagination-summary">
            <span>
              Showing {firstVisibleRecord}-{lastVisibleRecord} of{" "}
              {filtered.length} records
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

          <div className="sales-history-pagination-controls">
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
    </div>
  );
}
