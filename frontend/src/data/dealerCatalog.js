import { businessTypeConfig } from "./businessTypes";

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
  provision_mini_mart: [
    "Rice", "Cooking Oil", "Sugar", "Flour", "Milk and Dairy",
    "Bread and Bakery", "Breakfast Cereals", "Noodles and Pasta",
    "Canned Foods", "Tomato Paste and Sauces", "Spices and Seasoning",
    "Biscuits and Snacks", "Chocolate and Sweets", "Soft Drinks",
    "Malt and Energy Drinks", "Bottled Water", "Fruit Juice",
    "Tea and Coffee", "Eggs", "Frozen Foods", "Baby Products",
    "Toiletries", "Tissue and Paper Products", "Laundry Products",
    "Cleaning Supplies", "Household Essentials", "Petty Stationery",
    "Batteries and Small Essentials", "Personal Care", "General Groceries",
  ],
  phone_electronics_accessories: [
    "Smartphones", "Feature Phones", "Phone Cases", "Screen Protectors",
    "Wall Chargers", "Fast Chargers", "USB Cables", "Type-C Cables",
    "Lightning Cables", "Power Banks", "Wired Earphones",
    "Wireless Earbuds", "Headphones", "Bluetooth Speakers",
    "Smart Watches", "Memory Cards", "OTG Adapters", "Car Chargers",
    "Phone Holders", "Selfie Sticks", "Tripods", "Ring Lights",
    "Replacement Batteries", "Phone Displays", "Phone Repair Parts",
    "Laptop Chargers", "Computer Accessories", "Storage Devices",
    "Adapters and Converters", "Mobile Accessories",
  ],
  electrical_electronics: [
    "Electrical Cables and Wires", "Sockets and Outlets", "Switches",
    "LED Bulbs", "Lighting Fixtures", "Extension Boards",
    "Circuit Breakers", "Distribution Boards", "Plugs and Adaptors",
    "Conduits and Trunking", "Electrical Fittings", "Ceiling Fans",
    "Standing Fans", "Televisions", "Decoders and Receivers",
    "Refrigerators", "Freezers", "Microwaves", "Electric Irons",
    "Blenders", "Kettles", "Rice Cookers", "Washing Machines",
    "Air Conditioners", "Speakers and Sound Systems", "Solar Accessories",
    "Inverters", "Voltage Regulators", "Small Appliances",
    "Electronic Accessories",
  ],
  auto_spare_parts: [
    "Engine Parts", "Brake Pads and Shoes", "Brake Discs and Drums",
    "Oil Filters", "Air Filters", "Fuel Filters", "Spark Plugs",
    "Belts and Tensioners", "Bearings", "Suspension Parts",
    "Shock Absorbers", "Steering Parts", "Clutch Parts",
    "Transmission Parts", "Radiators and Cooling", "Water Pumps",
    "Fuel System Parts", "Electrical and Sensor Parts", "Car Batteries",
    "Automotive Bulbs", "Wiper Blades", "Mirrors", "Body Parts",
    "Bumpers and Grilles", "Tyres and Tubes", "Wheel Accessories",
    "Engine Oil and Lubricants", "Coolants and Fluids",
    "Car Care Accessories", "General Spare Parts",
  ],
  cosmetics_beauty: [
    "Body Lotions", "Body Creams", "Body Oils", "Face Creams",
    "Facial Cleansers", "Serums", "Sunscreen", "Soaps and Shower Gels",
    "Deodorants", "Perfumes and Fragrances", "Lip Products",
    "Foundation and Powder", "Eye Makeup", "Makeup Accessories",
    "Nail Products", "Hair Creams", "Hair Oils", "Shampoo and Conditioner",
    "Hair Treatments", "Hair Relaxers", "Wigs and Extensions",
    "Braiding Hair", "Barber Products", "Beauty Tools",
    "Skincare Sets", "Baby Skin Care", "Men's Grooming",
    "Bath Accessories", "Personal Care", "Beauty Accessories",
  ],
});

export function dealerCatalogForBusinessType(businessType) {
  return DEALER_CATALOG[businessType] ?? [];
}

export function businessTypeDealerLabel(businessType) {
  return businessTypeConfig(businessType).dealerLabel;
}
