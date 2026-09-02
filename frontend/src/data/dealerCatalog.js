export const DEALER_CATALOG = Object.freeze({
  building_materials: [
    "Tiles", "Cement", "Paints", "Blocks", "Sand", "Gravel and Stones",
    "Iron Rods and Rebars", "Binding Wire", "Wire Mesh", "Roofing Sheets",
    "Roofing Accessories", "Plywood", "Timber", "Doors", "Windows",
    "Ceiling Boards", "Gypsum Boards", "Tile Adhesives", "Grout",
    "Sanitary Ware", "Plumbing Pipes", "Plumbing Fittings",
    "Electrical Cables", "Electrical Fittings", "Water Tanks",
    "Nails and Fasteners", "Locks and Hinges", "Hardware and Tools",
    "Waterproofing Materials", "Concrete Products",
  ],
  boutique: [
    "Men's Clothing", "Women's Clothing", "Children's Clothing", "Shirts",
    "T-Shirts", "Trousers", "Jeans", "Dresses", "Skirts", "Shorts",
    "Suits and Blazers", "Traditional Wear", "Sportswear", "Footwear",
    "Bags", "Belts", "Caps and Hats", "Jewellery", "Watches",
    "Fashion Accessories", "Fabrics", "Underwear", "Sleepwear", "Scarves",
    "Sunglasses", "Hair Accessories", "School Wear", "Work Wear",
    "Unisex Clothing", "Beauty Accessories",
  ],
});

export function dealerCatalogForBusinessType(businessType) {
  return DEALER_CATALOG[businessType] ?? [];
}

export function businessTypeDealerLabel(businessType) {
  return businessType === "boutique" ? "fashion items" : "building materials";
}
