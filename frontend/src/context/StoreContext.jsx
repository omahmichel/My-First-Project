import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { useAuth } from "./AuthContext";
import { apiRequest } from "../services/api";
import { loadStoredValue, saveStoredValue } from "../services/storage";
import { createId } from "../utils/formatters";

const StoreContext = createContext(null);

const EMPTY_BUSINESS = Object.freeze({
  id: "",
  name: "",
  slug: "",
  type: "",
  phone: "",
  email: "",
  location: "",
  invoicePrefix: "INV",
  receiptPrefix: "RCT",
  status: "",
  ownerName: "",
  ownerEmail: "",
  currentUserRole: "",
  activeTeamMembers: 0,
  // Holds backend-authoritative trial and subscription access state.
  trialStartedAt: null,
  trialEndsAt: null,
  trialDaysRemaining: 0,
  subscriptionStatus: "",
  subscriptionStartedAt: null,
  subscriptionEndsAt: null,
  isTrialActive: false,
  hasActiveSubscription: false,
  subscriptionReminderDue: false,
  hasSystemAccess: false,
});


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
    // Preserves subscription state returned by the Django business API.
    trialStartedAt: record.trial_started_at ?? null,
    trialEndsAt: record.trial_ends_at ?? null,
    trialDaysRemaining: Number(record.trialDaysRemaining ?? 0),
    subscriptionStatus: record.subscription_status ?? "trial",
    subscriptionStartedAt: record.subscription_started_at ?? null,
    subscriptionEndsAt: record.subscription_ends_at ?? null,
    isTrialActive: Boolean(record.isTrialActive),
    hasActiveSubscription: Boolean(record.hasActiveSubscription),
    subscriptionReminderDue: Boolean(record.subscriptionReminderDue),
    hasSystemAccess: Boolean(record.hasSystemAccess),
  };
}



