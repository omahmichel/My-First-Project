import { Boxes, Filter, PackagePlus, Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import StickyTableScroll from "../../components/ui/StickyTableScroll";
import ProductFormModal from "../../components/products/ProductFormModal";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import PageHeader from "../../components/ui/PageHeader";
import { useStore } from "../../context/StoreContext";
import { formatCurrency } from "../../utils/formatters";

import "../../styles/products-control-board.css";

export default function ProductsPage() {
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
  const [status, setStatus] = useState("all");
  const [productModalOpen, setProductModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [stockProduct, setStockProduct] = useState(null);
  const [deleteProductTarget, setDeleteProductTarget] = useState(null);
  const [deleteError, setDeleteError] = useState("");
  const [stockForm, setStockForm] = useState({ quantity: "", reason: "New stock received", type: "stock_in" });
  const [stockError, setStockError] = useState("");
  const [inventoryActionError, setInventoryActionError] = useState("");
  const [statusProductId, setStatusProductId] = useState(null);
  const [stockSaving, setStockSaving] = useState(false);
  const [deleteSaving, setDeleteSaving] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const categories = [...new Set(products.map((product) => product.category))].sort();
  const filteredProducts = useMemo(() => {
    const query = search.trim().toLowerCase();
    return products.filter((product) => {
      const matchesSearch = !query || [product.name, product.sku, product.designCode, product.styleCode, product.brand]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(query));
      const matchesCategory = category === "all" || product.category === category;
      const matchesStatus = status === "all" || product.status === status;
      return matchesSearch && matchesCategory && matchesStatus;
    });
  }, [category, products, search, status]);

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
  }, [search, category, status, pageSize]);

  // Keeps the selected page inside the available page range.
  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  async function saveProduct(form) {
    setInventoryActionError("");

    if (editingProduct) {
      return updateProduct(editingProduct.id, form);
    }

    return addProduct(form);
  }

  // Archives a product without removing its historical database record.
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

  return (
    <div className="page-stack products-control-page">
      <PageHeader
        eyebrow="Inventory"
        title="Products"
        description="Manage every product, price, unit and stock level from one controlled list."
        actions={<Button onClick={() => { setEditingProduct(null); setProductModalOpen(true); }}><PackagePlus size={18} />

      {inventoryLoading ? (
        <div className="form-alert">Loading real inventory...</div>
      ) : null}

      {inventoryError || inventoryActionError ? (
        <div className="form-alert form-alert-error">
          {inventoryActionError || inventoryError}
        </div>
      ) : null} Add product</Button>}
      />

      <section className="inventory-summary-row">
        <article><span><Boxes size={20} /></span><div><strong>{products.length}</strong><small>Total products</small></div></article>
        <article><span><Filter size={20} /></span><div><strong>{categories.length}</strong><small>Categories</small></div></article>
        <article><span><SlidersHorizontal size={20} /></span><div><strong>{products.filter((product) => Number(product.availableStock ?? product.stock ?? 0) <= Number(product.lowStockLevel || 0)).length}</strong><small>Low-stock products</small></div></article>
      </section>

      <section className="panel-card">
        <div className="table-toolbar">
          <label className="table-search"><Search size={18} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, SKU, design or brand..." /></label>
          <div className="table-filter-group">
            <select value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">All categories</option>{categories.map((item) => <option key={item}>{item}</option>)}</select>
            <select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option></select>
          </div>
        </div>

        <StickyTableScroll>
<table className="data-table products-table">
            <thead><tr><th>Product</th><th>Category</th><th>Unit</th><th>Stock</th><th>Cost price</th><th>Selling price</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>
              {paginatedProducts.map((product) => {
                const availableStock = Number(
                  product.availableStock ?? product.stock ?? 0,
                );
                const lowStock =
                  availableStock <= Number(product.lowStockLevel || 0);
                return (
                  <tr key={product.id}>
                    <td>
                      <div className="table-product-cell">
                        <span className={`product-visual-small ${product.imageStyle || "product-generic"}`} />
                        <div><strong>{product.name}</strong><small>{product.designCode ? `Design ${product.designCode} · ` : product.styleCode ? `Style ${product.styleCode} · ` : ""}{product.sku}</small></div>
                      </div>
                    </td>
                    <td>{product.category}</td>
                    <td className="capitalize-text">{product.unit}</td>
                    <td>
                      <strong className={lowStock ? "danger-text" : ""}>
                        {availableStock} {product.unit}(s)
                      </strong>
                      {product.productType === "tile" ? (
                        <small>{product.loosePieces || 0} loose piece(s)</small>
                      ) : null}
                    </td>
                    <td>{formatCurrency(product.costPrice)}</td>
                    <td><strong>{formatCurrency(product.sellingPrice)}</strong></td>
                    <td><Badge tone={product.status === "active" ? (lowStock ? "warning" : "success") : "neutral"}>{product.status === "active" ? (lowStock ? "Low stock" : "Active") : "Inactive"}</Badge></td>
                    <td>
                      <div className="table-action-group">
                        <button type="button" onClick={() => { setEditingProduct(product); setProductModalOpen(true); }}>Edit</button>
                        <button
                          type="button"
                          onClick={() => setStockProduct(product)}
                          disabled={product.status !== "active"}
                        >
                          Stock
                        </button>
                        <button
                          type="button"
                          onClick={() => changeProductStatus(product)}
                          disabled={Boolean(statusProductId)}
                        >
                          {statusProductId === product.id
                            ? "Updating..."
                            : product.status === "active"
                              ? "Deactivate"
                              : "Activate"}
                        </button>
                        <button
                          type="button"
                          className="product-delete-action"
                          onClick={() => {
                            setDeleteError("");
                            setDeleteProductTarget(product);
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </StickyTableScroll>

        <div className="products-pagination">
          <div className="products-pagination-summary">
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

          <div className="products-pagination-controls">
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

      <ProductFormModal open={productModalOpen} onClose={() => setProductModalOpen(false)} onSave={saveProduct} product={editingProduct} />

      <Modal
        open={Boolean(deleteProductTarget)}
        onClose={() => {
          if (deleteSaving) return;
          setDeleteProductTarget(null);
          setDeleteError("");
        }}
        title="Archive product"
        description={
          deleteProductTarget
            ? `Archive ${deleteProductTarget.name} without deleting its stock history.`
            : ""
        }
      >
        {deleteError ? (
          <div className="form-alert form-alert-error">{deleteError}</div>
        ) : null}

        <div className="product-delete-confirmation">
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
              className="product-delete-confirm-button"
              onClick={confirmProductDeletion}
              disabled={deleteSaving}
            >
              {deleteSaving ? "Archiving..." : "Archive product"}
            </button>
          </div>
        </div>
      </Modal>

      <Modal open={Boolean(stockProduct)} onClose={() => { if (!stockSaving) setStockProduct(null); }} title="Adjust stock" description={stockProduct ? `${stockProduct.name} currently has ${stockProduct.stock} ${stockProduct.unit}(s).` : ""}>
        {stockError ? <div className="form-alert form-alert-error">{stockError}</div> : null}
        <form className="simple-form" onSubmit={submitStockAdjustment}>
          <label>Movement type<select value={stockForm.type} onChange={(event) => setStockForm((current) => ({ ...current, type: event.target.value }))}><option value="stock_in">New stock received</option><option value="adjustment">Manual correction</option><option value="damage">Damaged stock</option><option value="return">Customer return</option></select></label>
          <label>Quantity change<input type="number" value={stockForm.quantity} onChange={(event) => setStockForm((current) => ({ ...current, quantity: event.target.value }))} placeholder="Use -2 to reduce stock" required /></label>
          <label>Reason<textarea value={stockForm.reason} onChange={(event) => setStockForm((current) => ({ ...current, reason: event.target.value }))} rows="3" required /></label>
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
    </div>
  );
}
