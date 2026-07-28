import { useEffect, useState } from "react";

import Button from "../ui/Button";
import Modal from "../ui/Modal";

const emptyForm = {
  businessType: "building_materials",
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
  designCode: "",
  size: "",
  finish: "",
  color: "",
  batchNumber: "",
  piecesPerBox: "",
  sqmPerBox: "",
  loosePieces: "",
  styleCode: "",
};

export default function ProductFormModal({ open, onClose, onSave, product = null, defaultType = "standard" }) {
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setForm(
      product
        ? {
            ...emptyForm,
            ...product,
            stock: String(product.stock ?? ""),
            costPrice: String(product.costPrice ?? ""),
            sellingPrice: String(product.sellingPrice ?? ""),
            lowStockLevel: String(product.lowStockLevel ?? ""),
            loosePieces: String(product.loosePieces ?? ""),
            piecesPerBox: String(product.piecesPerBox ?? ""),
            sqmPerBox: String(product.sqmPerBox ?? ""),
          }
        : { ...emptyForm, productType: defaultType, businessType: defaultType === "fashion" ? "boutique" : "building_materials", unit: defaultType === "tile" ? "box" : "piece" },
    );
    setError("");
  }, [defaultType, open, product]);

  function handleChange(event) {
    const { name, value } = event.target;
    setForm((current) => ({
      ...current,
      [name]: value,
      ...(name === "productType"
        ? { businessType: value === "fashion" ? "boutique" : "building_materials", unit: value === "tile" ? "box" : value === "fashion" ? "piece" : current.unit }
        : {}),
    }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    setError("");

    if (!form.name.trim() || !form.category.trim() || !form.sku.trim()) {
      setError("Product name, category and SKU are required.");
      return;
    }

    if (form.productType === "tile" && !form.designCode.trim()) {
      setError("A tile design number or design code is required.");
      return;
    }

    onSave(form);
    onClose();
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={product ? "Edit product" : "Add a new product"}
      description="Enter the information needed for stock, sales and reporting."
      size="large"
    >
      {error ? <div className="form-alert form-alert-error">{error}</div> : null}

      <form className="product-form" onSubmit={handleSubmit}>
        <div className="form-section-heading">
          <span>General information</span>
          <p>Fields marked with an asterisk are required.</p>
        </div>

        <div className="form-grid form-grid-three">
          <label>
            Product type
            <select name="productType" value={form.productType} onChange={handleChange}>
              <option value="standard">Standard product</option>
              <option value="tile">Tile product</option>
              <option value="fashion">Boutique product</option>
            </select>
          </label>
          <label className="form-column-span-two">
            Product name *
            <input name="name" value={form.name} onChange={handleChange} placeholder="Product name" />
          </label>
          <label>
            SKU / stock code *
            <input name="sku" value={form.sku} onChange={handleChange} placeholder="Example: TILE-6052" />
          </label>
          <label>
            Category *
            <input name="category" value={form.category} onChange={handleChange} placeholder="Tiles, Cement, Dresses..." />
          </label>
          <label>
            Brand
            <input name="brand" value={form.brand} onChange={handleChange} placeholder="Brand name" />
          </label>
        </div>

        {form.productType === "tile" ? (
          <>
            <div className="form-section-heading">
              <span>Tile details</span>
              <p>Design and box information help staff identify the correct tile.</p>
            </div>
            <div className="form-grid form-grid-three">
              <label>
                Design number / code *
                <input name="designCode" value={form.designCode} onChange={handleChange} placeholder="6052" />
              </label>
              <label>
                Tile size
                <select name="size" value={form.size} onChange={handleChange}>
                  <option value="">Select tile size</option>
                  <option value="25 × 40 cm">25 × 40 cm</option>
                  <option value="30 × 30 cm">30 × 30 cm</option>
                  <option value="30 × 60 cm">30 × 60 cm</option>
                  <option value="33 × 33 cm">33 × 33 cm</option>
                  <option value="40 × 40 cm">40 × 40 cm</option>
                  <option value="50 × 50 cm">50 × 50 cm</option>
                  <option value="60 × 60 cm">60 × 60 cm</option>
                  <option value="60 × 120 cm">60 × 120 cm</option>
                </select>
              </label>
              <label>
                Finish
                <select name="finish" value={form.finish} onChange={handleChange}>
                  <option value="">Select finish</option>
                  <option>Porcelain</option>
                  <option>Glossy</option>
                  <option>Matte</option>
                  <option>Textured</option>
                  <option>Polished</option>
                  <option>Rough</option>
                </select>
              </label>
              <label>
                Colour
                <input name="color" value={form.color} onChange={handleChange} placeholder="Cream and Gold" />
              </label>
              <label>
                Batch / lot number
                <input name="batchNumber" value={form.batchNumber} onChange={handleChange} placeholder="RC-2607-A" />
              </label>
              <label>
                Pieces per box
                <input name="piecesPerBox" type="number" min="0" step="1" value={form.piecesPerBox} onChange={handleChange} />
              </label>
              <label>
                Square metres per box
                <input name="sqmPerBox" type="number" min="0" step="0.01" value={form.sqmPerBox} onChange={handleChange} />
              </label>
              <label>
                Loose pieces
                <input name="loosePieces" type="number" min="0" step="1" value={form.loosePieces} onChange={handleChange} />
              </label>
            </div>
          </>
        ) : null}

        {form.productType === "fashion" ? (
          <>
            <div className="form-section-heading">
              <span>Boutique details</span>
              <p>Variants will be managed in more detail during the backend phase.</p>
            </div>
            <div className="form-grid form-grid-three">
              <label>
                Style code
                <input name="styleCode" value={form.styleCode} onChange={handleChange} placeholder="ADA-220" />
              </label>
              <label>
                Main colour
                <input name="color" value={form.color} onChange={handleChange} placeholder="Olive" />
              </label>
              <label>
                Size range
                <input name="size" value={form.size} onChange={handleChange} placeholder="S, M, L, XL" />
              </label>
            </div>
          </>
        ) : null}

        <div className="form-section-heading">
          <span>Stock and pricing</span>
          <p>Cost price is used to estimate gross profit.</p>
        </div>
        <div className="form-grid form-grid-three">
          <label>
            Unit
            <select name="unit" value={form.unit} onChange={handleChange}>
              <option value="piece">Piece</option>
              <option value="box">Box</option>
              <option value="bag">Bag</option>
              <option value="pack">Pack</option>
              <option value="bundle">Bundle</option>
              <option value="length">Length</option>
              <option value="litre">Litre</option>
              <option value="kilogram">Kilogram</option>
            </select>
          </label>
          <label>
            Opening stock
            <input name="stock" type="number" min="0" step="1" value={form.stock} onChange={handleChange} />
          </label>
          <label>
            Low-stock level
            <input name="lowStockLevel" type="number" min="0" step="1" value={form.lowStockLevel} onChange={handleChange} />
          </label>
          <label>
            Cost price (GH₵)
            <input name="costPrice" type="number" min="0" step="0.01" value={form.costPrice} onChange={handleChange} />
          </label>
          <label>
            Selling price (GH₵)
            <input name="sellingPrice" type="number" min="0" step="0.01" value={form.sellingPrice} onChange={handleChange} />
          </label>
        </div>

        <div className="modal-form-actions">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit">{product ? "Save changes" : "Add product"}</Button>
        </div>
      </form>
    </Modal>
  );
}
