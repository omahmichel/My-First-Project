import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  seedBusiness,
  seedCustomers,
  seedProducts,
  seedSales,
  seedStockMovements,
  seedTeam,
} from "../data/seedData";
import { useAuth } from "./AuthContext";
import { apiRequest } from "../services/api";
import { loadStoredValue, saveStoredValue } from "../services/storage";
import { createId } from "../utils/formatters";

const StoreContext = createContext(null);

const BUSINESS_IDS_BY_TYPE = {
  building_materials: "business_phildial",
  boutique: "business_kendy",
};

const DEFAULT_BUSINESSES = [
  {
    ...seedBusiness,
    id: "business_phildial",
    name: "Phildial Enterprise",
    type: "building_materials",
  },
  {
    ...seedBusiness,
    id: "business_kendy",
    name: "Kendy Trenz",
    type: "boutique",
    invoicePrefix: "KDY",
    receiptPrefix: "KRC",
  },
];


// Maps a Django business response to the existing frontend business shape.
function normalizeBusiness(record) {
  return {
    id: record.id,
    name: record.name,
    slug: record.slug,
    type: record.business_type,
    businessType: record.business_type,
    phone: record.phone ?? "",
    email: record.email ?? "",
    location: record.location ?? "",
    invoicePrefix: record.invoicePrefix ?? "INV",
    receiptPrefix: record.receiptPrefix ?? "RCT",
    status: record.status ?? "active",
    ownerName: record.owner_name ?? "",
    ownerEmail: record.owner_email ?? "",
    currentUserRole: record.current_user_role ?? "account",
    activeTeamMembers: record.active_team_members ?? 0,
    createdAt: record.created_at ?? null,
    updatedAt: record.updated_at ?? null,
  };
}


// Converts plain or paginated API responses into a predictable array.
function normalizeApiCollection(response) {
  if (Array.isArray(response)) return response;
  if (Array.isArray(response?.results)) return response.results;
  return [];
}

// Converts Django decimal strings without exposing missing restricted values.
function normalizeOptionalNumber(value) {
  if (value === null || value === undefined || value === "") return null;

  const parsedValue = Number(value);
  return Number.isFinite(parsedValue) ? parsedValue : null;
}

// Maps a Django product response into the existing frontend product shape.
function normalizeProduct(record) {
  const isActive = record.isActive !== false;

  return {
    ...record,
    id: String(record.id),
    businessId: String(record.businessId),
    stock: Number(record.stock ?? 0),
    reservedStock: Number(record.reservedStock ?? 0),
    availableStock: Number(record.availableStock ?? record.stock ?? 0),
    lowStockLevel: Number(record.lowStockLevel ?? 0),
    costPrice: normalizeOptionalNumber(record.costPrice),
    sellingPrice: Number(record.sellingPrice ?? 0),
    piecesPerBox: Number(record.piecesPerBox ?? 0),
    sqmPerBox: Number(record.sqmPerBox ?? 0),
    loosePieces: Number(record.loosePieces ?? 0),
    isActive,
    status: isActive ? "active" : "inactive",
  };
}

// Maps Django stock history and preserves the existing opening-stock filter.
function normalizeStockMovement(record) {
  const isOpeningStock =
    record.type === "stock_in" && record.reason === "Opening stock";

  return {
    ...record,
    id: String(record.id),
    businessId: String(record.businessId),
    productId: String(record.productId),
    quantity: Number(record.quantity ?? 0),
    previousStock: Number(record.previousStock ?? 0),
    newStock: Number(record.newStock ?? 0),
    type: isOpeningStock ? "opening_stock" : record.type,
  };
}

// Replaces records for one business without removing another workspace's cache.
function replaceBusinessRecords(currentRecords, businessId, nextRecords) {
  return [
    ...currentRecords.filter(
      (record) => String(resolveRecordBusinessId(record)) !== String(businessId),
    ),
    ...nextRecords,
  ];
}

