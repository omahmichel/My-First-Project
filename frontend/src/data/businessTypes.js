export const BUSINESS_TYPE_OPTIONS = Object.freeze([
  {
    value: "building_materials",
    label: "Building materials",
    onboardingTitle: "Building materials shop",
    description: "Tiles, cement, paint, plumbing, roofing and related products.",
    detail: "Includes specialist tile design numbers, boxes, loose pieces and coverage.",
    dealerLabel: "building materials",
    inventoryRoute: "/app/tiles",
    inventoryLabel: "Tile inventory",
    inventoryTitle: "Tile Inventory",
  },
  {
    value: "boutique",
    label: "Boutique",
    onboardingTitle: "Boutique or fashion store",
    description: "Clothing, shoes, bags, accessories and related products.",
    detail: "Includes size, colour, style codes and product variants.",
    dealerLabel: "fashion items",
    inventoryRoute: "/app/boutique",
    inventoryLabel: "Boutique inventory",
    inventoryTitle: "Boutique Inventory",
  },
  {
    value: "provision_mini_mart",
    label: "Provision Shop & Mini Mart",
    onboardingTitle: "Provision Shop & Mini Mart",
    description: "Groceries, drinks, household essentials and fast-moving retail items.",
    detail: "Designed for everyday stock, pack sizes, expiry-aware items and quick cashier sales.",
    dealerLabel: "provision and mini-mart items",
    inventoryRoute: "/app/provision-mini-mart",
    inventoryLabel: "Provision inventory",
    inventoryTitle: "Provision Shop & Mini Mart Inventory",
  },
  {
    value: "phone_electronics_accessories",
    label: "Phone & Electronics Accessories",
    onboardingTitle: "Phone & Electronics Accessories",
    description: "Phones, chargers, cases, power banks, audio and smart accessories.",
    detail: "Designed for brands, model compatibility, variants, warranty references and accessories.",
    dealerLabel: "phone and electronics accessories",
    inventoryRoute: "/app/phone-accessories",
    inventoryLabel: "Phone & accessories",
    inventoryTitle: "Phone & Electronics Accessories Inventory",
  },
  {
    value: "electrical_electronics",
    label: "Electrical / Electronics Shop",
    onboardingTitle: "Electrical / Electronics Shop",
    description: "Electrical fittings, cables, lighting, appliances and electronic products.",
    detail: "Designed for model references, ratings, voltage, warranty and technical specifications.",
    dealerLabel: "electrical and electronics products",
    inventoryRoute: "/app/electrical-electronics",
    inventoryLabel: "Electrical inventory",
    inventoryTitle: "Electrical / Electronics Inventory",
  },
  {
    value: "auto_spare_parts",
    label: "Auto Spare Parts",
    onboardingTitle: "Auto Spare Parts Shop",
    description: "Vehicle parts, batteries, filters, lubricants and automotive accessories.",
    detail: "Designed for part numbers, OEM references, vehicle compatibility and technical fitment.",
    dealerLabel: "auto spare parts and accessories",
    inventoryRoute: "/app/auto-spare-parts",
    inventoryLabel: "Spare parts inventory",
    inventoryTitle: "Auto Spare Parts Inventory",
  },
  {
    value: "cosmetics_beauty",
    label: "Cosmetics & Beauty",
    onboardingTitle: "Cosmetics & Beauty Shop",
    description: "Skincare, haircare, makeup, fragrances and beauty accessories.",
    detail: "Designed for shades, sizes, beauty categories, batches and expiry-aware products.",
    dealerLabel: "cosmetics and beauty products",
    inventoryRoute: "/app/cosmetics-beauty",
    inventoryLabel: "Beauty inventory",
    inventoryTitle: "Cosmetics & Beauty Inventory",
  },
]);

export const BUSINESS_TYPE_MAP = Object.freeze(
  Object.fromEntries(
    BUSINESS_TYPE_OPTIONS.map((item) => [item.value, item]),
  ),
);

export const RETAIL_BUSINESS_TYPES = Object.freeze([
  "provision_mini_mart",
  "phone_electronics_accessories",
  "electrical_electronics",
  "auto_spare_parts",
  "cosmetics_beauty",
]);

export function businessTypeConfig(type) {
  return BUSINESS_TYPE_MAP[type] ?? {
    value: type || "",
    label: "Business",
    onboardingTitle: "Business",
    description: "StockFlow business workspace.",
    detail: "Shared inventory, sales and reporting tools.",
    dealerLabel: "products",
    inventoryRoute: "/app/products",
    inventoryLabel: "Inventory",
    inventoryTitle: "Inventory",
  };
}

export function businessTypeLabel(type) {
  return businessTypeConfig(type).label;
}
