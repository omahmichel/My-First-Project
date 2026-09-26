import { useEffect, useMemo, useState } from "react";

import { dealerCatalogForBusinessType } from "../../data/dealerCatalog";
import { retailInventoryConfig } from "../../data/retailInventoryConfig";
import Button from "../ui/Button";
import Modal from "../ui/Modal";

const EMPTY_BASE = {
  productType: "standard",
  name: "",
  sku: "",
  category: "",
  brand: "",
  unit: "piece",
  stock: "",
  costPrice: "",
  sellingPrice: "",
  lowStockLevel: "",
  retailDetails: {},
};

function buildInitialForm(product, config) {
  const unit = config?.units?.[0] || "piece";

  if (!product) {
    return {
      ...EMPTY_BASE,
      unit,
      retailDetails: {},
    };
  }

  return {
    ...EMPTY_BASE,
    ...product,
    productType: "standard",
    unit: product.unit || unit,
    stock: String(product.stock ?? ""),
    costPrice: String(product.costPrice ?? ""),
    sellingPrice: String(product.sellingPrice ?? ""),
    lowStockLevel: String(product.lowStockLevel ?? ""),
    retailDetails:
      product.retailDetails && typeof product.retailDetails === "object"
        ? { ...product.retailDetails }
        : {},
  };
}

export default function RetailProductFormModal({
  open,
  onClose,
  onSave,
  product = null,
  businessType,
}) {
  const config = retailInventoryConfig(businessType);
  const categories = useMemo(
    () => dealerCatalogForBusinessType(businessType),
    [businessType],
  );
  const [form, setForm] = useState(() => buildInitialForm(product, config));
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(buildInitialForm(product, config));
    setError("");
    setIsSaving(false);
  }, [config, open, product]);

  if (!config) return null;

  function handleBaseChange(event) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  }

  function handleDetailChange(field, value) {
    setForm((current) => ({
      ...current,
      retailDetails: {
        ...(current.retailDetails || {}),
        [field]: value,
      },
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (isSaving) return;

    setError("");
    if (!form.name.trim() || !form.category.trim() || !form.sku.trim()) {
      setError("Product name, category and SKU / stock code are required.");
      return;
    }

    setIsSaving(true);
    try {
      await onSave({
        ...form,
        productType: "standard",
        retailDetails: Object.fromEntries(
          Object.entries(form.retailDetails || {}).filter(
            ([, value]) => String(value ?? "").trim() !== "",
          ),
        ),
      });
      onClose();
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setIsSaving(false);
    }
  }

  function handleClose() {
    if (!isSaving) onClose();
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title={product ? `Edit ${config.recordLabel}` : config.addLabel}
      description="Save the core stock fields StockFlow uses everywhere, plus the specialist references used by this business route."
      size="large"
    >
      {error ? <div className="form-alert form-alert-error">{error}</div> : null}

      <form className="product-form retail-product-form" onSubmit={handleSubmit}>
        <div className="form-section-heading">
          <span>Product identity</span>
          <p>Required fields keep inventory, sales and reporting consistent.</p>
        </div>

        <div className="form-grid form-grid-three">
          <label className="form-column-span-two">
            Product name *
            <input
              name="name"
              value={form.name}
              onChange={handleBaseChange}
              placeholder="Product name"
            />
          </label>

          <label>
            {config.skuLabel} *
            <input
              name="sku"
              value={form.sku}
              onChange={handleBaseChange}
              placeholder="Unique stock reference"
            />
          </label>

          <label>
            Category *
            <input
              name="category"
              list={`retail-categories-${businessType}`}
              value={form.category}
              onChange={handleBaseChange}
              placeholder="Choose or type a category"
            />
            <datalist id={`retail-categories-${businessType}`}>
              {categories.map((category) => (
                <option value={category} key={category} />
              ))}
            </datalist>
          </label>

          <label>
            Brand
            <input
              name="brand"
              value={form.brand}
              onChange={handleBaseChange}
              placeholder="Brand / manufacturer"
            />
          </label>

          <label>
            Unit
            <select name="unit" value={form.unit} onChange={handleBaseChange}>
              {config.units.map((unit) => (
                <option value={unit} key={unit}>
                  {unit.charAt(0).toUpperCase() + unit.slice(1)}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="form-section-heading">
          <span>{config.recordLabel} details</span>
          <p>These references make searching and identification faster without changing the shared StockFlow product model.</p>
        </div>

        <div className="form-grid form-grid-three">
          {config.details.map((field) => (
            <label key={field.key}>
              {field.label}
              <input
                type={field.type || "text"}
                step={field.step}
                min={field.type === "number" ? "0" : undefined}
                value={form.retailDetails?.[field.key] ?? ""}
                onChange={(event) =>
                  handleDetailChange(field.key, event.target.value)
                }
                placeholder={field.placeholder || ""}
              />
            </label>
          ))}
        </div>

        <div className="form-section-heading">
          <span>Stock and pricing</span>
          <p>Cost price supports margin reporting. Existing stock is changed through Adjust stock so movement history remains complete.</p>
        </div>

        <div className="form-grid form-grid-three">
          <label>
            {product ? "Current stock (use Adjust stock)" : "Opening stock"}
            <input
              name="stock"
              type="number"
              min="0"
              step="1"
              value={form.stock}
              onChange={handleBaseChange}
              disabled={Boolean(product)}
            />
          </label>

          <label>
            Low-stock level
            <input
              name="lowStockLevel"
              type="number"
              min="0"
              step="1"
              value={form.lowStockLevel}
              onChange={handleBaseChange}
            />
          </label>

          <label>
            Cost price (GHS)
            <input
              name="costPrice"
              type="number"
              min="0"
              step="0.01"
              value={form.costPrice}
              onChange={handleBaseChange}
            />
          </label>

          <label>
            Selling price (GHS)
            <input
              name="sellingPrice"
              type="number"
              min="0"
              step="0.01"
              value={form.sellingPrice}
              onChange={handleBaseChange}
            />
          </label>
        </div>

        <div className="modal-form-actions">
          <Button variant="secondary" onClick={handleClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button type="submit" disabled={isSaving}>
            {isSaving ? "Saving..." : product ? "Save changes" : "Add product"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
