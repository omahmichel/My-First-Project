import { Plus, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { dealerCatalogForBusinessType } from "../../data/dealerCatalog";
import { retailInventoryConfig } from "../../data/retailInventoryConfig";
import {
  retailBrandSuggestions,
  retailSpecificationFields,
} from "../../data/retailProductProfiles";
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

function normalizeAdditionalSpecifications(retailDetails) {
  const rows = retailDetails?.additionalSpecifications;
  if (!Array.isArray(rows)) return [];

  return rows
    .map((item) => ({
      label: String(item?.label ?? ""),
      value: String(item?.value ?? ""),
    }))
    .filter((item) => item.label || item.value);
}

function buildInitialForm(product, config) {
  const unit = config?.units?.[0] || "piece";

  if (!product) {
    return {
      ...EMPTY_BASE,
      unit,
      retailDetails: { additionalSpecifications: [] },
    };
  }

  const details =
    product.retailDetails && typeof product.retailDetails === "object"
      ? { ...product.retailDetails }
      : {};

  return {
    ...EMPTY_BASE,
    ...product,
    productType: "standard",
    unit: product.unit || unit,
    stock: String(product.stock ?? ""),
    costPrice: String(product.costPrice ?? ""),
    sellingPrice: String(product.sellingPrice ?? ""),
    lowStockLevel: String(product.lowStockLevel ?? ""),
    retailDetails: {
      ...details,
      additionalSpecifications: normalizeAdditionalSpecifications(details),
    },
  };
}

function cleanRetailDetails(retailDetails) {
  const source = retailDetails && typeof retailDetails === "object"
    ? retailDetails
    : {};
  const cleaned = {};

  Object.entries(source).forEach(([key, value]) => {
    if (key === "additionalSpecifications") return;
    if (String(value ?? "").trim() !== "") cleaned[key] = value;
  });

  const additionalSpecifications = normalizeAdditionalSpecifications(source)
    .map((item) => ({
      label: item.label.trim(),
      value: item.value.trim(),
    }))
    .filter((item) => item.label && item.value);

  if (additionalSpecifications.length) {
    cleaned.additionalSpecifications = additionalSpecifications;
  }

  return cleaned;
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
  const brandSuggestions = useMemo(
    () => retailBrandSuggestions(businessType),
    [businessType],
  );
  const [form, setForm] = useState(() => buildInitialForm(product, config));
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const specificationFields = useMemo(
    () => retailSpecificationFields(businessType, form.category),
    [businessType, form.category],
  );

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

  function addSpecificationRow() {
    setForm((current) => ({
      ...current,
      retailDetails: {
        ...(current.retailDetails || {}),
        additionalSpecifications: [
          ...normalizeAdditionalSpecifications(current.retailDetails),
          { label: "", value: "" },
        ],
      },
    }));
  }

  function updateSpecificationRow(index, field, value) {
    setForm((current) => {
      const rows = normalizeAdditionalSpecifications(current.retailDetails);
      const nextRows = rows.map((row, rowIndex) =>
        rowIndex === index ? { ...row, [field]: value } : row,
      );

      return {
        ...current,
        retailDetails: {
          ...(current.retailDetails || {}),
          additionalSpecifications: nextRows,
        },
      };
    });
  }

  function removeSpecificationRow(index) {
    setForm((current) => {
      const nextRows = normalizeAdditionalSpecifications(current.retailDetails)
        .filter((_, rowIndex) => rowIndex !== index);

      return {
        ...current,
        retailDetails: {
          ...(current.retailDetails || {}),
          additionalSpecifications: nextRows,
        },
      };
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (isSaving) return;

    setError("");
    if (
      !form.name.trim() ||
      !form.category.trim() ||
      !form.brand.trim() ||
      !form.sku.trim()
    ) {
      setError(
        "Product name, category, brand and SKU / stock code are required. Use Generic / Unbranded when a product has no formal brand.",
      );
      return;
    }

    setIsSaving(true);
    try {
      await onSave({
        ...form,
        productType: "standard",
        brand: form.brand.trim(),
        category: form.category.trim(),
        retailDetails: cleanRetailDetails(form.retailDetails),
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

  const additionalRows = normalizeAdditionalSpecifications(form.retailDetails);

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title={product ? `Edit ${config.recordLabel}` : config.addLabel}
      description="Classify the item first, then record the specifications that distinguish this exact sellable item from other brands, models, sizes and variants."
      size="large"
    >
      {error ? <div className="form-alert form-alert-error">{error}</div> : null}

      <form className="product-form retail-product-form" onSubmit={handleSubmit}>
        <div className="form-section-heading">
          <span>Product classification</span>
          <p>Category and brand are used to keep different product families visibly separated throughout StockFlow.</p>
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
              autoComplete="off"
            />
            <datalist id={`retail-categories-${businessType}`}>
              {categories.map((category) => (
                <option value={category} key={category} />
              ))}
            </datalist>
            <small className="retail-field-help">Choose the closest category so StockFlow can show the correct specification fields.</small>
          </label>

          <label>
            Brand / manufacturer *
            <input
              name="brand"
              list={`retail-brands-${businessType}`}
              value={form.brand}
              onChange={handleBaseChange}
              placeholder="Apple / Samsung / Generic / Unbranded"
              autoComplete="off"
            />
            <datalist id={`retail-brands-${businessType}`}>
              {brandSuggestions.map((brand) => (
                <option value={brand} key={brand} />
              ))}
            </datalist>
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

        <div className="form-section-heading retail-specification-heading">
          <span>{form.category ? `${form.category} specifications` : `${config.recordLabel} specifications`}</span>
          <p>
            {form.category
              ? "These fields change with the selected category so phones, laptops, spare parts, provisions, electrical items and beauty products are described correctly."
              : "Select a category first to load the most relevant specification fields."}
          </p>
        </div>

        {specificationFields.length ? (
          <div className="form-grid form-grid-three retail-specification-grid">
            {specificationFields.map((field) => (
              <label key={field.key}>
                {field.label}
                {field.options ? (
                  <select
                    value={form.retailDetails?.[field.key] ?? ""}
                    onChange={(event) =>
                      handleDetailChange(field.key, event.target.value)
                    }
                  >
                    <option value="">Select</option>
                    {field.options.map((option) => (
                      <option value={option} key={option}>{option}</option>
                    ))}
                  </select>
                ) : (
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
                )}
              </label>
            ))}
          </div>
        ) : (
          <div className="retail-category-prompt">
            Select or enter a category above to load detailed product specifications.
          </div>
        )}

        <div className="retail-additional-specifications">
          <div className="retail-additional-specifications-heading">
            <div>
              <strong>Additional specifications</strong>
              <p>Add any important specification that is not already covered. This keeps StockFlow flexible for new products and models.</p>
            </div>
            <button type="button" onClick={addSpecificationRow}>
              <Plus size={15} /> Add specification
            </button>
          </div>

          {additionalRows.length ? (
            <div className="retail-additional-specification-list">
              {additionalRows.map((row, index) => (
                <div className="retail-additional-specification-row" key={`additional-${index}`}>
                  <input
                    value={row.label}
                    onChange={(event) => updateSpecificationRow(index, "label", event.target.value)}
                    placeholder="Specification name e.g. Face ID"
                    aria-label={`Additional specification ${index + 1} name`}
                  />
                  <input
                    value={row.value}
                    onChange={(event) => updateSpecificationRow(index, "value", event.target.value)}
                    placeholder="Value e.g. Supported"
                    aria-label={`Additional specification ${index + 1} value`}
                  />
                  <button
                    type="button"
                    className="retail-remove-specification"
                    onClick={() => removeSpecificationRow(index)}
                    aria-label={`Remove additional specification ${index + 1}`}
                    title="Remove specification"
                  >
                    <X size={15} />
                  </button>
                </div>
              ))}
            </div>
          ) : null}
        </div>

        <div className="form-section-heading">
          <span>Stock and pricing</span>
          <p>Each distinct model, size, capacity, shade or sellable variant remains its own stock record and therefore keeps its own price and quantity.</p>
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