// Maps one Django team membership into the existing React team shape.
function normalizeTeamMember(record, business) {
  return {
    ...record,
    id: String(record.id),
    businessId: String(business.id),
    businessType: business.type,
    name: record.name ?? "",
    email: record.email ?? "",
    phone: record.phone ?? "",
    role: record.role ?? "cashier",
    status: record.status ?? "active",
    lastActive: record.lastActive ?? null,
    joinedAt: record.joinedAt ?? null,
    isNewUser: Boolean(record.isNewUser),
    temporaryPassword: record.temporaryPassword ?? "",
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


// Maps Django customer decimals into values used by React calculations.
function normalizeCustomer(record) {
  const isActive = record.isActive !== false;

  return {
    ...record,
    id: String(record.id),
    businessId: String(record.businessId),
    outstandingBalance: Number(record.outstandingBalance ?? 0),
    totalPurchases: Number(record.totalPurchases ?? 0),
    isActive,
    status: isActive ? "active" : "inactive",
  };
}

// Maps a real Django payment response into the existing receipt shape.
function normalizePayment(record) {
  return {
    ...record,
    id: String(record.id),
    businessId: String(record.businessId),
    saleId: record.saleId ? String(record.saleId) : null,
    customerId: record.customerId ? String(record.customerId) : null,
    amount: Number(record.amount ?? 0),
    cashier: record.initiatedBy ?? record.cashier ?? "",
  };
}


// Maps one immutable Django sale line into React numeric values.
function normalizeSaleItem(record) {
  return {
    ...record,
    id: String(record.id),
    productId: String(record.productId),
    quantity: Number(record.quantity ?? 0),
    unitPrice: Number(record.unitPrice ?? 0),
    costPrice:
      record.costPrice === null || record.costPrice === undefined
        ? null
        : Number(record.costPrice),
    total: Number(record.total ?? record.lineTotal ?? 0),
  };
}

// Maps a complete Django invoice response into the existing sale shape.
function normalizeSale(record) {
  const nextPayments = (record.payments ?? []).map(normalizePayment);

  return {
    ...record,
    id: String(record.id),
    businessId: String(record.businessId),
    customerId: record.customerId ? String(record.customerId) : null,
    subtotal: Number(record.subtotal ?? 0),
    discount: Number(record.discount ?? 0),
    total: Number(record.total ?? 0),
    amountPaid: Number(record.amountPaid ?? 0),
    outstandingBalance: Number(record.outstandingBalance ?? 0),
    items: (record.items ?? []).map(normalizeSaleItem),
    payments: nextPayments,
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
function resolveRecordBusinessId(record, fallbackBusinessId = "") {
  return String(
    record?.businessId ??
      record?.business_id ??
      fallbackBusinessId,
  );
}

export function StoreProvider({ children }) {
  const { user, isInitializing: authInitializing } = useAuth();
  const [businesses, setBusinesses] = useState([]);
  const [businessesLoading, setBusinessesLoading] = useState(true);
  const [businessesError, setBusinessesError] = useState("");
  const [activeBusinessId, setActiveBusinessId] = useState(() =>
    loadStoredValue("active_business_id", ""),
  );
  const [products, setProducts] = useState([]);
  const [inventoryLoading, setInventoryLoading] = useState(false);
  const [inventoryError, setInventoryError] = useState("");
  const [customers, setCustomers] = useState([]);
  const [customersLoading, setCustomersLoading] = useState(false);
  const [customersError, setCustomersError] = useState("");
  const [sales, setSales] = useState([]);
  const [salesLoading, setSalesLoading] = useState(false);
  const [salesError, setSalesError] = useState("");
  const [stockMovements, setStockMovements] = useState([]);
  const [team, setTeam] = useState([]);
  const [teamLoading, setTeamLoading] = useState(false);
  const [teamError, setTeamError] = useState("");
  const [payments, setPayments] = useState([]);

  const business = useMemo(
    () =>
      businesses.find((item) => item.id === activeBusinessId) ??
      businesses[0] ??
      EMPTY_BUSINESS,
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


  // Loads real customers for the currently selected business.
  const loadCustomers = useCallback(async (businessId) => {
    if (!businessId) {
      setCustomersLoading(false);
      setCustomersError("");
      return [];
    }

    setCustomersLoading(true);
    setCustomersError("");

    try {
      const response = await apiRequest(
        `/businesses/${businessId}/customers/`,
      );
      const nextCustomers = normalizeApiCollection(response).map(
        normalizeCustomer,
      );

      setCustomers((current) =>
        replaceBusinessRecords(current, businessId, nextCustomers),
      );

      return nextCustomers;
    } catch (error) {
      setCustomersError(error.message);
      throw error;
    } finally {
      setCustomersLoading(false);
    }
  }, []);


  // Loads real invoices and their issued payments for one business.
  const loadSales = useCallback(async (businessId) => {
    if (!businessId) {
      setSalesLoading(false);
      setSalesError("");
      return [];
    }

    setSalesLoading(true);
    setSalesError("");

    try {
      const response = await apiRequest(
        `/businesses/${businessId}/sales/`,
      );
      const nextSales = normalizeApiCollection(response).map(
        normalizeSale,
      );
      const nextPayments = nextSales.flatMap(
        (sale) => sale.payments ?? [],
      );

      setSales((current) =>
        replaceBusinessRecords(current, businessId, nextSales),
      );
      setPayments((current) =>
        replaceBusinessRecords(current, businessId, nextPayments),
      );

      return nextSales;
    } catch (error) {
      setSalesError(error.message);
      throw error;
    } finally {
      setSalesLoading(false);
    }
  }, []);

  // Restores real businesses after a saved JWT session is verified.
  useEffect(() => {
    if (authInitializing) return;

    if (!user) {
      setBusinesses([]);
      setActiveBusinessId("");
      setProducts([]);
      setCustomers([]);
      setSales([]);
      setStockMovements([]);
      setTeam([]);
      setPayments([]);
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

    const activeBusiness = businesses.find(
      (item) => String(item.id) === String(activeBusinessId),
    );

    // Avoids blocked operational requests after trial or subscription expiry.
    if (!activeBusiness?.hasSystemAccess) {
      setProducts((current) =>
        current.filter(
          (record) =>
            resolveRecordBusinessId(record) !== String(activeBusinessId),
        ),
      );
      setStockMovements((current) =>
        current.filter(
          (record) =>
            resolveRecordBusinessId(record) !== String(activeBusinessId),
        ),
      );
      setInventoryLoading(false);
      setInventoryError('');
      return;
    }

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


  // Refreshes real customers whenever the authenticated workspace changes.
  useEffect(() => {
    if (authInitializing || businessesLoading) return;

    if (!user) {
      setCustomersLoading(false);
      setCustomersError("");
      return;
    }

    const businessExists = businesses.some(
      (item) => String(item.id) === String(activeBusinessId),
    );

    if (!activeBusinessId || !businessExists) return;

    const activeBusiness = businesses.find(
      (item) => String(item.id) === String(activeBusinessId),
    );

    // Removes inaccessible customer records without requesting the blocked API.
    if (!activeBusiness?.hasSystemAccess) {
      setCustomers((current) =>
        current.filter(
          (record) =>
            resolveRecordBusinessId(record) !== String(activeBusinessId),
        ),
      );
      setCustomersLoading(false);
      setCustomersError('');
      return;
    }

    loadCustomers(activeBusinessId).catch(() => {
      // The exposed error state lets the customer page report the failure.
    });
  }, [
    activeBusinessId,
    authInitializing,
    businesses,
    businessesLoading,
    loadCustomers,
    user,
  ]);


  // Refreshes real invoices whenever the authenticated workspace changes.
  useEffect(() => {
    if (authInitializing || businessesLoading) return;

    if (!user) {
      setSalesLoading(false);
      setSalesError("");
      return;
    }

    const businessExists = businesses.some(
      (item) => String(item.id) === String(activeBusinessId),
    );

    if (!activeBusinessId || !businessExists) return;

    const activeBusiness = businesses.find(
      (item) => String(item.id) === String(activeBusinessId),
    );

    // Removes inaccessible sales data without requesting the blocked API.
    if (!activeBusiness?.hasSystemAccess) {
      setSales((current) =>
        current.filter(
          (record) =>
            resolveRecordBusinessId(record) !== String(activeBusinessId),
        ),
      );
      setPayments((current) =>
        current.filter(
          (record) =>
            resolveRecordBusinessId(record) !== String(activeBusinessId),
        ),
      );
      setSalesLoading(false);
      setSalesError('');
      return;
    }

    loadSales(activeBusinessId).catch(() => {
      // The exposed error state lets sales pages report the failure.
    });
  }, [
    activeBusinessId,
    authInitializing,
    businesses,
    businessesLoading,
    loadSales,
    user,
  ]);

  // Persists only the selected workspace preference, never business data.
  useEffect(
    () => saveStoredValue("active_business_id", activeBusinessId),
    [activeBusinessId],
  );

  // Exposes only records carrying the active Django business ID.
  const currentProducts = useMemo(
    () =>
      products.filter(
        (product) =>
          resolveRecordBusinessId(product) === business.id,
      ),
    [business.id, products],
  );

  const currentCustomers = useMemo(
    () =>
      customers.filter(
        (customer) =>
          resolveRecordBusinessId(customer) === business.id,
      ),
    [business.id, customers],
  );

  const currentSales = useMemo(
    () =>
      sales.filter(
        (sale) => resolveRecordBusinessId(sale) === business.id,
      ),
    [business.id, sales],
  );

  const currentStockMovements = useMemo(
    () =>
      stockMovements.filter(
        (movement) =>
          resolveRecordBusinessId(movement) === business.id,
      ),
    [business.id, stockMovements],
  );

  const currentPayments = useMemo(
    () =>
      payments.filter(
        (payment) =>
          resolveRecordBusinessId(payment) === business.id,
      ),
    [business.id, payments],
  );

  // Loads only real active team members for one manageable business.
  const loadTeam = useCallback(
    async (businessId, businessRecord = business) => {
      if (!businessId) {
        setTeam([]);
        setTeamLoading(false);
        setTeamError("");
        return [];
      }

      setTeamLoading(true);
      setTeamError("");

      try {
        const response = await apiRequest(
          `/businesses/${businessId}/team/`,
        );
        const nextTeam = normalizeApiCollection(response).map(
          (record) => normalizeTeamMember(record, businessRecord),
        );

        setTeam(nextTeam);
        return nextTeam;
      } catch (error) {
        setTeamError(error.message);
        throw error;
      } finally {
        setTeamLoading(false);
      }
    },
    [business],
  );

  // Refreshes team access whenever the selected business changes.
  useEffect(() => {
    if (authInitializing || businessesLoading) return;

    if (!user || !business?.id) {
      setTeam([]);
      setTeamLoading(false);
      setTeamError("");
      return;
    }

    // Team operations are also unavailable after subscription expiry.
    if (!business.hasSystemAccess) {
      setTeam([]);
      setTeamLoading(false);
      setTeamError('');
      return;
    }

    loadTeam(business.id, business).catch(() => {
      // The Team page displays the exposed error state.
    });
  }, [
    authInitializing,
    business,
    businessesLoading,
    loadTeam,
    user,
  ]);

  const currentTeam = useMemo(
    () =>
      team.filter(
        (member) => resolveRecordBusinessId(member) === business.id,
      ),
    [business.id, team],
  );

  async function updateBusiness(changes) {
    if (!business.id) {
      throw new Error(
        "Create or select a business before updating settings.",
      );
    }

    const response = await apiRequest(
      `/businesses/${business.id}/`,
      {
        method: "PATCH",
        body: JSON.stringify({
          name: String(changes.name ?? business.name).trim(),
          business_type:
            changes.type ??
            changes.businessType ??
            business.type,
          phone: String(changes.phone ?? "").trim(),
          email: String(changes.email ?? "").trim(),
          location: String(changes.location ?? "").trim(),
          invoicePrefix: String(
            changes.invoicePrefix ??
              business.invoicePrefix ??
              "INV",
          )
            .trim()
            .toUpperCase(),
          receiptPrefix: String(
            changes.receiptPrefix ??
              business.receiptPrefix ??
              "RCT",
          )
            .trim()
            .toUpperCase(),
        }),
      },
    );

    const nextBusiness = normalizeBusiness(response);

    setBusinesses((current) =>
      current.map((item) =>
        String(item.id) === String(nextBusiness.id)
          ? nextBusiness
          : item,
      ),
    );

    return nextBusiness;
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

  async function addCustomer(customer) {
    const response = await apiRequest(
      `/businesses/${business.id}/customers/`,
      {
        method: "POST",
        body: JSON.stringify({
          name: String(customer.name ?? "").trim(),
          phone: String(customer.phone ?? "").trim(),
          email: String(customer.email ?? "").trim(),
          address: String(customer.address ?? "").trim(),
        }),
      },
    );
    const nextCustomer = normalizeCustomer(response);

    setCustomers((current) =>
      upsertBusinessRecord(current, nextCustomer),
    );

    return nextCustomer;
  }

  // Records a real debt payment and keeps the visible balances synchronized.
  async function recordCustomerPayment(
    customerId,
    amount,
    details = {},
  ) {
    const paymentAmount = Number(amount);
    const customer = currentCustomers.find(
      (item) => String(item.id) === String(customerId),
    );

    if (!customer) {
      throw new Error("Customer not found in this business.");
    }

    if (!Number.isFinite(paymentAmount) || paymentAmount <= 0) {
      throw new Error("Enter a valid payment amount.");
    }

    if (paymentAmount > Number(customer.outstandingBalance ?? 0)) {
      throw new Error(
        "Payment cannot exceed the customer's outstanding balance.",
      );
    }

    const requestKey =
      typeof window.crypto?.randomUUID === "function"
        ? window.crypto.randomUUID()
        : createId("debt_payment");

    const response = await apiRequest(
      `/businesses/${business.id}/customers/${customerId}/payments/`,
      {
        method: "POST",
        headers: {
          "Idempotency-Key": requestKey,
        },
        body: JSON.stringify({
          amount: paymentAmount,
          saleId: details.saleId || null,
          paymentMethod: details.paymentMethod || "cash",
          reference: String(details.reference ?? "").trim(),
          note: String(details.note ?? "").trim(),
        }),
      },
    );
    const nextPayment = normalizePayment(response);

    setCustomers((current) =>
      current.map((item) =>
        String(item.id) === String(customerId)
          ? {
              ...item,
              outstandingBalance: Math.max(
                0,
                Number(item.outstandingBalance ?? 0) -
                  nextPayment.amount,
              ),
            }
          : item,
      ),
    );

    if (nextPayment.saleId) {
      setSales((current) =>
        current.map((sale) => {
          if (String(sale.id) !== String(nextPayment.saleId)) {
            return sale;
          }

          const nextAmountPaid =
            Number(sale.amountPaid ?? 0) + nextPayment.amount;
          const nextOutstandingBalance = Math.max(
            0,
            Number(sale.outstandingBalance ?? 0) -
              nextPayment.amount,
          );

          return {
            ...sale,
            amountPaid: nextAmountPaid,
            outstandingBalance: nextOutstandingBalance,
            status:
              nextOutstandingBalance > 0
                ? "partially_paid"
                : "completed",
            latestReceiptNumber: nextPayment.receiptNumber,
          };
        }),
      );
    }

    setPayments((current) =>
      upsertBusinessRecord(current, nextPayment),
    );

    return nextPayment;
  }

  // Creates or updates one persistent waybill through Django.
  async function saveWaybill(saleId, details = {}) {
    const selectedSale = currentSales.find(
      (sale) => String(sale.id) === String(saleId),
    );

    if (!selectedSale) {
      throw new Error("Sale not found in this business.");
    }

    const payload = {
      recipientName:
        String(
          details.recipientName || selectedSale.customerName || "",
        ).trim() || "Walk-in customer",
      recipientPhone: String(details.recipientPhone || "").trim(),
      deliveryAddress: String(details.deliveryAddress || "").trim(),
      dispatchDate:
        details.dispatchDate || new Date().toISOString().slice(0, 10),
      driverName: String(details.driverName || "").trim(),
      vehicleNumber: String(details.vehicleNumber || "").trim(),
      deliveryNotes: String(details.deliveryNotes || "").trim(),
      status: details.status || "pending",
    };

    if (!payload.deliveryAddress) {
      throw new Error("Enter the delivery address.");
    }

    const waybill = await apiRequest(
      `/businesses/${business.id}/sales/${saleId}/waybill/`,
      {
        method: selectedSale.waybill ? "PUT" : "POST",
        body: JSON.stringify(payload),
      },
    );

    setSales((current) =>
      current.map((sale) =>
        String(sale.id) === String(saleId)
          ? {
              ...sale,
              waybill,
            }
          : sale,
      ),
    );

    return waybill;
  }

  async function completeSale({
    cartItems,
    customerId,
    discount,
    amountPaid,
    paymentMethod,
    amountPaidMethod = "",
    debtDueDate = "",
    mobileMoneyNetwork = "",
    mobileMoneyNumber = "",
    idempotencyKey,
  }) {
    if (!cartItems.length) {
      throw new Error("Add at least one product to the sale.");
    }

    cartItems.forEach((cartItem) => {
      const product = findCurrentProduct(cartItem.productId);
      const availableStock = Number(
        product?.availableStock ?? product?.stock ?? 0,
      );

      if (!product || product.status !== "active") {
        throw new Error(
          `${cartItem.name} is not available in this business.`,
        );
      }

      if (Number(cartItem.quantity) > availableStock) {
        throw new Error(
          `Only ${availableStock} ${product.unit}(s) of ${product.name} remain.`,
        );
      }
    });

    const subtotal = cartItems.reduce(
      (sum, item) =>
        sum + Number(item.quantity) * Number(item.unitPrice),
      0,
    );
    const safeDiscount = Math.max(0, Number(discount) || 0);
    const total = Math.max(0, subtotal - safeDiscount);
    const safeAmountPaid = Math.max(0, Number(amountPaid) || 0);
    const selectedCustomer = currentCustomers.find(
      (customer) => String(customer.id) === String(customerId),
    );

    if (safeDiscount > subtotal) {
      throw new Error("Discount cannot be greater than the subtotal.");
    }

    if (paymentMethod === "mobile_money") {
      if (!String(mobileMoneyNetwork || "").trim()) {
        throw new Error("Select the customer's Mobile Money network.");
      }

      if (!String(mobileMoneyNumber || "").trim()) {
        throw new Error("Enter the customer's Mobile Money number.");
      }
    }

    if (paymentMethod === "credit" && !selectedCustomer) {
      throw new Error(
        "Select a customer for a credit or part-payment sale.",
      );
    }

    if (safeAmountPaid > total) {
      throw new Error(
        "Amount paid cannot be greater than the sale total.",
      );
    }

    if (
      paymentMethod === "credit" &&
      safeAmountPaid > 0 &&
      !amountPaidMethod
    ) {
      throw new Error(
        "Select how the initial payment was received.",
      );
    }

    const outstandingBalance = Math.max(
      0,
      total - safeAmountPaid,
    );

    if (
      paymentMethod === "credit" &&
      outstandingBalance > 0 &&
      !String(debtDueDate || "").trim()
    ) {
      throw new Error(
        "Select the date when this debt is due.",
      );
    }

    const requestKey =
      idempotencyKey ||
      (typeof window.crypto?.randomUUID === "function"
        ? window.crypto.randomUUID()
        : createId("sale"));

    const response = await apiRequest(
      `/businesses/${business.id}/sales/`,
      {
        method: "POST",
        headers: {
          "Idempotency-Key": requestKey,
        },
        body: JSON.stringify({
          items: cartItems.map((item) => ({
            productId: item.productId,
            quantity: Number(item.quantity),
            unitPrice: Number(item.unitPrice),
          })),
          customerId: customerId || null,
          discount: safeDiscount,
          amountPaid:
            paymentMethod === "credit" ? safeAmountPaid : total,
          paymentMethod,
          amountPaidMethod:
            paymentMethod === "credit" && safeAmountPaid > 0
              ? amountPaidMethod
              : "",
          debtDueDate:
            paymentMethod === "credit" &&
            outstandingBalance > 0
              ? String(debtDueDate).trim()
              : null,
          mobileMoneyNetwork:
            paymentMethod === "mobile_money"
              ? String(mobileMoneyNetwork).trim()
              : "",
          mobileMoneyNumber:
            paymentMethod === "mobile_money"
              ? String(mobileMoneyNumber).trim()
              : "",
        }),
      },
    );
    const nextSale = normalizeSale(response);

    setSales((current) =>
      upsertBusinessRecord(current, nextSale),
    );

    setPayments((current) =>
      (nextSale.payments ?? []).reduce(
        (records, payment) =>
          upsertBusinessRecord(records, payment),
        current,
      ),
    );

    if (nextSale.status === "pending_payment") {
      // Refreshes reserved stock without pretending payment has completed.
      loadInventory(business.id).catch(() => {});
      return nextSale;
    }

    // Updates the visible stock immediately from the confirmed invoice.
    setProducts((current) =>
      current.map((product) => {
        const soldItem = nextSale.items.find(
          (item) => String(item.productId) === String(product.id),
        );

        if (!soldItem) return product;

        const nextStock = Math.max(
          0,
          Number(product.stock ?? 0) - soldItem.quantity,
        );
        const reservedStock = Number(product.reservedStock ?? 0);

        return {
          ...product,
          stock: nextStock,
          availableStock: Math.max(0, nextStock - reservedStock),
        };
      }),
    );

    const saleMovements = nextSale.items.map((item) => ({
      id: `sale-${nextSale.id}-${item.productId}`,
      productId: item.productId,
      productName: item.name,
      businessType: nextSale.businessType,
      businessId: nextSale.businessId,
      type: "sale",
      quantity: -item.quantity,
      unit: item.unit,
      reason: `Sale ${nextSale.saleNumber}`,
      user: nextSale.cashier,
      createdAt: nextSale.completedAt ?? nextSale.createdAt,
    }));

    setStockMovements((current) => [
      ...saleMovements,
      ...current.filter(
        (movement) =>
          !saleMovements.some(
            (nextMovement) => nextMovement.id === movement.id,
          ),
      ),
    ]);

    if (nextSale.customerId) {
      setCustomers((current) =>
        current.map((customer) =>
          String(customer.id) === String(nextSale.customerId)
            ? {
                ...customer,
                outstandingBalance:
                  Number(customer.outstandingBalance ?? 0) +
                  nextSale.outstandingBalance,
                totalPurchases:
                  Number(customer.totalPurchases ?? 0) + nextSale.total,
              }
            : customer,
        ),
      );
    }

    // Reconciles the optimistic screen values with authoritative API data.
    loadInventory(business.id).catch(() => {});
    loadCustomers(business.id).catch(() => {});

    return nextSale;
  }

  async function verifyMobileMoneySale(reference) {
    const safeReference = String(reference || "").trim();

    if (!safeReference) {
      throw new Error("The Mobile Money payment reference is missing.");
    }

    const response = await apiRequest(
      `/businesses/${business.id}/sales/mobile-money/${encodeURIComponent(
        safeReference,
      )}/verify/`,
      {
        method: "POST",
      },
    );
    const nextSale = normalizeSale(response);

    setSales((current) =>
      upsertBusinessRecord(current, nextSale),
    );

    setPayments((current) =>
      (nextSale.payments ?? []).reduce(
        (records, payment) =>
          upsertBusinessRecord(records, payment),
        current,
      ),
    );

    // Uses backend-authoritative stock, movement and customer balances.
    await Promise.allSettled([
      loadInventory(business.id),
      loadCustomers(business.id),
    ]);

    return nextSale;
  }


  async function addTeamMember(member) {
    const response = await apiRequest(
      `/businesses/${business.id}/team/`,
      {
        method: "POST",
        body: JSON.stringify({
          name: String(member.name || "").trim(),
          email: String(member.email || "")
            .trim()
            .toLowerCase(),
          phone: String(member.phone || "").trim(),
          role: member.role || "cashier",
        }),
      },
    );

    const nextMember = normalizeTeamMember(response, business);

    setTeam((current) => [
      ...current.filter(
        (item) => String(item.id) !== String(nextMember.id),
      ),
      nextMember,
    ]);

    return nextMember;
  }

  // Soft-removes access from the active business without deleting the user.
  async function deleteTeamMember(memberId) {
    const member = team.find(
      (item) => String(item.id) === String(memberId),
    );

    if (!member) {
      throw new Error("This team member could not be found.");
    }

    if (member.role === "owner") {
      throw new Error(
        "The business owner account cannot be removed.",
      );
    }

    await apiRequest(
      `/businesses/${business.id}/team/${memberId}/`,
      {
        method: "DELETE",
      },
    );

    setTeam((current) =>
      current.filter(
        (item) => String(item.id) !== String(memberId),
      ),
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
      customersLoading,
      customersError,
      loadCustomers,
      salesLoading,
      salesError,
      loadSales,
      products: currentProducts,
      customers: currentCustomers,
      sales: currentSales,
      payments: currentPayments,
      stockMovements: currentStockMovements,
      team: currentTeam,
      teamLoading,
      teamError,
      loadTeam,
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
      verifyMobileMoneySale,
      addTeamMember,
      deleteTeamMember,
    }),
    [
      activeBusinessId,
      business,
      businesses,
      businessesError,
      businessesLoading,
      customersError,
      customersLoading,
      inventoryError,
      inventoryLoading,
      salesError,
      salesLoading,
      currentCustomers,
      currentProducts,
      currentSales,
      currentPayments,
      currentStockMovements,
      currentTeam,
      teamError,
      teamLoading,
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