// Inserts a new API record or replaces its current cached version.
function upsertBusinessRecord(currentRecords, nextRecord) {
  const recordExists = currentRecords.some(
    (record) => String(record.id) === String(nextRecord.id),
  );

  if (!recordExists) return [nextRecord, ...currentRecords];

  return currentRecords.map((record) =>
    String(record.id) === String(nextRecord.id) ? nextRecord : record,
  );
}

// Builds only writable product fields accepted by the Django serializer.
function buildProductPayload(product, { includeStock = false } = {}) {
  const numberOrZero = (value) => {
    const parsedValue = Number(value);
    return Number.isFinite(parsedValue) && parsedValue >= 0
      ? parsedValue
      : 0;
  };

  const payload = {
    productType: product.productType,
    name: String(product.name ?? "").trim(),
    sku: String(product.sku ?? "").trim(),
    category: String(product.category ?? "").trim(),
    brand: String(product.brand ?? "").trim(),
    unit: product.unit || "piece",
    lowStockLevel: numberOrZero(product.lowStockLevel),
    costPrice: numberOrZero(product.costPrice),
    sellingPrice: numberOrZero(product.sellingPrice),
    designCode: String(product.designCode ?? "").trim(),
    size: String(product.size ?? "").trim(),
    finish: String(product.finish ?? "").trim(),
    color: String(product.color ?? "").trim(),
    batchNumber: String(product.batchNumber ?? "").trim(),
    piecesPerBox: numberOrZero(product.piecesPerBox),
    sqmPerBox: numberOrZero(product.sqmPerBox),
    loosePieces: numberOrZero(product.loosePieces),
    styleCode: String(product.styleCode ?? "").trim(),
  };

  if (includeStock) {
    payload.stock = numberOrZero(product.stock);
  }

  return payload;
}

// Resolves old business-type records into stable business IDs during migration.
function resolveRecordBusinessId(record, fallbackBusinessId = "business_phildial") {
  return (
    record.businessId ??
    BUSINESS_IDS_BY_TYPE[record.businessType] ??
    fallbackBusinessId
  );
}

// Preserves an existing multi-business list or migrates the former single profile.
function loadInitialBusinesses() {
  const storedBusinesses = loadStoredValue("businesses", null);

  if (Array.isArray(storedBusinesses) && storedBusinesses.length > 0) {
    return storedBusinesses;
  }

  const legacyBusiness = loadStoredValue("business", seedBusiness);

  return DEFAULT_BUSINESSES.map((defaultBusiness) =>
    defaultBusiness.type === legacyBusiness.type
      ? {
          ...defaultBusiness,
          ...legacyBusiness,
          id: defaultBusiness.id,
          name: defaultBusiness.name,
          type: defaultBusiness.type,
        }
      : defaultBusiness,
  );
}

// Adds business IDs to old browser records without removing their existing fields.
function loadBusinessRecords(storageKey, seedRecords, fallbackBusinessId) {
  const records = loadStoredValue(storageKey, seedRecords);

  return records.map((record) => ({
    ...record,
    businessId: resolveRecordBusinessId(record, fallbackBusinessId),
  }));
}

