import {
  Boxes,
  Filter,
  PackagePlus,
  Search,
  Shirt,
  SlidersHorizontal,
  Tags,
} from "lucide-react";
import { PackagePlus as StockActionIcon, Pencil, Power, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import StickyTableScroll from "../../components/ui/StickyTableScroll";
import ProductFormModal from "../../components/products/ProductFormModal";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import PageHeader from "../../components/ui/PageHeader";
import { useStore } from "../../context/StoreContext";
import { formatCurrency, formatNumber } from "../../utils/formatters";

import "../../styles/boutique-inventory-records.css";

export default function BoutiquePage() {
  const {
    products,
    inventoryLoading,
    inventoryError,
    addProduct,
    updateProduct,
    toggleProductStatus,
    deleteProduct,
    adjustStock,
  } = useStore();

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [size, setSize] = useState("all");
  const [color, setColor] = useState("all");
  const [status, setStatus] = useState("all");

  const [productModalOpen, setProductModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);

  const [stockProduct, setStockProduct] = useState(null);
  const [stockForm, setStockForm] = useState({
    quantity: "",
    reason: "New stock received",
    type: "stock_in",
  });
  const [stockError, setStockError] = useState("");

  const [deleteProductTarget, setDeleteProductTarget] = useState(null);
  const [deleteError, setDeleteError] = useState("");
  const [inventoryActionError, setInventoryActionError] = useState("");
  const [statusProductId, setStatusProductId] = useState(null);
  const [stockSaving, setStockSaving] = useState(false);
  const [deleteSaving, setDeleteSaving] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Limits this specialist page to fashion records from the active boutique.
  const fashionProducts = useMemo(
    () => products.filter((product) => product.productType === "fashion"),
    [products],
  );

  const categories = useMemo(
    () =>
      [...new Set(fashionProducts.map((product) => product.category).filter(Boolean))]
        .sort(),
    [fashionProducts],
  );

  const sizes = useMemo(
    () =>
      [...new Set(fashionProducts.flatMap((product) => {
        const variantSizes = (product.variants ?? [])
          .map((variant) => variant.size)
          .filter(Boolean);

        return [product.size, ...variantSizes].filter(Boolean);
      }))].sort(),
    [fashionProducts],
  );

  const colors = useMemo(
    () =>
      [...new Set(fashionProducts.flatMap((product) => {
        const variantColors = (product.variants ?? [])
          .map((variant) => variant.color)
          .filter(Boolean);

        return [product.color, ...variantColors].filter(Boolean);
      }))].sort(),
    [fashionProducts],
  );

  const filteredProducts = useMemo(() => {
    const query = search.trim().toLowerCase();

    return fashionProducts.filter((product) => {
      const searchableValues = [
        product.name,
        product.styleCode,
        product.sku,
        product.category,
        product.brand,
        product.size,
        product.color,
      ]
        .filter(Boolean)
        .map((value) => String(value).toLowerCase());

      const variantSizes = (product.variants ?? []).map((variant) => variant.size);
      const variantColors = (product.variants ?? []).map((variant) => variant.color);

      const matchesSearch =
        !query || searchableValues.some((value) => value.includes(query));
      const matchesCategory =
        category === "all" || product.category === category;
      const matchesSize =
        size === "all" ||
        product.size === size ||
        variantSizes.includes(size);
      const matchesColor =
        color === "all" ||
        product.color === color ||
        variantColors.includes(color);
      const matchesStatus =
        status === "all" ||
        (status === "low_stock"
          ? product.stock <= product.lowStockLevel
          : product.status === status);

      return (
        matchesSearch &&
        matchesCategory &&
        matchesSize &&
        matchesColor &&
        matchesStatus
      );
    });
  }, [
    category,
    color,
    fashionProducts,
    search,
    size,
    status,
  ]);

  const totalPages = Math.max(
    1,
    Math.ceil(filteredProducts.length / pageSize),
  );

  const safeCurrentPage = Math.min(currentPage, totalPages);

  const paginatedProducts = useMemo(() => {
    const startIndex = (safeCurrentPage - 1) * pageSize;

    return filteredProducts.slice(startIndex, startIndex + pageSize);
  }, [filteredProducts, pageSize, safeCurrentPage]);

  const firstVisibleRecord = filteredProducts.length
    ? (safeCurrentPage - 1) * pageSize + 1
    : 0;

  const lastVisibleRecord = filteredProducts.length
    ? firstVisibleRecord + paginatedProducts.length - 1
    : 0;

  // Returns to page one whenever search, filters or page size change.
  useEffect(() => {
    setCurrentPage(1);
  }, [search, category, size, color, status, pageSize]);

  // Keeps the selected page inside the available page range.
  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  // Uses the shared stock-summary fields exposed to every inventory screen.
  const totalStockUnits = fashionProducts.reduce(
    (sum, product) => sum + Number(product.totalStock ?? product.stock ?? 0),
    0,
  );
  const totalSoldUnits = fashionProducts.reduce(
    (sum, product) => sum + Number(product.quantitySold ?? 0),
    0,
  );
  const totalAvailableUnits = fashionProducts.reduce(
    (sum, product) => sum + Number(product.availableStock ?? product.stock ?? 0),
    0,
  );

  async function saveProduct(form) {
    setInventoryActionError("");

    if (editingProduct) {
      return updateProduct(editingProduct.id, form);
    }

    return addProduct(form);
  }

  function openNewProductModal() {
    setEditingProduct(null);
    setProductModalOpen(true);
  }

  function openEditProductModal(product) {
    setEditingProduct(product);
    setProductModalOpen(true);
  }

  async function submitStockAdjustment(event) {
    event.preventDefault();

    if (stockSaving) return;

    setStockError("");
    setStockSaving(true);

    try {
      await adjustStock({
        productId: stockProduct.id,
        quantity: Number(stockForm.quantity),
        type: stockForm.type,
        reason: stockForm.reason,
      });

      setStockProduct(null);
      setStockForm({
        quantity: "",
        reason: "New stock received",
        type: "stock_in",
      });
    } catch (error) {
      setStockError(error.message);
    } finally {
      setStockSaving(false);
    }
  }

  async function confirmProductDeletion() {
    if (!deleteProductTarget || deleteSaving) return;

    setDeleteError("");
    setDeleteSaving(true);

    try {
      await deleteProduct(deleteProductTarget.id);
      setDeleteProductTarget(null);
    } catch (error) {
      setDeleteError(error.message);
    } finally {
      setDeleteSaving(false);
    }
  }

  async function changeProductStatus(product) {
    if (statusProductId) return;

    setInventoryActionError("");
    setStatusProductId(product.id);

    try {
      await toggleProductStatus(product.id);
    } catch (error) {
      setInventoryActionError(error.message);
    } finally {
      setStatusProductId(null);
    }
  }

  function clearFilters() {
    setSearch("");
    setCategory("all");
    setSize("all");
    setColor("all");
    setStatus("all");
  }

  const hasActiveFilters =
    search ||
    category !== "all" ||
    size !== "all" ||
    color !== "all" ||
    status !== "all";

  return (
    <div className="page-stack stockflow-inventory-page boutique-records-page rounded-2xl bg-emerald-50/55 p-1.5">
      <PageHeader
        eyebrow="Fashion inventory"
        title="Boutique Inventory"
        description="Record and manage clothing, footwear, bags and accessories by style, size, colour, stock and price."
        actions={
          <Button onClick={openNewProductModal}>
            <PackagePlus size={18} />

      {inventoryLoading ? (
        <div className="form-alert">Loading real boutique inventory...</div>
      ) : null}

      {inventoryError || inventoryActionError ? (
        <div className="form-alert form-alert-error">
          {inventoryActionError || inventoryError}
        </div>
      ) : null}
            Add boutique record
          </Button>
        }
      />

      <section className="boutique-records-summary">
        <article>
          <span><Shirt size={20} /></span>
          <div>
            <strong>{fashionProducts.length}</strong>
            <small>Product records</small>
          </div>
        </article>

        <article>
          <span><Boxes size={20} /></span>
          <div>
            <strong>{formatNumber(totalStockUnits, 0)}</strong>
            <small>Total stock</small>
          </div>
        </article>

        <article>
          <span><SlidersHorizontal size={20} /></span>
          <div>
            <strong>{formatNumber(totalSoldUnits, 0)}</strong>
            <small>Quantity sold</small>
          </div>
        </article>

        <article>
          <span><Tags size={20} /></span>
          <div>
            <strong>{formatNumber(totalAvailableUnits, 0)}</strong>
            <small>Available stock</small>
          </div>
        </article>
      </section>

      <section className="panel-card stockflow-inventory-panel boutique-records-panel">
        <div className="stockflow-inventory-toolbar boutique-records-toolbar">
          <div className="boutique-records-search-row">
            <label className="table-search boutique-records-search">
              <Search size={18} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search product, style code, SKU, brand or category..."
              />
            </label>

            <div className="boutique-records-result-group">
              <span className="boutique-records-result-count">
                {filteredProducts.length} record(s)
              </span>

              {hasActiveFilters ? (
                <button
                  type="button"
                  className="boutique-clear-filters"
                  onClick={clearFilters}
                >
                  <Filter size={14} />
                  Clear filters
                </button>
              ) : null}
            </div>
          </div>

          <div className="boutique-records-filters">
            <select
              value={category}
              onChange={(event) => setCategory(event.target.value)}
            >
              <option value="all">All categories</option>
              {categories.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>

            <select
              value={size}
              onChange={(event) => setSize(event.target.value)}
            >
              <option value="all">All sizes</option>
              {sizes.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>

            <select
              value={color}
              onChange={(event) => setColor(event.target.value)}
            >
              <option value="all">All colours</option>
              {colors.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>

            <select
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="low_stock">Low stock</option>
            </select>
          </div>
        </div>

        <StickyTableScroll className="stockflow-inventory-table-wrapper boutique-records-table-wrapper">
          <table className="w-full min-w-[900px] table-fixed border-collapse font-sans text-left text-[12px] text-slate-800">
            <colgroup>
              <col className="w-[19%]" />
              <col className="w-[11%]" />
              <col className="w-[14%]" />
              <col className="w-[14%]" />
              <col className="w-[9%]" />
              <col className="w-[9%]" />
              <col className="w-[10%]" />
              <col className="w-[14%]" />
            </colgroup>

            <thead className="bg-slate-50/95">
              <tr className="border-b border-slate-200">
                <th className="px-3 py-2 align-middle text-[10.5px] font-bold uppercase tracking-[0.075em] text-slate-600">Product</th>
                <th className="px-3 py-2 align-middle text-[10.5px] font-bold uppercase tracking-[0.075em] text-slate-600">Style / Category</th>
                <th className="px-3 py-2 align-middle text-[10.5px] font-bold uppercase tracking-[0.075em] text-slate-600">Variants</th>
                <th className="px-3 py-2 align-middle text-[10.5px] font-bold uppercase tracking-[0.075em] text-slate-600">Stock</th>
                <th className="px-3 py-2 align-middle text-[10.5px] font-bold uppercase tracking-[0.075em] text-slate-600">Selling Price</th>
                <th className="px-3 py-2 align-middle text-[10.5px] font-bold uppercase tracking-[0.075em] text-slate-600">Cost Price</th>
                <th className="px-3 py-2 align-middle text-[10.5px] font-bold uppercase tracking-[0.075em] text-slate-600">Status</th>
                <th className="px-3 py-2 text-center align-middle text-[10.5px] font-bold uppercase tracking-[0.075em] text-slate-600">Actions</th>
              </tr>
            </thead>

            <tbody>
              {paginatedProducts.map((product) => {
                const availableStock = Number(
                  product.availableStock ?? product.stock ?? 0,
                );
                const lowStock =
                  availableStock <= Number(product.lowStockLevel || 0);

                const variantSummary = product.variants?.length
                  ? `${product.variants.length} variant(s)`
                  : "No variants";

                const statusLabel =
                  product.status === "active"
                    ? lowStock
                      ? "Low stock"
                      : "Available"
                    : "Inactive";

                const statusClassName =
                  product.status !== "active"
                    ? "bg-slate-100 text-slate-700 ring-slate-300"
                    : lowStock
                      ? "bg-amber-50 text-amber-800 ring-amber-200"
                      : "bg-emerald-50 text-emerald-800 ring-emerald-200";

                const statusDotClassName =
                  product.status !== "active"
                    ? "bg-slate-400"
                    : lowStock
                      ? "bg-amber-500"
                      : "bg-emerald-500";

                return (
                  <tr
                    key={product.id}
                    className="border-b border-slate-200 bg-white transition-colors last:border-b-0 hover:bg-slate-50"
                  >
                    <td className="px-3 py-2 align-middle">
                      <div className="min-w-0">
                        <strong className="block truncate text-[13.5px] font-bold leading-5 text-slate-950">
                          {product.name}
                        </strong>
                        <div className="mt-0.5 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 text-[10.5px] font-medium leading-4 text-slate-600">
                          <span className="truncate">{product.brand || "Brand not recorded"}</span>
                          <span className="text-slate-400" aria-hidden="true">•</span>
                          <span className="truncate">SKU: {product.sku || "Not recorded"}</span>
                        </div>
                      </div>
                    </td>

                    <td className="px-3 py-2 align-middle">
                      <strong className="block truncate text-[12.5px] font-bold text-slate-900">
                        {product.styleCode || "Not recorded"}
                      </strong>
                      <small className="mt-0.5 block truncate text-[10.5px] font-medium text-slate-600">
                        {product.category || "Uncategorized"}
                      </small>
                    </td>

                    <td className="px-3 py-2 align-middle">
                      <div className="flex flex-wrap items-center gap-1">
                        <span className="inline-flex max-w-full items-center rounded-md bg-slate-100 px-2 py-1 text-[10.5px] font-semibold leading-none text-slate-700 ring-1 ring-inset ring-slate-200">
                          Size&nbsp;<strong className="truncate font-semibold">{product.size || "N/A"}</strong>
                        </span>
                        <span className="inline-flex max-w-full items-center rounded-md bg-slate-100 px-2 py-1 text-[10.5px] font-semibold leading-none text-slate-700 ring-1 ring-inset ring-slate-200">
                          <span className="truncate">{product.color || "No colour"}</span>
                        </span>
                        <span className="inline-flex max-w-full items-center rounded-md bg-white px-2 py-1 text-[10px] font-semibold leading-none text-slate-600 ring-1 ring-inset ring-slate-200">
                          {variantSummary}
                        </span>
                      </div>
                    </td>

                    <td className="px-3 py-2 align-middle">
                      <div className="flex items-center gap-1.5">
                        <strong className={`whitespace-nowrap text-[13.5px] font-bold ${lowStock ? "text-amber-800" : "text-slate-950"}`}>
                          {formatNumber(availableStock, 0)} units
                        </strong>
                        {lowStock ? (
                          <span className="inline-flex rounded-full bg-amber-50 px-1.5 py-0.5 text-[9.5px] font-bold leading-none text-amber-800 ring-1 ring-inset ring-amber-200">
                            Low
                          </span>
                        ) : null}
                      </div>
                      <small className="mt-0.5 block text-[10.5px] font-medium leading-4 text-slate-600">
                        <span className="block whitespace-nowrap">
                          Total {formatNumber(product.totalStock ?? product.stock ?? 0, 0)}
                          {" · "}Sold {formatNumber(product.quantitySold ?? 0, 0)}
                        </span>
                        <span className="block whitespace-nowrap text-slate-500">
                          Alert {formatNumber(product.lowStockLevel || 0, 0)}
                        </span>
                      </small>
                    </td>

                    <td className="px-3 py-2 align-middle">
                      <strong className="block whitespace-nowrap text-[13.5px] font-bold text-slate-950">
                        {formatCurrency(product.sellingPrice)}
                      </strong>
                    </td>

                    <td className="px-3 py-2 align-middle">
                      <strong className="block whitespace-nowrap text-[12.5px] font-semibold text-slate-800">
                        {formatCurrency(product.costPrice)}
                      </strong>
                    </td>

                    <td className="px-3 py-2 align-middle">
                      <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[10.5px] font-bold ring-1 ring-inset ${statusClassName}`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${statusDotClassName}`} aria-hidden="true" />
                        {statusLabel}
                      </span>
                    </td>

                    <td className="px-3 py-2 align-middle">
                      <div className="flex items-center justify-center gap-1">
                        <button
                          type="button"
                          className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 disabled:cursor-not-allowed disabled:opacity-40"
                          aria-label={`Edit ${product.name}`}
                          title="Edit product"
                          onClick={() => openEditProductModal(product)}
                        >
                          <Pencil size={14} aria-hidden="true" />
                        </button>

                        <button
                          type="button"
                          className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-emerald-200 hover:bg-emerald-50 hover:text-emerald-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 disabled:cursor-not-allowed disabled:opacity-40"
                          aria-label={`Adjust stock for ${product.name}`}
                          title="Adjust stock"
                          onClick={() => setStockProduct(product)}
                          disabled={product.status !== "active"}
                        >
                          <StockActionIcon size={14} aria-hidden="true" />
                        </button>

                        <button
                          type="button"
                          className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-amber-200 hover:bg-amber-50 hover:text-amber-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 disabled:cursor-not-allowed disabled:opacity-40"
                          aria-label={
                            statusProductId === product.id
                              ? `Updating ${product.name}`
                              : product.status === "active"
                                ? `Deactivate ${product.name}`
                                : `Activate ${product.name}`
                          }
                          title={
                            statusProductId === product.id
                              ? "Updating status"
                              : product.status === "active"
                                ? "Deactivate product"
                                : "Activate product"
                          }
                          onClick={() => changeProductStatus(product)}
                          disabled={Boolean(statusProductId)}
                        >
                          <Power size={14} aria-hidden="true" />
                        </button>

                        <button
                          type="button"
                          className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:border-red-200 hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                          aria-label={`Delete ${product.name}`}
                          title="Archive product"
                          onClick={() => {
                            setDeleteError("");
                            setDeleteProductTarget(product);
                          }}
                        >
                          <Trash2 size={14} aria-hidden="true" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}

              {!filteredProducts.length ? (
                <tr>
                  <td className="px-6 py-12 text-center" colSpan="8">
                    <strong className="block text-sm font-semibold text-slate-900">
                      No boutique records found.
                    </strong>
                    <span className="mt-1 block text-xs text-slate-500">
                      Change the filters or add a new boutique record.
                    </span>
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </StickyTableScroll>

        <div className="boutique-records-pagination">
          <div className="boutique-pagination-summary">
            <span>
              Showing {firstVisibleRecord}-{lastVisibleRecord} of{" "}
              {filteredProducts.length} records
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

          <div className="boutique-pagination-controls">
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

      <ProductFormModal
        open={productModalOpen}
        onClose={() => {
          setProductModalOpen(false);
          setEditingProduct(null);
        }}
        onSave={saveProduct}
        product={editingProduct}
        defaultType="fashion"
      />

      <Modal
        open={Boolean(stockProduct)}
        onClose={() => {
          if (stockSaving) return;
          setStockProduct(null);
          setStockError("");
        }}
        title="Adjust boutique stock"
        description={
          stockProduct
            ? `${stockProduct.name} currently has ${stockProduct.stock} unit(s).`
            : ""
        }
      >
        {stockError ? (
          <div className="form-alert form-alert-error">{stockError}</div>
        ) : null}

        <form className="simple-form" onSubmit={submitStockAdjustment}>
          <label>
            Movement type
            <select
              value={stockForm.type}
              onChange={(event) =>
                setStockForm((current) => ({
                  ...current,
                  type: event.target.value,
                }))
              }
            >
              <option value="stock_in">New stock received</option>
              <option value="adjustment">Manual correction</option>
              <option value="damage">Damaged stock</option>
              <option value="return">Customer return</option>
            </select>
          </label>

          <label>
            Quantity change
            <input
              type="number"
              value={stockForm.quantity}
              onChange={(event) =>
                setStockForm((current) => ({
                  ...current,
                  quantity: event.target.value,
                }))
              }
              placeholder="Use -2 to reduce stock"
              required
            />
          </label>

          <label>
            Reason
            <textarea
              value={stockForm.reason}
              onChange={(event) =>
                setStockForm((current) => ({
                  ...current,
                  reason: event.target.value,
                }))
              }
              rows="3"
              required
            />
          </label>

          <div className="modal-form-actions">
            <Button
              variant="secondary"
              onClick={() => setStockProduct(null)}
              disabled={stockSaving}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={stockSaving}>
              {stockSaving ? "Saving..." : "Save adjustment"}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={Boolean(deleteProductTarget)}
        onClose={() => {
          if (deleteSaving) return;
          setDeleteProductTarget(null);
          setDeleteError("");
        }}
        title="Archive boutique record"
        description={
          deleteProductTarget
            ? `Archive ${deleteProductTarget.name} without deleting its stock history.`
            : ""
        }
      >
        {deleteError ? (
          <div className="form-alert form-alert-error">{deleteError}</div>
        ) : null}

        <div className="boutique-delete-confirmation">
          <p>
            The product will become inactive but its stock and transaction history
            will remain safely stored.
          </p>

          <div className="modal-form-actions">
            <Button
              variant="secondary"
              onClick={() => {
                setDeleteProductTarget(null);
                setDeleteError("");
              }}
            >
              Cancel
            </Button>

            <button
              type="button"
              className="boutique-delete-confirm-button"
              onClick={confirmProductDeletion}
              disabled={deleteSaving}
            >
              {deleteSaving ? "Archiving..." : "Archive record"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
