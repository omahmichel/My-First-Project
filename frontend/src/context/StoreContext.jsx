import { createContext, useContext, useEffect, useMemo, useState } from "react";

import {
  seedBusiness,
  seedCustomers,
  seedProducts,
  seedSales,
  seedStockMovements,
  seedTeam,
} from "../data/seedData";
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
  const [businesses, setBusinesses] = useState(loadInitialBusinesses);
  const [activeBusinessId, setActiveBusinessId] = useState(() => {
    const legacyBusiness = loadStoredValue("business", seedBusiness);
    const fallbackId =
      BUSINESS_IDS_BY_TYPE[legacyBusiness.type] ?? "business_phildial";

    return loadStoredValue("active_business_id", fallbackId);
  });
  const [products, setProducts] = useState(() =>
    loadBusinessRecords("products", seedProducts, "business_phildial"),
  );
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

  function addProduct(product) {
    const nextProduct = {
      ...product,
      id: createId("product"),
      businessType: business.type,
      businessId: business.id,
      stock: Number(product.stock) || 0,
      loosePieces: Number(product.loosePieces) || 0,
      costPrice: Number(product.costPrice) || 0,
      sellingPrice: Number(product.sellingPrice) || 0,
      lowStockLevel: Number(product.lowStockLevel) || 0,
      status: "active",
    };

    setProducts((current) => [nextProduct, ...current]);

    if (nextProduct.stock > 0) {
      setStockMovements((current) => [
        {
          id: createId("movement"),
          productId: nextProduct.id,
          productName: nextProduct.name,
          businessType: business.type,
          businessId: business.id,
          type: "opening_stock",
          quantity: nextProduct.stock,
          unit: nextProduct.unit,
          reason: "Opening stock entered",
          user: "Business Owner",
          createdAt: new Date().toISOString(),
        },
        ...current,
      ]);
    }

    return nextProduct;
  }

  function updateProduct(productId, changes) {
    if (!findCurrentProduct(productId)) {
      throw new Error("You cannot update a product outside this business type.");
    }

    setProducts((current) =>
      current.map((product) =>
        product.id === productId
          ? {
              ...product,
              ...changes,
              businessType: business.type,
              businessId: business.id,
              stock: Number(changes.stock ?? product.stock),
              loosePieces: Number(changes.loosePieces ?? product.loosePieces ?? 0),
              costPrice: Number(changes.costPrice ?? product.costPrice),
              sellingPrice: Number(changes.sellingPrice ?? product.sellingPrice),
              lowStockLevel: Number(changes.lowStockLevel ?? product.lowStockLevel),
            }
          : product,
      ),
    );
  }

  function toggleProductStatus(productId) {
    if (!findCurrentProduct(productId)) {
      throw new Error("You cannot change a product outside this business type.");
    }

    setProducts((current) =>
      current.map((product) =>
        product.id === productId
          ? { ...product, status: product.status === "active" ? "inactive" : "active" }
          : product,
      ),
    );
  }


  // Permanently removes only unsold products from the active business inventory.
  function deleteProduct(productId) {
    const product = findCurrentProduct(productId);

    if (!product) {
      throw new Error("You cannot delete a product outside this business type.");
    }

    const hasSalesHistory = sales.some((sale) =>
      (sale.items ?? []).some((item) => item.productId === productId),
    );

    if (hasSalesHistory) {
      throw new Error(
        "This product already has sales or invoice history. Deactivate it instead.",
      );
    }

    setProducts((current) =>
      current.filter((item) => item.id !== productId),
    );

    setStockMovements((current) =>
      current.filter((movement) => movement.productId !== productId),
    );

    return product;
  }

  function adjustStock({ productId, quantity, type, reason, user = "Business Owner" }) {
    const adjustment = Number(quantity);
    const product = findCurrentProduct(productId);

    if (!product) throw new Error("Product not found in this business inventory.");
    if (!adjustment) throw new Error("Enter a stock adjustment quantity.");
    if (product.stock + adjustment < 0) {
      throw new Error("This adjustment would reduce stock below zero.");
    }

    setProducts((current) =>
      current.map((item) =>
        item.id === productId ? { ...item, stock: item.stock + adjustment } : item,
      ),
    );

    setStockMovements((current) => [
      {
        id: createId("movement"),
        productId,
        productName: product.designCode
          ? `${product.name} — ${product.designCode}`
          : product.name,
        businessType: business.type,
        businessId: business.id,
        type,
        quantity: adjustment,
        unit: product.unit,
        reason,
        user,
        createdAt: new Date().toISOString(),
      },
      ...current,
    ]);
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
      (sum, product) => sum + product.stock * product.costPrice,
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
