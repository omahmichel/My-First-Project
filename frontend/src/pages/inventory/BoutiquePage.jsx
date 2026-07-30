import {
  Boxes,
  Filter,
  PackagePlus,
  Search,
  Shirt,
  SlidersHorizontal,
  Tags,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import StickyTableScroll from "../../components/ui/StickyTableScroll";
import ProductFormModal from "../../components/products/ProductFormModal";
import Badge from "../../components/ui/Badge";
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

  const totalUnits = fashionProducts.reduce(
    (sum, product) => sum + Number(product.stock || 0),
    0,
  );

  const lowStockCount = fashionProducts.filter(
    (product) =>
      product.status === "active" &&
      Number(product.stock || 0) <= Number(product.lowStockLevel || 0),
  ).length;

  const inventoryValue = fashionProducts.reduce(
    (sum, product) =>
      sum + Number(product.stock || 0) * Number(product.costPrice || 0),
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
    <div className="page-stack boutique-records-page">
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
            <strong>{formatNumber(totalUnits, 0)}</strong>
            <small>Total units in stock</small>
          </div>
        </article>

        <article>
          <span><SlidersHorizontal size={20} /></span>
          <div>
            <strong>{lowStockCount}</strong>
            <small>Low-stock records</small>
          </div>
        </article>

        <article>
          <span><Tags size={20} /></span>
          <div>
            <strong>{formatCurrency(inventoryValue)}</strong>
            <small>Estimated stock value</small>
          </div>
        </article>
      </section>

      <section className="panel-card boutique-records-panel">
        <div className="boutique-records-toolbar">
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

        <StickyTableScroll className="boutique-records-table-wrapper">
<table className="data-table boutique-records-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Style / category</th>
                <th>Size / colour</th>
                <th>Stock</th>
                <th>Pricing</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {paginatedProducts.map((product) => {
                const lowStock =
                  Number(product.stock || 0) <=
                  Number(product.lowStockLevel || 0);

                const variantSummary = product.variants?.length
                  ? `${product.variants.length} variant(s)`
                  : "No detailed variants";

                return (
                  <tr key={product.id}>
                    <td data-label="Product">
                      <div className="boutique-record-product">
                        <span className="boutique-record-marker">
                          <Shirt size={17} />
                        </span>

                        <div>
                          <strong>{product.name}</strong>
                          <small>{product.brand || "Brand not recorded"}</small>
                          <small>SKU: {product.sku || "Not recorded"}</small>
                        </div>
                      </div>
                    </td>

                    <td data-label="Style / category">
                      <div className="boutique-record-stack">
                        <strong>{product.styleCode || "Not recorded"}</strong>
                        <small>{product.category || "Uncategorized"}</small>
                      </div>
                    </td>

                    <td data-label="Size / colour">
                      <div className="boutique-specification-list">
                        <span>
                          <small>Size</small>
                          <strong>{product.size || "Not recorded"}</strong>
                        </span>
                        <span>
                          <small>Colour</small>
                          <strong>{product.color || "Not recorded"}</strong>
                        </span>
                        <span className="boutique-variant-summary">
                          <small>Variants</small>
                          <strong>{variantSummary}</strong>
                        </span>
                      </div>
                    </td>

                    <td data-label="Stock">
                      <div className="boutique-record-stock">
                        <strong className={lowStock ? "danger-text" : ""}>
                          {formatNumber(product.stock || 0, 0)} unit(s)
                        </strong>
                        <small>
                          Alert at {formatNumber(product.lowStockLevel || 0, 0)}
                        </small>
                      </div>
                    </td>

                    <td data-label="Pricing">
                      <div className="boutique-record-pricing">
                        <strong>{formatCurrency(product.sellingPrice)}</strong>
                        <span>Selling price</span>
                        <small>Cost: {formatCurrency(product.costPrice)}</small>
                      </div>
                    </td>

                    <td data-label="Status">
                      <Badge
                        tone={
                          product.status === "active"
                            ? lowStock
                              ? "warning"
                              : "success"
                            : "neutral"
                        }
                      >
                        {product.status === "active"
                          ? lowStock
                            ? "Low stock"
                            : "Available"
                          : "Inactive"}
                      </Badge>
                    </td>

                    <td data-label="Actions">
                      <div className="boutique-record-actions">
                        <button
                          type="button"
                          onClick={() => openEditProductModal(product)}
                        >
                          Edit
                        </button>

                        <button
                          type="button"
                          onClick={() => setStockProduct(product)}
                          disabled={product.status !== "active"}
                        >
                          Adjust stock
                        </button>

                        <button
                          type="button"
                          className="boutique-record-secondary-action"
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
                          className="boutique-record-delete-action"
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

              {!filteredProducts.length ? (
                <tr>
                  <td className="boutique-records-empty" colSpan="7">
                    <strong>No boutique records found.</strong>
                    <span>Change the filters or add a new boutique record.</span>
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
