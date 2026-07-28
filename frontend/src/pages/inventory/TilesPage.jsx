import {
  AlertTriangle,
  Boxes,
  FilterX,
  PackageOpen,
  PackagePlus,
  Search,
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
import "../../styles/tile-inventory-records.css";

// Returns the operational stock state used by filters and badges.
function getTileStockState(tile) {
  if (tile.status !== "active") return "inactive";
  if (Number(tile.stock) <= 0) return "out_of_stock";
  if (Number(tile.stock) <= Number(tile.lowStockLevel || 0)) return "low_stock";
  return "available";
}

// Keeps stock labels and badge colours consistent across the page.
function getTileStatusPresentation(tile) {
  const state = getTileStockState(tile);

  if (state === "inactive") return { label: "Inactive", tone: "neutral" };
  if (state === "out_of_stock") return { label: "Out of stock", tone: "danger" };
  if (state === "low_stock") return { label: "Low stock", tone: "warning" };
  return { label: "Available", tone: "success" };
}

export default function TilesPage() {
  const {
    products,
    addProduct,
    updateProduct,
    toggleProductStatus,
    adjustStock,
  } = useStore();

  const [search, setSearch] = useState("");
  const [brand, setBrand] = useState("all");
  const [size, setSize] = useState("all");
  const [finish, setFinish] = useState("all");
  const [stockState, setStockState] = useState("all");
  const [productModalOpen, setProductModalOpen] = useState(false);
  const [editingTile, setEditingTile] = useState(null);
  const [stockTile, setStockTile] = useState(null);
  const [stockForm, setStockForm] = useState({
    quantity: "",
    reason: "New tile stock received",
    type: "stock_in",
  });
  const [stockError, setStockError] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Limits this specialist page to tile records from the current business.
  const tiles = useMemo(
    () => products.filter((product) => product.productType === "tile"),
    [products],
  );

  // Builds filter values from the shop's existing records.
  const brands = useMemo(
    () => [...new Set(tiles.map((tile) => tile.brand).filter(Boolean))].sort(),
    [tiles],
  );
 // Combines standard tile sizes with sizes already stored in inventory records.
const sizes = useMemo(() => {
  const standardSizes = [
    "25 × 40 cm",
    "30 × 30 cm",
    "33 × 33 cm",
    "50 × 50 cm",
    "60 × 120 cm",
  ];

  const recordedSizes = tiles
    .map((tile) => tile.size)
    .filter(Boolean);

  return [...new Set([...standardSizes, ...recordedSizes])].sort();
}, [tiles]);

// Combines standard finishes with finishes already stored in inventory records.
const finishes = useMemo(() => {
  const standardFinishes = [
    "Porcelain",
    "Rough",
    "Glossy",
  ];

  const recordedFinishes = tiles
    .map((tile) => tile.finish)
    .filter(Boolean);

  return [...new Set([...standardFinishes, ...recordedFinishes])].sort();
}, [tiles]);

  // Applies text search and operational filters to the records table.
  const filteredTiles = useMemo(() => {
    const query = search.trim().toLowerCase();

    return tiles.filter((tile) => {
      const searchableValues = [
        tile.name,
        tile.sku,
        tile.designCode,
        tile.brand,
        tile.size,
        tile.finish,
        tile.color,
        tile.batchNumber,
      ];

      const matchesSearch =
        !query ||
        searchableValues
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(query));
      const matchesBrand = brand === "all" || tile.brand === brand;
      const matchesSize = size === "all" || tile.size === size;
      const matchesFinish = finish === "all" || tile.finish === finish;
      const matchesStockState =
        stockState === "all" || getTileStockState(tile) === stockState;

      return (
        matchesSearch &&
        matchesBrand &&
        matchesSize &&
        matchesFinish &&
        matchesStockState
      );
    });
  }, [brand, finish, search, size, stockState, tiles]);

  const totalPages = Math.max(
    1,
    Math.ceil(filteredTiles.length / pageSize),
  );

  const safeCurrentPage = Math.min(currentPage, totalPages);

  const paginatedTiles = useMemo(() => {
    const startIndex = (safeCurrentPage - 1) * pageSize;

    return filteredTiles.slice(startIndex, startIndex + pageSize);
  }, [filteredTiles, pageSize, safeCurrentPage]);

  const firstVisibleRecord = filteredTiles.length
    ? (safeCurrentPage - 1) * pageSize + 1
    : 0;

  const lastVisibleRecord = filteredTiles.length
    ? firstVisibleRecord + paginatedTiles.length - 1
    : 0;

  // Returns to page one whenever search, filters or page size change.
  useEffect(() => {
    setCurrentPage(1);
  }, [search, brand, size, finish, stockState, pageSize]);

  // Keeps the selected page inside the available page range.
  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  const totalBoxes = tiles.reduce(
    (sum, tile) => sum + Number(tile.stock || 0),
    0,
  );
  const totalLoosePieces = tiles.reduce(
    (sum, tile) => sum + Number(tile.loosePieces || 0),
    0,
  );
  const lowStockRecords = tiles.filter(
    (tile) =>
      tile.status === "active" &&
      Number(tile.stock) <= Number(tile.lowStockLevel || 0),
  ).length;
  const hasActiveFilters =
    search.trim() ||
    brand !== "all" ||
    size !== "all" ||
    finish !== "all" ||
    stockState !== "all";

  // Creates or updates a tile while preserving the specialist product type.
  function saveTile(form) {
    const tileForm = { ...form, productType: "tile" };

    if (editingTile) updateProduct(editingTile.id, tileForm);
    else addProduct(tileForm);
  }

  // Resets every search and filter control in one action.
  function clearFilters() {
    setSearch("");
    setBrand("all");
    setSize("all");
    setFinish("all");
    setStockState("all");
  }

  // Records full-box stock movements through the existing workflow.
  function submitStockAdjustment(event) {
    event.preventDefault();
    setStockError("");

    try {
      adjustStock({
        productId: stockTile.id,
        quantity: Number(stockForm.quantity),
        type: stockForm.type,
        reason: stockForm.reason,
      });
      setStockTile(null);
      setStockForm({
        quantity: "",
        reason: "New tile stock received",
        type: "stock_in",
      });
    } catch (error) {
      setStockError(error.message);
    }
  }

  return (
    <div className="page-stack tile-records-page">
      <PageHeader
        eyebrow="Building materials inventory"
        title="Tile inventory"
        description="Record, search and manage tile details, quantities, prices and stock status from one operational list."
        actions={
          <Button
            onClick={() => {
              setEditingTile(null);
              setProductModalOpen(true);
            }}
          >
            <PackagePlus size={18} /> Add tile record
          </Button>
        }
      />

      <section className="tile-records-summary" aria-label="Tile inventory summary">
        <article>
          <span><Boxes size={20} /></span>
          <div><strong>{tiles.length}</strong><small>Tile records</small></div>
        </article>
        <article>
          <span><PackageOpen size={20} /></span>
          <div><strong>{formatNumber(totalBoxes, 0)}</strong><small>Boxes in stock</small></div>
        </article>
        <article>
          <span><PackageOpen size={20} /></span>
          <div><strong>{formatNumber(totalLoosePieces, 0)}</strong><small>Loose pieces</small></div>
        </article>
        <article>
          <span><AlertTriangle size={20} /></span>
          <div><strong>{lowStockRecords}</strong><small>Low-stock records</small></div>
        </article>
      </section>

      <section className="panel-card tile-records-panel">
        <div className="tile-records-toolbar">
          <div className="tile-records-search-row">
            <label className="table-search tile-records-search">
              <Search size={18} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search product, design code, SKU, colour or batch..."
              />
            </label>

            <div className="tile-records-result-group">
              <span className="tile-records-result-count">
                {filteredTiles.length} of {tiles.length} record(s)
              </span>
              {hasActiveFilters ? (
                <button
                  className="tile-clear-filters"
                  type="button"
                  onClick={clearFilters}
                >
                  <FilterX size={16} /> Clear filters
                </button>
              ) : null}
            </div>
          </div>

          <div className="tile-records-filters" aria-label="Tile inventory filters">
            <select value={brand} onChange={(event) => setBrand(event.target.value)}>
              <option value="all">All brands</option>
              {brands.map((item) => <option key={item}>{item}</option>)}
            </select>

            <select value={size} onChange={(event) => setSize(event.target.value)}>
              <option value="all">All sizes</option>
              {sizes.map((item) => <option key={item}>{item}</option>)}
            </select>

            <select value={finish} onChange={(event) => setFinish(event.target.value)}>
              <option value="all">All finishes</option>
              {finishes.map((item) => <option key={item}>{item}</option>)}
            </select>

            <select
              value={stockState}
              onChange={(event) => setStockState(event.target.value)}
            >
              <option value="all">All stock statuses</option>
              <option value="available">Available</option>
              <option value="low_stock">Low stock</option>
              <option value="out_of_stock">Out of stock</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
        </div>

        <StickyTableScroll className="tile-records-table-wrapper">
<table className="data-table tile-records-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Design / batch</th>
                <th>Specifications</th>
                <th>Stock</th>
                <th>Pricing</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {filteredTiles.length ? (
                paginatedTiles.map((tile) => {
                  const statusPresentation = getTileStatusPresentation(tile);
                  const stockStateValue = getTileStockState(tile);
                  const lowStock = ["low_stock", "out_of_stock"].includes(
                    stockStateValue,
                  );

                  return (
                    <tr key={tile.id}>
                      <td data-label="Product">
                        <div className="tile-record-product">
                          <strong>{tile.name}</strong>
                          <span>{tile.brand || "Brand not recorded"}</span>
                          <small>SKU: {tile.sku || "Not assigned"}</small>
                        </div>
                      </td>

                      <td data-label="Design / batch">
                        <div className="tile-record-stack">
                          <strong>{tile.designCode || "Not recorded"}</strong>
                          <small>Batch: {tile.batchNumber || "Not recorded"}</small>
                        </div>
                      </td>

                      <td data-label="Specifications">
                        <div className="tile-specification-list">
                          <span><small>Size</small><strong>{tile.size || "Not recorded"}</strong></span>
                          <span><small>Finish</small><strong>{tile.finish || "Not recorded"}</strong></span>
                          <span><small>Colour</small><strong>{tile.color || "Not recorded"}</strong></span>
                        </div>
                      </td>

                      <td data-label="Stock">
                        <div className="tile-record-stock">
                          <strong className={lowStock ? "danger-text" : ""}>
                            {formatNumber(Number(tile.stock || 0), 0)} boxes
                          </strong>
                          <small>{formatNumber(Number(tile.loosePieces || 0), 0)} loose piece(s)</small>
                          <small>{formatNumber(Number(tile.piecesPerBox || 0), 0)} piece(s) per box</small>
                        </div>
                      </td>

                      <td data-label="Pricing">
                        <div className="tile-record-pricing">
                          <strong>{formatCurrency(tile.sellingPrice)}</strong>
                          <span>per box</span>
                          <small>Cost: {formatCurrency(tile.costPrice)}</small>
                        </div>
                      </td>

                      <td data-label="Status">
                        <Badge tone={statusPresentation.tone}>
                          {statusPresentation.label}
                        </Badge>
                      </td>

                      <td data-label="Actions">
                        <div className="tile-record-actions">
                          <button
                            type="button"
                            onClick={() => {
                              setEditingTile(tile);
                              setProductModalOpen(true);
                            }}
                          >
                            Edit
                          </button>
                          <button type="button" onClick={() => setStockTile(tile)}>
                            Adjust stock
                          </button>
                          <button
                            className="tile-record-secondary-action"
                            type="button"
                            onClick={() => toggleProductStatus(tile.id)}
                          >
                            {tile.status === "active" ? "Deactivate" : "Activate"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td className="tile-records-empty" colSpan="7">
                    <strong>No tile records found</strong>
                    <span>Change the search or filters to view matching records.</span>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </StickyTableScroll>

        <div className="tile-records-pagination">
          <div className="tile-pagination-summary">
            <span>
              Showing {firstVisibleRecord}-{lastVisibleRecord} of{" "}
              {filteredTiles.length} records
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

          <div className="tile-pagination-controls">
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
          setEditingTile(null);
        }}
        onSave={saveTile}
        product={editingTile}
        defaultType="tile"
      />

      <Modal
        open={Boolean(stockTile)}
        onClose={() => setStockTile(null)}
        title="Adjust tile box stock"
        description={
          stockTile
            ? `${stockTile.name} currently has ${stockTile.stock} full box(es) and ${stockTile.loosePieces || 0} loose piece(s).`
            : ""
        }
      >
        {stockError ? <div className="form-alert form-alert-error">{stockError}</div> : null}

        <form className="simple-form" onSubmit={submitStockAdjustment}>
          <label>
            Movement type
            <select
              value={stockForm.type}
              onChange={(event) =>
                setStockForm((current) => ({ ...current, type: event.target.value }))
              }
            >
              <option value="stock_in">New stock received</option>
              <option value="adjustment">Manual correction</option>
              <option value="damage">Damaged stock</option>
              <option value="return">Customer return</option>
            </select>
          </label>

          <label>
            Box quantity change
            <input
              type="number"
              value={stockForm.quantity}
              onChange={(event) =>
                setStockForm((current) => ({
                  ...current,
                  quantity: event.target.value,
                }))
              }
              placeholder="Use -2 to reduce boxes"
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
            <Button variant="secondary" onClick={() => setStockTile(null)}>
              Cancel
            </Button>
            <Button type="submit">Save adjustment</Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