export function StoreProvider({ children }) {
  const { user, isInitializing: authInitializing } = useAuth();
  const [businesses, setBusinesses] = useState(loadInitialBusinesses);
  const [businessesLoading, setBusinessesLoading] = useState(true);
  const [businessesError, setBusinessesError] = useState("");
  const [activeBusinessId, setActiveBusinessId] = useState(() => {
    const legacyBusiness = loadStoredValue("business", seedBusiness);
    const fallbackId =
      BUSINESS_IDS_BY_TYPE[legacyBusiness.type] ?? "business_phildial";

    return loadStoredValue("active_business_id", fallbackId);
  });
  const [products, setProducts] = useState(() =>
    loadBusinessRecords("products", seedProducts, "business_phildial"),
  );
  const [inventoryLoading, setInventoryLoading] = useState(false);
  const [inventoryError, setInventoryError] = useState("");
  const [customers, setCustomers] = useState(() =>
    loadBusinessRecords("customers", seedCustomers, "business_phildial"),
  );
  const [sales, setSales] = useState(() =>
    loadBusinessRecords("sales", seedSales, "business_phildial"),
  );
  const [stockMovements, setStockMovements] = useState(() =>
    loadBusinessRecords(
      "stock_movements",
      seedStockMovements,
      "business_phildial",
    ),
  );
  const [team, setTeam] = useState(() =>
    loadBusinessRecords("team", seedTeam, "business_phildial"),
  );
  // Stores issued receipts and later customer debt payments.
  const [payments, setPayments] = useState(() =>
    loadBusinessRecords("payments", [], "business_phildial"),
  );

  const business = useMemo(
    () =>
      businesses.find((item) => item.id === activeBusinessId) ??
      businesses[0] ??
      DEFAULT_BUSINESSES[0],
    [activeBusinessId, businesses],
  );



  // Loads only the authenticated user's real Django business workspaces.
  const loadBusinesses = useCallback(async (preferredBusinessId = null) => {
    setBusinessesLoading(true);
    setBusinessesError("");

    try {
      const response = await apiRequest("/businesses/");
      const records = Array.isArray(response)
        ? response
        : Array.isArray(response?.results)
          ? response.results
          : [];
      const nextBusinesses = records
        .map(normalizeBusiness)
        .sort(
          (first, second) =>
            new Date(first.createdAt ?? 0).getTime() -
            new Date(second.createdAt ?? 0).getTime(),
        );

      setBusinesses(nextBusinesses);
      setActiveBusinessId((currentBusinessId) => {
        if (
          preferredBusinessId &&
          nextBusinesses.some((item) => item.id === preferredBusinessId)
        ) {
          return preferredBusinessId;
        }

        if (nextBusinesses.some((item) => item.id === currentBusinessId)) {
          return currentBusinessId;
        }

        return nextBusinesses[0]?.id ?? "";
      });

      return nextBusinesses;
    } catch (error) {
      setBusinessesError(error.message);
      throw error;
    } finally {
      setBusinessesLoading(false);
    }
  }, []);


  // Loads real products and stock movements for one selected business.
  const loadInventory = useCallback(async (businessId) => {
    if (!businessId) {
      setInventoryLoading(false);
      setInventoryError("");
      return { products: [], stockMovements: [] };
    }

    setInventoryLoading(true);
    setInventoryError("");

    try {
      const [productResponse, movementResponse] = await Promise.all([
        apiRequest(`/businesses/${businessId}/products/`),
        apiRequest(`/businesses/${businessId}/stock-movements/`),
      ]);

      const nextProducts = normalizeApiCollection(productResponse).map(
        normalizeProduct,
      );
      const nextStockMovements = normalizeApiCollection(
        movementResponse,
      ).map(normalizeStockMovement);

      setProducts((current) =>
        replaceBusinessRecords(current, businessId, nextProducts),
      );
      setStockMovements((current) =>
        replaceBusinessRecords(
          current,
          businessId,
          nextStockMovements,
        ),
      );

      return {
        products: nextProducts,
        stockMovements: nextStockMovements,
      };
    } catch (error) {
      setInventoryError(error.message);
      throw error;
    } finally {
      setInventoryLoading(false);
    }
  }, []);

  // Restores real businesses after a saved JWT session is verified.
  useEffect(() => {
    if (authInitializing) return;

    if (!user) {
      setBusinessesLoading(false);
      setBusinessesError("");
      return;
    }

    loadBusinesses().catch(() => {
      // The exposed error state allows the UI to report the failure later.
    });
  }, [authInitializing, loadBusinesses, user]);


  // Refreshes real inventory whenever the authenticated workspace changes.
  useEffect(() => {
    if (authInitializing || businessesLoading) return;

    if (!user) {
      setInventoryLoading(false);
      setInventoryError("");
      return;
    }

    const businessExists = businesses.some(
      (item) => String(item.id) === String(activeBusinessId),
    );

    if (!activeBusinessId || !businessExists) return;

    loadInventory(activeBusinessId).catch(() => {
      // The exposed error state lets inventory pages report the failure.
    });
  }, [
    activeBusinessId,
    authInitializing,
    businesses,
    businessesLoading,
    loadInventory,
    user,
  ]);

  useEffect(() => saveStoredValue("businesses", businesses), [businesses]);
  useEffect(
    () => saveStoredValue("active_business_id", activeBusinessId),
    [activeBusinessId],
  );
  useEffect(() => saveStoredValue("business", business), [business]);
  useEffect(() => saveStoredValue("products", products), [products]);
  useEffect(() => saveStoredValue("customers", customers), [customers]);
  useEffect(() => saveStoredValue("sales", sales), [sales]);
  useEffect(() => saveStoredValue("stock_movements", stockMovements), [stockMovements]);
  useEffect(() => saveStoredValue("team", team), [team]);
  useEffect(() => saveStoredValue("payments", payments), [payments]);

  // Keeps all business records in storage while exposing only the active business.
  const productBusinessIds = useMemo(
    () =>
      new Map(
        products.map((product) => [
          product.id,
          resolveRecordBusinessId(product),
        ]),
      ),
    [products],
  );

  const currentProducts = useMemo(
    () =>
      products.filter(
        (product) => resolveRecordBusinessId(product) === business.id,
      ),
    [business.id, products],
  );

  const currentCustomers = useMemo(
    () =>
      customers.filter(
        (customer) => resolveRecordBusinessId(customer) === business.id,
      ),
    [business.id, customers],
  );

  const currentSales = useMemo(
    () =>
      sales.filter((sale) => {
        const saleBusinessId =
          sale.businessId ?? BUSINESS_IDS_BY_TYPE[sale.businessType];

        if (saleBusinessId) return saleBusinessId === business.id;

        return (sale.items ?? []).some(
          (item) => productBusinessIds.get(item.productId) === business.id,
        );
      }),
    [business.id, productBusinessIds, sales],
  );

  const currentStockMovements = useMemo(
    () =>
      stockMovements.filter((movement) => {
        const movementBusinessId =
          movement.businessId ??
          BUSINESS_IDS_BY_TYPE[movement.businessType];

        if (movementBusinessId) return movementBusinessId === business.id;

        return productBusinessIds.get(movement.productId) === business.id;
      }),
    [business.id, productBusinessIds, stockMovements],
  );

  const currentPayments = useMemo(
    () =>
      payments.filter(
        (payment) => resolveRecordBusinessId(payment) === business.id,
      ),
    [business.id, payments],
  );

  const currentTeam = useMemo(
    () =>
      team.filter(
        (member) => resolveRecordBusinessId(member) === business.id,
      ),
    [business.id, team],
  );

  function updateBusiness(changes) {
    const requestedBusinessId = changes.id;

    // Preserves onboarding compatibility by adding a genuinely new business.
    if (
      requestedBusinessId &&
      requestedBusinessId !== activeBusinessId &&
      !businesses.some((item) => item.id === requestedBusinessId)
    ) {
      const nextBusiness = {
        ...business,
        ...changes,
        id: requestedBusinessId,
      };

      setBusinesses((current) => [...current, nextBusiness]);
      setActiveBusinessId(nextBusiness.id);
      return nextBusiness;
    }

    setBusinesses((current) =>
      current.map((item) =>
        item.id === activeBusinessId
          ? {
              ...item,
              ...changes,
              id: item.id,
            }
          : item,
      ),
    );

    return {
      ...business,
      ...changes,
      id: business.id,
    };
  }

  function switchBusiness(businessId) {
    const nextBusiness = businesses.find((item) => item.id === businessId);

    if (!nextBusiness) {
      throw new Error("The selected business is not available.");
    }

    setActiveBusinessId(nextBusiness.id);
    return nextBusiness;
  }

  function findCurrentProduct(productId) {
    return currentProducts.find((product) => product.id === productId);
  }

  async function addProduct(product) {
    const businessId = business.id;
    const response = await apiRequest(
      `/businesses/${businessId}/products/`,
      {
        method: "POST",
        body: JSON.stringify(
          buildProductPayload(product, { includeStock: true }),
        ),
      },
    );
    const nextProduct = normalizeProduct(response);

    setProducts((current) =>
      upsertBusinessRecord(current, nextProduct),
    );

    // Shows opening stock immediately while preserving backend authority.
    if (nextProduct.stock > 0) {
      setStockMovements((current) => [
        {
          id: createId("movement"),
          businessId,
          businessType: business.type,
          productId: nextProduct.id,
          productName: nextProduct.name,
          type: "opening_stock",
          quantity: nextProduct.stock,
          unit: nextProduct.unit,
          previousStock: 0,
          newStock: nextProduct.stock,
          reason: "Opening stock",
          user: "Current user",
          createdAt: nextProduct.createdAt ?? new Date().toISOString(),
        },
        ...current,
      ]);
    }

    return nextProduct;
  }

  async function updateProduct(productId, changes) {
    const currentProduct = findCurrentProduct(productId);

    if (!currentProduct) {
      throw new Error(
        "You cannot update a product outside this business.",
      );
    }

    const response = await apiRequest(
      `/businesses/${business.id}/products/${productId}/`,
      {
        method: "PATCH",
        body: JSON.stringify(buildProductPayload(changes)),
      },
    );
    const updatedProduct = normalizeProduct(response);

    setProducts((current) =>
      upsertBusinessRecord(current, updatedProduct),
    );

    return updatedProduct;
  }

  async function toggleProductStatus(productId) {
    const currentProduct = findCurrentProduct(productId);

    if (!currentProduct) {
      throw new Error(
        "You cannot change a product outside this business.",
      );
    }

    const response = await apiRequest(
      `/businesses/${business.id}/products/${productId}/status/`,
      {
        method: "PATCH",
        body: JSON.stringify({
          isActive: currentProduct.status !== "active",
        }),
      },
    );
    const updatedProduct = normalizeProduct(response);

    setProducts((current) =>
      upsertBusinessRecord(current, updatedProduct),
    );

    return updatedProduct;
  }

  // Archives a product through Django without deleting its audit history.
  async function deleteProduct(productId) {
    const currentProduct = findCurrentProduct(productId);

    if (!currentProduct) {
      throw new Error(
        "You cannot archive a product outside this business.",
      );
    }

    await apiRequest(
      `/businesses/${business.id}/products/${productId}/`,
      { method: "DELETE" },
    );

    const archivedProduct = {
      ...currentProduct,
      isActive: false,
      status: "inactive",
    };

    setProducts((current) =>
      upsertBusinessRecord(current, archivedProduct),
    );

    return archivedProduct;
  }

  async function adjustStock({ productId, quantity, type, reason }) {
    const currentProduct = findCurrentProduct(productId);

    if (!currentProduct) {
      throw new Error(
        "Product not found in this business inventory.",
      );
    }

    const response = await apiRequest(
      `/businesses/${business.id}/products/${productId}/adjust-stock/`,
      {
        method: "POST",
        body: JSON.stringify({
          quantity: Number(quantity),
          type,
          reason: String(reason ?? "").trim(),
        }),
      },
    );

    const updatedProduct = normalizeProduct(response.product);
    const nextMovement = normalizeStockMovement(response.movement);

    setProducts((current) =>
      upsertBusinessRecord(current, updatedProduct),
    );
    setStockMovements((current) => [
      nextMovement,
      ...current.filter(
        (movement) =>
          String(movement.id) !== String(nextMovement.id),
      ),
    ]);

    return {
      product: updatedProduct,
      movement: nextMovement,
    };
  }

  function addCustomer(customer) {
    const nextCustomer = {
      ...customer,
      id: createId("customer"),
      businessType: business.type,
      businessId: business.id,
      outstandingBalance: Number(customer.outstandingBalance) || 0,
      totalPurchases: 0,
      createdAt: new Date().toISOString(),
    };

    setCustomers((current) => [nextCustomer, ...current]);
    return nextCustomer;
  }

  // Records a customer payment against one unpaid invoice and issues a receipt.
  function recordCustomerPayment(customerId, amount, details = {}) {
    const paymentAmount = Number(amount);
    const customer = currentCustomers.find((item) => item.id === customerId);

    if (!customer) throw new Error("Customer not found in this business.");
    if (paymentAmount <= 0) throw new Error("Enter a valid payment amount.");
    if (paymentAmount > customer.outstandingBalance) {
      throw new Error("Payment cannot exceed the customer's outstanding balance.");
    }

    const unpaidSales = currentSales
      .filter(
        (sale) =>
          sale.customerId === customerId &&
          Number(sale.outstandingBalance || 0) > 0,
      )
      .sort(
        (first, second) =>
          new Date(first.createdAt).getTime() -
          new Date(second.createdAt).getTime(),
      );

    const selectedSale = details.saleId
      ? unpaidSales.find((sale) => sale.id === details.saleId)
      : unpaidSales[0];

    if (!selectedSale) {
      throw new Error("No unpaid invoice was found for this customer.");
    }

    if (paymentAmount > Number(selectedSale.outstandingBalance || 0)) {
      throw new Error(
        `Payment cannot exceed the selected invoice balance of ${selectedSale.outstandingBalance}.`,
      );
    }

    const createdAt = new Date().toISOString();
    const receiptSequence = currentPayments.length + 501;
    const receiptNumber = `${business.receiptPrefix || "RCT"}-${String(
      receiptSequence,
    ).padStart(5, "0")}`;

    const receipt = {
      id: createId("payment"),
      receiptNumber,
      businessType: business.type,
      businessId: business.id,
      saleId: selectedSale.id,
      saleNumber: selectedSale.saleNumber,
      invoiceNumber: selectedSale.invoiceNumber,
      customerId: customer.id,
      customerName: customer.name,
      amount: paymentAmount,
      paymentMethod: details.paymentMethod || "cash",
      reference: String(details.reference || "").trim(),
      note: String(details.note || "").trim(),
      cashier: details.cashier || "Michael Triumph",
      type: "debt_payment",
      status: "issued",
      createdAt,
    };

    setSales((current) =>
      current.map((sale) => {
        if (sale.id !== selectedSale.id) return sale;

        const nextAmountPaid = Number(sale.amountPaid || 0) + paymentAmount;
        const nextOutstandingBalance = Math.max(
          0,
          Number(sale.outstandingBalance || 0) - paymentAmount,
        );

        return {
          ...sale,
          amountPaid: nextAmountPaid,
          outstandingBalance: nextOutstandingBalance,
          status: nextOutstandingBalance > 0 ? "partially_paid" : "completed",
          latestReceiptNumber: receiptNumber,
        };
      }),
    );

    setCustomers((current) =>
      current.map((item) =>
        item.id === customerId
          ? {
              ...item,
              outstandingBalance: Math.max(
                0,
                Number(item.outstandingBalance || 0) - paymentAmount,
              ),
            }
          : item,
      ),
    );

    setPayments((current) => [receipt, ...current]);
    return receipt;
  }

  // Creates or updates one waybill for the complete multi-item sale.
  function saveWaybill(saleId, details = {}) {
    const selectedSale = currentSales.find((sale) => sale.id === saleId);

    if (!selectedSale) {
      throw new Error("Sale not found in this business.");
    }

    const existingWaybillNumber = selectedSale.waybill?.waybillNumber;
    const waybillSequence =
      currentSales.filter((sale) => sale.waybill?.waybillNumber).length + 101;
    const waybillNumber =
      existingWaybillNumber ||
      `${business.waybillPrefix || "WB"}-${String(waybillSequence).padStart(
        5,
        "0",
      )}`;

    const waybill = {
      waybillNumber,
      recipientName:
        String(details.recipientName || selectedSale.customerName || "").trim() ||
        "Walk-in customer",
      recipientPhone: String(details.recipientPhone || "").trim(),
      deliveryAddress: String(details.deliveryAddress || "").trim(),
      dispatchDate:
        details.dispatchDate || new Date().toISOString().slice(0, 10),
      driverName: String(details.driverName || "").trim(),
      vehicleNumber: String(details.vehicleNumber || "").trim(),
      deliveryNotes: String(details.deliveryNotes || "").trim(),
      status: details.status || "pending",
      createdAt: selectedSale.waybill?.createdAt || new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    setSales((current) =>
      current.map((sale) =>
        sale.id === saleId
          ? {
              ...sale,
              waybill,
            }
          : sale,
      ),
    );

    return waybill;
  }

  function completeSale({ cartItems, customerId, discount, amountPaid, paymentMethod }) {
    if (!cartItems.length) throw new Error("Add at least one product to the sale.");

    cartItems.forEach((cartItem) => {
      const product = findCurrentProduct(cartItem.productId);
      if (!product || product.status !== "active") {
        throw new Error(`${cartItem.name} is not available in this business.`);
      }
      if (cartItem.quantity > product.stock) {
        throw new Error(`Only ${product.stock} ${product.unit}(s) of ${product.name} remain.`);
      }
    });

    const subtotal = cartItems.reduce((sum, item) => sum + item.quantity * item.unitPrice, 0);
    const safeDiscount = Math.max(0, Number(discount) || 0);
    const total = Math.max(0, subtotal - safeDiscount);
    const safeAmountPaid = Math.max(0, Number(amountPaid) || 0);
    const outstandingBalance = Math.max(0, total - safeAmountPaid);
    const selectedCustomer = currentCustomers.find((customer) => customer.id === customerId);

    if (outstandingBalance > 0 && !selectedCustomer) {
      throw new Error("Select a customer before completing a credit sale.");
    }

    if (safeAmountPaid > total) {
      throw new Error("Amount paid cannot be greater than the sale total.");
    }

    const saleSequence = currentSales.length + 32;
    const invoiceSequence = currentSales.length + 285;
    const createdAt = new Date().toISOString();
    const saleId = createId("sale");
    const saleNumber = `SAL-${String(saleSequence).padStart(5, "0")}`;
    const invoiceNumber = `${business.invoicePrefix || "INV"}-${String(invoiceSequence).padStart(5, "0")}`;
    // Issues a receipt immediately when money is received with the sale.
    const receiptSequence = currentPayments.length + 501;
    const receiptNumber =
      safeAmountPaid > 0
        ? `${business.receiptPrefix || "RCT"}-${String(
            receiptSequence,
          ).padStart(5, "0")}`
        : null;

    const saleItems = cartItems.map((cartItem) => {
      const product = findCurrentProduct(cartItem.productId);
      return {
        productId: product.id,
        name: product.designCode ? `${product.name} — Design ${product.designCode}` : product.name,
        quantity: cartItem.quantity,
        unit: product.unit,
        unitPrice: cartItem.unitPrice,
        costPrice: product.costPrice,
        total: cartItem.quantity * cartItem.unitPrice,
      };
    });

    const sale = {
      id: saleId,
      saleNumber,
      invoiceNumber,
      receiptNumber,
      latestReceiptNumber: receiptNumber,
      waybill: null,
      businessType: business.type,
      businessId: business.id,
      customerId: selectedCustomer?.id ?? null,
      customerName: selectedCustomer?.name ?? "Walk-in customer",
      items: saleItems,
      subtotal,
      discount: safeDiscount,
      total,
      amountPaid: safeAmountPaid,
      outstandingBalance,
      paymentMethod,
      status: outstandingBalance > 0 ? "partially_paid" : "completed",
      cashier: "Michael Triumph",
      createdAt,
    };

    setProducts((current) =>
      current.map((product) => {
        const soldItem = saleItems.find((item) => item.productId === product.id);
        return soldItem ? { ...product, stock: product.stock - soldItem.quantity } : product;
      }),
    );

    const saleMovements = saleItems.map((item) => ({
      id: createId("movement"),
      productId: item.productId,
      productName: item.name,
      businessType: business.type,
      businessId: business.id,
      type: "sale",
      quantity: -item.quantity,
      unit: item.unit,
      reason: `Sale ${saleNumber}`,
      user: "Michael Triumph",
      createdAt,
    }));

    setStockMovements((current) => [...saleMovements, ...current]);
    setSales((current) => [sale, ...current]);

    if (safeAmountPaid > 0) {
      const receipt = {
        id: createId("payment"),
        receiptNumber,
        businessType: business.type,
        businessId: business.id,
        saleId,
        saleNumber,
        invoiceNumber,
        customerId: selectedCustomer?.id ?? null,
        customerName: selectedCustomer?.name ?? "Walk-in customer",
        amount: safeAmountPaid,
        paymentMethod,
        reference: "",
        note: "Payment received when the sale was completed.",
        cashier: "Michael Triumph",
        type: "sale_payment",
        status: "issued",
        createdAt,
      };

      setPayments((current) => [receipt, ...current]);
    }

    if (selectedCustomer) {
      setCustomers((current) =>
        current.map((customer) =>
          customer.id === selectedCustomer.id
            ? {
                ...customer,
                outstandingBalance: customer.outstandingBalance + outstandingBalance,
                totalPurchases: customer.totalPurchases + total,
              }
            : customer,
        ),
      );
    }

    return sale;
  }

  function addTeamMember(member) {
    const nextMember = {
      ...member,
      id: createId("team"),
      businessType: business.type,
      businessId: business.id,
      status: "active",
      lastActive: null,
    };
    setTeam((current) => [...current, nextMember]);
    return nextMember;
  }

  // Deletes a staff account only from the currently active business.
  function deleteTeamMember(memberId) {
    const member = team.find((item) => item.id === memberId);

    if (!member) {
      throw new Error("This team member could not be found.");
    }

    if (resolveRecordBusinessId(member) !== business.id) {
      throw new Error(
        "You cannot remove a team member from another business.",
      );
    }

    if (member.role === "owner") {
      throw new Error(
        "The business owner account cannot be deleted.",
      );
    }

    setTeam((current) =>
      current.filter((item) => item.id !== memberId),
    );

    return member;
  }

  const metrics = useMemo(() => {
    const today = new Date().toDateString();
    const todaySales = currentSales.filter(
      (sale) => new Date(sale.createdAt).toDateString() === today,
    );
    const todayRevenue = todaySales.reduce((sum, sale) => sum + sale.total, 0);
    const todayProfit = todaySales.reduce(
      (sum, sale) =>
        sum +
        sale.items.reduce(
          (itemSum, item) => itemSum + (item.unitPrice - item.costPrice) * item.quantity,
          0,
        ) -
        sale.discount,
      0,
    );
    const customerDebt = currentCustomers.reduce(
      (sum, customer) => sum + customer.outstandingBalance,
      0,
    );
    const stockValue = currentProducts.reduce(
      (sum, product) =>
        sum + product.stock * Number(product.costPrice ?? 0),
      0,
    );
    const lowStockProducts = currentProducts.filter(
      (product) => product.status === "active" && product.stock <= product.lowStockLevel,
    );

    return {
      todaySales,
      todayRevenue,
      todayProfit,
      customerDebt,
      stockValue,
      lowStockProducts,
      activeProducts: currentProducts.filter((product) => product.status === "active").length,
    };
  }, [currentCustomers, currentProducts, currentSales]);

  const value = useMemo(
    () => ({
      business,
      businesses,
      activeBusinessId,
      businessesLoading,
      businessesError,
      loadBusinesses,
      inventoryLoading,
      inventoryError,
      loadInventory,
      products: currentProducts,
      customers: currentCustomers,
      sales: currentSales,
      payments: currentPayments,
      stockMovements: currentStockMovements,
      team: currentTeam,
      metrics,
      updateBusiness,
      switchBusiness,
      addProduct,
      updateProduct,
      toggleProductStatus,
      deleteProduct,
      adjustStock,
      addCustomer,
      recordCustomerPayment,
      saveWaybill,
      completeSale,
      addTeamMember,
      deleteTeamMember,
    }),
    [
      activeBusinessId,
      business,
      businesses,
      businessesError,
      businessesLoading,
      inventoryError,
      inventoryLoading,
      currentCustomers,
      currentProducts,
      currentSales,
      currentPayments,
      currentStockMovements,
      currentTeam,
      metrics,
    ],
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore() {
  const context = useContext(StoreContext);
  if (!context) throw new Error("useStore must be used inside StoreProvider.");
  return context;
}
