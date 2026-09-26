import {
  Boxes,
  Car,
  CircleDollarSign,
  Filter,
  PackagePlus,
  Pencil,
  Power,
  Search,
  ShoppingCart,
  Smartphone,
  Sparkles,
  Trash2,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import RetailProductFormModal from "../../components/products/RetailProductFormModal";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import PageHeader from "../../components/ui/PageHeader";
import StickyTableScroll from "../../components/ui/StickyTableScroll";
import { useStore } from "../../context/StoreContext";
import { businessTypeLabel } from "../../data/businessTypes";
import { retailInventoryConfig } from "../../data/retailInventoryConfig";
import { formatCurrency, formatNumber } from "../../utils/formatters";

import "../../styles/retail-inventory.css";

const ROUTE_ICONS = {
  provision_mini_mart: ShoppingCart,
  phone_electronics_accessories: Smartphone,
  electrical_electronics: Zap,
  auto_spare_parts: Car,
  cosmetics_beauty: Sparkles,
};

function detailValue(product, key) {
  const value = product.retailDetails?.[key];
  return value === null || value === undefined || value === ""
    ? ""
    : String(value);
}

function recordCountLabel(count) {
  return `${count} ${count === 1 ? "record" : "records"}`;
}

export default function RetailInventoryPage() {
  const {
    business,
    products,
    inventoryLoading,
    inventoryError,
    addProduct,
    updateProduct,
    toggleProductStatus,
    deleteProduct,
    adjustStock,
  } = useStore();

  const config = retailInventoryConfig(business.type);
  const RouteIcon = ROUTE_ICONS[business.type] || Boxes;
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
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
  const [stockSaving, setStockSaving] = useState(false);
  const [archiveProduct, setArchiveProduct] = useState(null);
  const [archiveError, setArchiveError] = useState("");
  const [archiveSaving, setArchiveSaving] = useState(false);
  const [actionError, setActionError] = useState("");
  const [statusProductId, setStatusProductId] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const retailProducts = useMemo(
    () => products.filter((product) => product.productType === "standard"),
    [products],
  );

  const categories = useMemo(
    () =>
      [...new Set(retailProducts.map((product) => product.category).filter(Boolean))]
        .sort((a, b) => a.localeCompare(b)),
    [retailProducts],
  );

  const filteredProducts = useMemo(() => {
    const query = search.trim().toLowerCase();

    return retailProducts.filter((product) => {
      const retailValues = Object.values(product.retailDetails || {});
      const searchable = [
        product.name,
        product.sku,
        product.category,
        product.brand,
        product.unit,
        ...retailValues,
      ]
        .filter(Boolean)
        .map((value) => String(value).toLowerCase());

      const matchesSearch =
        !query || searchable.some((value) => value.includes(query));
      const matchesCategory =
        category === "all" || product.category === category;
      const available = Number(product.availableStock ?? product.stock ?? 0);
      const matchesStatus =
        status === "all" ||
        (status === "low_stock"
          ? product.status === "active" &&
            available <= Number(product.lowStockLevel || 0)
          : product.status === status);

      return matchesSearch && matchesCategory && matchesStatus;
    });
  }, [category, retailProducts, search, status]);

  const totalPages = Math.max(1, Math.ceil(filteredProducts.length / pageSize));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const paginatedProducts = useMemo(() => {
    const start = (safeCurrentPage - 1) * pageSize;
    return filteredProducts.slice(start, start + pageSize);
  }, [filteredProducts, pageSize, safeCurrentPage]);

  useEffect(() => {
    setCurrentPage(1);
  }, [search, category, status, pageSize]);

  useEffect(() => {
    if (currentPage > totalPages) setCurrentPage(totalPages);
  }, [currentPage, totalPages]);

  if (!config) return null;

  const totalAvailable = retailProducts.reduce(
    (sum, product) =>
      sum + Number(product.availableStock ?? product.stock ?? 0),
    0,
  );
  const lowStockCount = retailProducts.filter((product) => {
    const available = Number(product.availableStock ?? product.stock ?? 0);
    return (
      product.status === "active" &&
      available <= Number(product.lowStockLevel || 0)
    );
  }).length;
  const stockValue = retailProducts.reduce((sum, product) => {
    const available = Number(product.availableStock ?? product.stock ?? 0);
    return sum + available * Number(product.costPrice ?? 0);
  }, 0);

  const firstVisible = filteredProducts.length
    ? (safeCurrentPage - 1) * pageSize + 1
    : 0;
  const lastVisible = filteredProducts.length
    ? firstVisible + paginatedProducts.length - 1
    : 0;
  const hasActiveFilters = search || category !== "all" || status !== "all";

  function openNewProduct() {
    setEditingProduct(null);
    setProductModalOpen(true);
  }

  function openEditProduct(product) {
    setEditingProduct(product);
    setProductModalOpen(true);
  }

  async function saveProduct(form) {
    setActionError("");
    if (editingProduct) return updateProduct(editingProduct.id, form);
    return addProduct(form);
  }

  async function changeProductStatus(product) {
    if (statusProductId) return;
    setActionError("");
    setStatusProductId(product.id);
    try {
      await toggleProductStatus(product.id);
    } catch (error) {
      setActionError(error.message);
    } finally {
      setStatusProductId(null);
    }
  }

  async function submitStockAdjustment(event) {
    event.preventDefault();
    if (!stockProduct || stockSaving) return;
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

  async function confirmArchive() {
    if (!archiveProduct || archiveSaving) return;
    setArchiveError("");
    setArchiveSaving(true);
    try {
      await deleteProduct(archiveProduct.id);
      setArchiveProduct(null);
    } catch (error) {
      setArchiveError(error.message);
    } finally {
      setArchiveSaving(false);
    }
  }

  function clearFilters() {
    setSearch("");
    setCategory("all");
    setStatus("all");
  }

  return (
    <div className={`page-stack retail-inventory-page retail-inventory-${config.slug}`}>
      <section className="retail-inventory-hero">
        <div className="retail-inventory-hero-copy">
          <span className="retail-inventory-route-icon" aria-hidden="true">
            <RouteIcon size={24} />
          </span>
          <div>
            <small>{config.eyebrow}</small>
            <strong>{business.name || config.title}</strong>
            <p>Specialist StockFlow workspace · {config.recordLabel}</p>
          </div>
        </div>
        <span className="retail-inventory-route-badge">{businessTypeLabel(business.type)}</span>
      </section>

      <PageHeader
        eyebrow={config.eyebrow}
        title={config.title}
        description={config.description}
        actions={
          <Button onClick={openNewProduct}>
            <PackagePlus size={18} /> {config.addLabel}
          </Button>
        }
      />

      {inventoryLoading ? (
        <div className="form-alert">Loading real inventory...</div>
      ) : null}
      {inventoryError || actionError ? (
        <div className="form-alert form-alert-error">
          {actionError || inventoryError}
        </div>
      ) : null}

      <section className="retail-inventory-summary">
        <article>
          <span><Boxes size={20} /></span>
          <div><strong>{retailProducts.length}</strong><small>Product records</small></div>
        </article>
        <article>
          <span><RouteIcon size={20} /></span>
          <div><strong>{formatNumber(totalAvailable, 0)}</strong><small>Available units</small></div>
        </article>
        <article>
          <span><Filter size={20} /></span>
          <div><strong>{lowStockCount}</strong><small>Low-stock records</small></div>
        </article>
        <article>
          <span><CircleDollarSign size={20} /></span>
          <div><strong>{formatCurrency(stockValue)}</strong><small>Stock cost value</small></div>
        </article>
      </section>

      <section className="panel-card retail-inventory-panel">
        <div className="retail-inventory-toolbar">
          <div className="retail-inventory-search-row">
            <label className="table-search retail-inventory-search">
              <Search size={18} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={config.searchPlaceholder}
              />
            </label>
            <div className="retail-inventory-result-group">
              <span>{recordCountLabel(filteredProducts.length)}</span>
              {hasActiveFilters ? (
                <button type="button" onClick={clearFilters}>
                  <Filter size={14} /> Clear filters
                </button>
              ) : null}
            </div>
          </div>

          <div className="retail-inventory-filters">
            <select value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="all">All categories</option>
              {categories.map((item) => <option key={item}>{item}</option>)}
            </select>
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="low_stock">Low stock</option>
            </select>
          </div>
        </div>

        <StickyTableScroll className="retail-inventory-table-wrapper">
          <table className="retail-inventory-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Category</th>
                <th>{config.detailsHeading || "Product details"}</th>
                <th>Stock</th>
                <th>Selling price</th>
                <th>Cost price</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {paginatedProducts.map((product) => {
                const available = Number(product.availableStock ?? product.stock ?? 0);
                const lowStock = available <= Number(product.lowStockLevel || 0);
                const detailEntries = config.highlights
                  .map((key) => {
                    const field = config.details.find((item) => item.key === key);
                    const value = detailValue(product, key);
                    return field && value ? { label: field.label, value } : null;
                  })
                  .filter(Boolean)
                  .slice(0, 3);
                const statusLabel =
                  product.status === "active"
                    ? lowStock ? "Low stock" : "Available"
                    : "Inactive";

                return (
                  <tr key={product.id}>
                    <td>
                      <strong>{product.name}</strong>
                      <small>{product.brand || "Brand not recorded"} · {product.sku}</small>
                    </td>
                    <td><strong>{product.category || "Uncategorized"}</strong><small>{product.unit}</small></td>
                    <td>
                      <div className="retail-detail-list">
                        {detailEntries.length ? detailEntries.map((entry) => (
                          <span key={entry.label}><b>{entry.label}:</b> {entry.value}</span>
                        )) : <small>No specialist details recorded</small>}
                      </div>
                    </td>
                    <td><strong>{formatNumber(available, 0)} {product.unit}</strong><small>Low at {formatNumber(product.lowStockLevel || 0, 0)}</small></td>
                    <td><strong>{formatCurrency(product.sellingPrice)}</strong></td>
                    <td><strong>{formatCurrency(product.costPrice || 0)}</strong></td>
                    <td>
                      <span className={`retail-status-pill ${product.status !== "active" ? "is-inactive" : lowStock ? "is-low" : "is-active"}`}>
                        {statusLabel}
                      </span>
                    </td>
                    <td>
                      <div className="retail-row-actions">
                        <button type="button" title="Edit product" onClick={() => openEditProduct(product)}><Pencil size={15} /></button>
                        <button type="button" title="Adjust stock" onClick={() => setStockProduct(product)}><PackagePlus size={15} /></button>
                        <button type="button" title={product.status === "active" ? "Deactivate" : "Reactivate"} disabled={Boolean(statusProductId)} onClick={() => changeProductStatus(product)}><Power size={15} /></button>
                        <button type="button" title="Archive product" onClick={() => setArchiveProduct(product)}><Trash2 size={15} /></button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </StickyTableScroll>

        {!filteredProducts.length && !inventoryLoading ? (
          <div className="retail-inventory-empty">
            <RouteIcon size={26} />
            <strong>No {config.recordPlural || `${config.recordLabel.toLowerCase()} records`} found.</strong>
            <p>{hasActiveFilters ? "Change the filters or search terms." : `Use ${config.addLabel} to create the first record.`}</p>
          </div>
        ) : null}

        {filteredProducts.length ? (
          <div className="retail-inventory-pagination">
            <span>Showing {firstVisible}-{lastVisible} of {filteredProducts.length}</span>
            <div>
              <label>
                Rows
                <select value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))}>
                  <option value="10">10</option>
                  <option value="25">25</option>
                  <option value="50">50</option>
                </select>
              </label>
              <button type="button" disabled={safeCurrentPage <= 1} onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}>Previous</button>
              <span>Page {safeCurrentPage} of {totalPages}</span>
              <button type="button" disabled={safeCurrentPage >= totalPages} onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}>Next</button>
            </div>
          </div>
        ) : null}
      </section>

      <RetailProductFormModal
        open={productModalOpen}
        onClose={() => {
          setProductModalOpen(false);
          setEditingProduct(null);
        }}
        onSave={saveProduct}
        product={editingProduct}
        businessType={business.type}
      />

      <Modal
        open={Boolean(stockProduct)}
        onClose={() => {
          if (stockSaving) return;
          setStockProduct(null);
          setStockError("");
        }}
        title={`Adjust ${config.recordLabel} stock`}
        description={stockProduct ? `${stockProduct.name} currently has ${formatNumber(stockProduct.availableStock ?? stockProduct.stock ?? 0, 0)} ${stockProduct.unit || "units"} available.` : ""}
      >
        {stockError ? <div className="form-alert form-alert-error">{stockError}</div> : null}
        <form className="simple-form" onSubmit={submitStockAdjustment}>
          <label>
            Movement type
            <select value={stockForm.type} onChange={(event) => setStockForm((current) => ({ ...current, type: event.target.value }))}>
              <option value="stock_in">New stock received</option>
              <option value="adjustment">Manual correction</option>
              <option value="damage">Damaged stock</option>
              <option value="return">Customer return</option>
            </select>
          </label>
          <label>
            Quantity change
            <input type="number" value={stockForm.quantity} onChange={(event) => setStockForm((current) => ({ ...current, quantity: event.target.value }))} placeholder="Use -2 to reduce stock" required />
          </label>
          <label>
            Reason
            <textarea value={stockForm.reason} onChange={(event) => setStockForm((current) => ({ ...current, reason: event.target.value }))} rows="3" required />
          </label>
          <div className="modal-form-actions">
            <Button variant="secondary" onClick={() => setStockProduct(null)} disabled={stockSaving}>Cancel</Button>
            <Button type="submit" disabled={stockSaving}>{stockSaving ? "Saving..." : "Save adjustment"}</Button>
          </div>
        </form>
      </Modal>

      <Modal
        open={Boolean(archiveProduct)}
        onClose={() => {
          if (archiveSaving) return;
          setArchiveProduct(null);
          setArchiveError("");
        }}
        title={`Archive ${config.recordLabel}`}
        description={archiveProduct ? `Archive ${archiveProduct.name} without deleting its stock or transaction history.` : ""}
      >
        {archiveError ? <div className="form-alert form-alert-error">{archiveError}</div> : null}
        <div className="retail-archive-confirmation">
          <p>The product becomes inactive while StockFlow preserves historical stock movements, sales and reporting references.</p>
          <div className="modal-form-actions">
            <Button variant="secondary" onClick={() => setArchiveProduct(null)} disabled={archiveSaving}>Cancel</Button>
            <button type="button" className="retail-archive-button" onClick={confirmArchive} disabled={archiveSaving}>{archiveSaving ? "Archiving..." : "Archive record"}</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
