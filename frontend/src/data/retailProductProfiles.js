const textField = (key, label, placeholder, extra = {}) => ({
  key,
  label,
  placeholder,
  ...extra,
});

const numberField = (key, label, placeholder, extra = {}) => ({
  key,
  label,
  placeholder,
  type: "number",
  ...extra,
});

const dateField = (key, label, extra = {}) => ({
  key,
  label,
  type: "date",
  ...extra,
});

const COMMON_WARRANTY = textField("warranty", "Warranty", "12 months");
const COMMON_COLOUR = textField("colour", "Colour", "Black / Silver / Blue");
const COMMON_MODEL = textField("model", "Model", "Model / product line");
const COMMON_CONDITION = textField("condition", "Condition", "New / Used / Refurbished", {
  options: ["New", "Used", "Refurbished", "Open box"],
});

const PHONE_PROFILES = {
  smartphone: {
    groupKeys: ["model", "series"],
    variantKeys: ["storageCapacity", "ram", "colour", "condition"],
    fields: [
      COMMON_MODEL,
      textField("series", "Series / generation", "iPhone 16 / Galaxy S series"),
      textField("storageCapacity", "Storage capacity", "128 GB / 256 GB / 512 GB / 1 TB"),
      textField("ram", "RAM", "8 GB / 12 GB"),
      COMMON_COLOUR,
      COMMON_CONDITION,
      textField("simType", "SIM type", "Dual SIM / eSIM / Nano SIM"),
      textField("networkTechnology", "Network", "4G LTE / 5G"),
      textField("screenSize", "Screen size", "6.7 inches"),
      textField("displayType", "Display type", "OLED / AMOLED / LCD"),
      textField("processor", "Processor / chipset", "A18 Pro / Snapdragon 8 Gen 3"),
      textField("batteryCapacity", "Battery capacity", "5000 mAh"),
      textField("cameraSpecification", "Camera specification", "48 MP + 12 MP"),
      textField("operatingSystem", "Operating system", "iOS / Android"),
      textField("imeiSerial", "IMEI / serial number", "IMEI or serial reference"),
      COMMON_WARRANTY,
    ],
  },
  featurePhone: {
    groupKeys: ["model"],
    variantKeys: ["colour", "simType"],
    fields: [
      COMMON_MODEL,
      COMMON_COLOUR,
      COMMON_CONDITION,
      textField("simType", "SIM type", "Single SIM / Dual SIM"),
      textField("networkTechnology", "Network", "2G / 3G / 4G"),
      textField("screenSize", "Screen size", "2.4 inches"),
      textField("batteryCapacity", "Battery capacity", "1450 mAh"),
      textField("memorySupport", "Memory card support", "Up to 32 GB"),
      textField("imeiSerial", "IMEI / serial number", "IMEI or serial reference"),
      COMMON_WARRANTY,
    ],
  },
  tablet: {
    groupKeys: ["model", "series"],
    variantKeys: ["storageCapacity", "ram", "connectivity", "colour"],
    fields: [
      COMMON_MODEL,
      textField("series", "Series / generation", "iPad Air / Galaxy Tab S"),
      textField("storageCapacity", "Storage capacity", "128 GB / 256 GB"),
      textField("ram", "RAM", "8 GB"),
      textField("screenSize", "Screen size", "11 inches"),
      textField("connectivity", "Connectivity", "Wi-Fi / Wi-Fi + Cellular"),
      textField("simType", "SIM type", "eSIM / Nano SIM"),
      textField("processor", "Processor / chipset", "M2 / Snapdragon"),
      textField("batteryCapacity", "Battery capacity", "8000 mAh"),
      textField("operatingSystem", "Operating system", "iPadOS / Android / Windows"),
      COMMON_COLOUR,
      COMMON_CONDITION,
      textField("serialNumber", "Serial number", "Device serial reference"),
      COMMON_WARRANTY,
    ],
  },
  laptop: {
    groupKeys: ["model", "series"],
    variantKeys: ["processor", "ram", "storageCapacity", "screenSize"],
    fields: [
      COMMON_MODEL,
      textField("series", "Series / family", "EliteBook / ThinkPad / MacBook Air"),
      textField("processor", "Processor", "Intel Core i7 / Ryzen 7 / Apple M3"),
      textField("processorGeneration", "Processor generation", "13th Gen / Ryzen 7000 series"),
      textField("ram", "RAM", "8 GB / 16 GB / 32 GB"),
      textField("storageType", "Storage type", "SSD / NVMe SSD / HDD"),
      textField("storageCapacity", "Storage capacity", "256 GB / 512 GB / 1 TB"),
      textField("screenSize", "Screen size", "14 inches / 15.6 inches"),
      textField("screenResolution", "Screen resolution", "1920 x 1080 / 2560 x 1600"),
      textField("graphics", "Graphics / GPU", "Intel Iris Xe / RTX 4060"),
      textField("operatingSystem", "Operating system", "Windows 11 Pro / macOS"),
      textField("touchscreen", "Touchscreen", "Yes / No", { options: ["Yes", "No"] }),
      textField("keyboardLayout", "Keyboard layout", "US / UK / French"),
      COMMON_COLOUR,
      COMMON_CONDITION,
      textField("batteryCondition", "Battery condition", "Excellent / 85% health"),
      textField("serialNumber", "Serial number", "Device serial reference"),
      COMMON_WARRANTY,
    ],
  },
  desktop: {
    groupKeys: ["model", "series"],
    variantKeys: ["processor", "ram", "storageCapacity", "formFactor"],
    fields: [
      COMMON_MODEL,
      textField("series", "Series / family", "OptiPlex / ProDesk / iMac"),
      textField("processor", "Processor", "Intel Core i5 / Ryzen 5"),
      textField("processorGeneration", "Processor generation", "12th Gen"),
      textField("ram", "RAM", "16 GB"),
      textField("storageType", "Storage type", "SSD / HDD"),
      textField("storageCapacity", "Storage capacity", "512 GB"),
      textField("graphics", "Graphics / GPU", "Integrated / RTX 3060"),
      textField("formFactor", "Form factor", "Tower / Mini / All-in-one"),
      textField("operatingSystem", "Operating system", "Windows 11 Pro"),
      textField("monitorIncluded", "Monitor included", "Yes / No", { options: ["Yes", "No"] }),
      COMMON_CONDITION,
      textField("serialNumber", "Serial number", "Device serial reference"),
      COMMON_WARRANTY,
    ],
  },
  monitor: {
    groupKeys: ["model"],
    variantKeys: ["screenSize", "resolution", "refreshRate"],
    fields: [
      COMMON_MODEL,
      textField("screenSize", "Screen size", "24 inches / 27 inches"),
      textField("resolution", "Resolution", "1920 x 1080 / 4K UHD"),
      textField("panelType", "Panel type", "IPS / VA / OLED"),
      textField("refreshRate", "Refresh rate", "60 Hz / 144 Hz"),
      textField("responseTime", "Response time", "1 ms / 5 ms"),
      textField("ports", "Ports", "HDMI, DisplayPort, USB-C"),
      COMMON_COLOUR,
      COMMON_CONDITION,
      COMMON_WARRANTY,
    ],
  },
  charger: {
    groupKeys: ["modelCompatibility", "connectorType"],
    variantKeys: ["wattage", "colour"],
    fields: [
      textField("modelCompatibility", "Model / compatibility", "iPhone 16 / Samsung / USB-C devices"),
      textField("connectorType", "Connector type", "USB-C / Lightning / Micro USB"),
      textField("wattage", "Power / wattage", "20 W / 45 W / 65 W"),
      textField("fastChargeStandard", "Fast-charge standard", "PD / PPS / Quick Charge"),
      textField("inputRating", "Input rating", "100-240 V"),
      textField("outputRating", "Output rating", "5V 3A / 9V 2.22A"),
      textField("cableIncluded", "Cable included", "Yes / No", { options: ["Yes", "No"] }),
      COMMON_COLOUR,
      COMMON_WARRANTY,
    ],
  },
  cable: {
    groupKeys: ["connectorFrom", "connectorTo"],
    variantKeys: ["length", "powerRating", "colour"],
    fields: [
      textField("connectorFrom", "Connector from", "USB-A / USB-C"),
      textField("connectorTo", "Connector to", "USB-C / Lightning / Micro USB"),
      textField("length", "Cable length", "1 m / 2 m"),
      textField("powerRating", "Power rating", "60 W / 100 W"),
      textField("dataSpeed", "Data speed", "480 Mbps / 10 Gbps"),
      textField("material", "Cable material", "Braided nylon / PVC"),
      COMMON_COLOUR,
      COMMON_WARRANTY,
    ],
  },
  powerBank: {
    groupKeys: ["model", "capacityMah"],
    variantKeys: ["outputWattage", "colour"],
    fields: [
      COMMON_MODEL,
      textField("capacityMah", "Battery capacity", "10,000 mAh / 20,000 mAh"),
      textField("outputWattage", "Maximum output", "20 W / 65 W"),
      textField("inputPorts", "Input ports", "USB-C / Micro USB"),
      textField("outputPorts", "Output ports", "2 x USB-A + USB-C"),
      textField("fastChargeStandard", "Fast-charge support", "PD / PPS / Quick Charge"),
      textField("displayType", "Charge display", "LED percentage / indicator lights"),
      COMMON_COLOUR,
      COMMON_WARRANTY,
    ],
  },
  audio: {
    groupKeys: ["model"],
    variantKeys: ["connectivity", "colour"],
    fields: [
      COMMON_MODEL,
      textField("connectivity", "Connectivity", "Bluetooth 5.3 / Wired / USB-C"),
      textField("batteryLife", "Battery life", "8 hours / 30 hours"),
      textField("noiseCancellation", "Noise cancellation", "ANC / Passive / None"),
      textField("microphone", "Microphone", "Built-in / Dual mic"),
      textField("waterResistance", "Water resistance", "IPX4 / IP67"),
      textField("driverSize", "Driver size", "10 mm / 40 mm"),
      COMMON_COLOUR,
      COMMON_WARRANTY,
    ],
  },
  smartwatch: {
    groupKeys: ["model", "series"],
    variantKeys: ["caseSize", "connectivity", "colour"],
    fields: [
      COMMON_MODEL,
      textField("series", "Series / generation", "Series 10 / Watch 7"),
      textField("compatibility", "Phone compatibility", "iPhone / Android"),
      textField("caseSize", "Case / display size", "42 mm / 46 mm"),
      textField("connectivity", "Connectivity", "Bluetooth / LTE / Wi-Fi"),
      textField("batteryLife", "Battery life", "18 hours / 7 days"),
      textField("gps", "GPS", "Built-in / Connected"),
      textField("waterResistance", "Water resistance", "5 ATM / IP68"),
      textField("strapSize", "Strap size", "S/M / M/L"),
      COMMON_COLOUR,
      COMMON_WARRANTY,
    ],
  },
  storage: {
    groupKeys: ["storageType", "model"],
    variantKeys: ["storageCapacity", "interfaceType"],
    fields: [
      COMMON_MODEL,
      textField("storageType", "Storage type", "MicroSD / USB flash / SSD / HDD"),
      textField("storageCapacity", "Storage capacity", "64 GB / 1 TB"),
      textField("interfaceType", "Interface", "USB 3.2 / USB-C / NVMe / SATA"),
      textField("readWriteSpeed", "Read / write speed", "Up to 1050 MB/s"),
      textField("formFactor", "Form factor", "2.5 inch / M.2 2280"),
      COMMON_WARRANTY,
    ],
  },
  network: {
    groupKeys: ["model", "networkTechnology"],
    variantKeys: ["maxSpeed", "wifiStandard"],
    fields: [
      COMMON_MODEL,
      textField("networkTechnology", "Mobile network", "4G LTE / 5G"),
      textField("maxSpeed", "Maximum speed", "300 Mbps / 1 Gbps"),
      textField("simType", "SIM type", "Nano SIM / eSIM"),
      textField("wifiStandard", "Wi-Fi standard", "Wi-Fi 5 / Wi-Fi 6"),
      textField("lanPorts", "LAN ports", "1 / 4"),
      textField("batteryCapacity", "Battery capacity", "5000 mAh"),
      textField("carrierLock", "Network lock", "Unlocked / MTN / Telecel"),
      COMMON_WARRANTY,
    ],
  },
  accessory: {
    groupKeys: ["modelCompatibility", "itemType"],
    variantKeys: ["sizeSpecification", "colour"],
    fields: [
      textField("itemType", "Type / style", "Case / stand / adapter / accessory type"),
      textField("modelCompatibility", "Model / compatibility", "iPhone 15 Pro / USB-C devices"),
      textField("sizeSpecification", "Size / specification", "Size / capacity / dimensions"),
      textField("material", "Material", "Silicone / aluminium / glass"),
      textField("connectorType", "Connector / interface", "USB-C / HDMI / Bluetooth"),
      COMMON_COLOUR,
      COMMON_WARRANTY,
    ],
  },
};

const PROVISION_PROFILES = {
  grocery: {
    groupKeys: ["productLine", "variant"],
    variantKeys: ["packSize", "netWeightVolume", "flavourVariant"],
    fields: [
      textField("productLine", "Product line / type", "Jasmine rice / powdered milk"),
      textField("variant", "Variant", "Original / Light / Premium"),
      textField("packSize", "Pack size", "12 x 500 ml / 24 sachets"),
      textField("netWeightVolume", "Net weight / volume", "5 kg / 500 ml"),
      textField("flavourVariant", "Flavour / variety", "Chocolate / Strawberry"),
      textField("barcode", "Barcode", "Scan or enter barcode"),
      textField("batchNumber", "Batch / lot number", "LOT-2409"),
      dateField("manufactureDate", "Manufacture date"),
      dateField("expiryDate", "Expiry / best-before date"),
      textField("countryOfOrigin", "Country of origin", "Ghana"),
      numberField("wholesalePrice", "Wholesale price (GHS)", "0.00", { step: "0.01" }),
    ],
  },
  beverage: {
    groupKeys: ["productLine", "flavourVariant"],
    variantKeys: ["volumeSize", "packCount", "packagingType"],
    fields: [
      textField("productLine", "Drink type / product line", "Cola / Malt / Juice"),
      textField("flavourVariant", "Flavour / variant", "Orange / Pineapple / Original"),
      textField("volumeSize", "Bottle / can size", "330 ml / 500 ml / 1.5 L"),
      textField("packCount", "Units per pack", "6 / 12 / 24"),
      textField("packagingType", "Packaging", "Bottle / Can / Tetra pack / Sachet"),
      textField("barcode", "Barcode", "Scan or enter barcode"),
      textField("batchNumber", "Batch / lot number", "LOT-2409"),
      dateField("expiryDate", "Expiry / best-before date"),
      numberField("wholesalePrice", "Wholesale price (GHS)", "0.00", { step: "0.01" }),
    ],
  },
  household: {
    groupKeys: ["productLine", "variant"],
    variantKeys: ["volumeSize", "packCount", "scent"],
    fields: [
      textField("productLine", "Product type / line", "Laundry powder / Dishwashing liquid"),
      textField("variant", "Variant", "Sensitive / Extra strength"),
      textField("volumeSize", "Size / volume", "500 ml / 1 kg"),
      textField("packCount", "Units per pack", "1 / 6 / 12"),
      textField("scent", "Scent / fragrance", "Lemon / Lavender / Unscented"),
      textField("barcode", "Barcode", "Scan or enter barcode"),
      textField("batchNumber", "Batch / lot number", "LOT-2409"),
      dateField("expiryDate", "Expiry date"),
      numberField("wholesalePrice", "Wholesale price (GHS)", "0.00", { step: "0.01" }),
    ],
  },
};

const ELECTRICAL_PROFILES = {
  generic: {
    groupKeys: ["modelNumber", "itemType"],
    variantKeys: ["voltage", "wattage", "sizeSpecification"],
    fields: [
      textField("itemType", "Type / series", "Product type / series"),
      textField("modelNumber", "Model number", "Model / reference"),
      textField("voltage", "Voltage", "220-240 V"),
      textField("wattage", "Wattage / power rating", "15 W / 2.5 kVA"),
      textField("amperage", "Current / amperage", "13 A / 32 A"),
      textField("frequency", "Frequency", "50 Hz"),
      textField("phase", "Phase", "Single phase / Three phase"),
      textField("sizeSpecification", "Size / dimensions", "Dimensions / capacity"),
      COMMON_COLOUR,
      COMMON_WARRANTY,
    ],
  },
  cable: {
    groupKeys: ["cableType", "cableSize"],
    variantKeys: ["coreCount", "length", "voltageRating"],
    fields: [
      textField("cableType", "Cable / wire type", "Flexible / Armoured / Twin & earth"),
      textField("cableSize", "Cable size", "1.5 mm² / 2.5 mm² / 6 mm²"),
      textField("coreCount", "Number of cores", "2 core / 3 core / 4 core"),
      textField("length", "Length", "10 m / 100 m coil"),
      textField("conductorMaterial", "Conductor material", "Copper / Aluminium"),
      textField("voltageRating", "Voltage rating", "300/500 V / 0.6/1 kV"),
      textField("currentRating", "Current rating", "20 A"),
      textField("insulationType", "Insulation", "PVC / XLPE"),
    ],
  },
  lighting: {
    groupKeys: ["modelNumber", "lightType"],
    variantKeys: ["wattage", "colourTemperature", "baseType"],
    fields: [
      textField("lightType", "Light type", "LED bulb / Panel / Floodlight"),
      textField("modelNumber", "Model number", "Model / reference"),
      textField("wattage", "Wattage", "9 W / 18 W / 50 W"),
      textField("voltage", "Voltage", "220-240 V"),
      textField("lumenOutput", "Brightness / lumens", "900 lm"),
      textField("colourTemperature", "Colour temperature", "3000K / 6500K"),
      textField("baseType", "Base / fitting", "E27 / B22 / GU10"),
      textField("dimensions", "Dimensions", "Size / diameter"),
      COMMON_WARRANTY,
    ],
  },
  television: {
    groupKeys: ["modelNumber", "series"],
    variantKeys: ["screenSize", "resolution", "displayTechnology"],
    fields: [
      textField("modelNumber", "Model number", "Model / reference"),
      textField("series", "Series", "Crystal UHD / OLED C Series"),
      textField("screenSize", "Screen size", "43 inches / 55 inches"),
      textField("resolution", "Resolution", "Full HD / 4K UHD / 8K"),
      textField("displayTechnology", "Display technology", "LED / QLED / OLED"),
      textField("smartPlatform", "Smart TV platform", "Google TV / webOS / Tizen"),
      textField("refreshRate", "Refresh rate", "60 Hz / 120 Hz"),
      textField("ports", "Ports", "HDMI x3, USB x2"),
      COMMON_WARRANTY,
    ],
  },
  appliance: {
    groupKeys: ["modelNumber", "itemType"],
    variantKeys: ["capacity", "wattage", "colour"],
    fields: [
      textField("itemType", "Appliance type / series", "Double-door / Front-load / Digital"),
      textField("modelNumber", "Model number", "Model / reference"),
      textField("capacity", "Capacity", "200 L / 8 kg / 1.7 L"),
      textField("voltage", "Voltage", "220-240 V"),
      textField("wattage", "Power consumption", "1500 W"),
      textField("energyRating", "Energy rating", "A+++ / 4 star"),
      textField("dimensions", "Dimensions", "W x H x D"),
      COMMON_COLOUR,
      COMMON_WARRANTY,
    ],
  },
  airConditioner: {
    groupKeys: ["modelNumber", "airconType"],
    variantKeys: ["horsepower", "btu", "inverterType"],
    fields: [
      textField("airconType", "AC type", "Split / Floor standing / Window"),
      textField("modelNumber", "Model number", "Model / reference"),
      textField("horsepower", "Horsepower", "1 HP / 1.5 HP / 2 HP"),
      textField("btu", "Cooling capacity (BTU)", "12000 BTU"),
      textField("inverterType", "Inverter", "Inverter / Non-inverter"),
      textField("energyRating", "Energy rating", "4 star / A++"),
      textField("voltage", "Voltage", "220-240 V"),
      textField("refrigerant", "Refrigerant", "R32 / R410A"),
      COMMON_WARRANTY,
    ],
  },
  powerSystem: {
    groupKeys: ["modelNumber", "itemType"],
    variantKeys: ["powerRating", "voltage", "phase"],
    fields: [
      textField("itemType", "System type", "Inverter / UPS / Charge controller / Solar panel"),
      textField("modelNumber", "Model number", "Model / reference"),
      textField("powerRating", "Power rating", "1 kVA / 5 kW / 550 W"),
      textField("voltage", "System voltage", "12 V / 24 V / 48 V"),
      textField("phase", "Phase", "Single phase / Three phase"),
      textField("batteryCompatibility", "Battery compatibility", "Lithium / AGM / 48 V bank"),
      textField("efficiency", "Efficiency", "95%"),
      textField("protectionRating", "Protection rating", "IP65"),
      COMMON_WARRANTY,
    ],
  },
};

const AUTO_PROFILES = {
  part: {
    groupKeys: ["vehicleMake", "vehicleModel", "partType"],
    variantKeys: ["yearRange", "engineType", "position"],
    fields: [
      textField("partType", "Part type / series", "Front brake pad / Oil filter"),
      textField("oemNumber", "OEM number", "90915-YZZD2"),
      textField("manufacturerPartNumber", "Manufacturer part number", "Part reference"),
      textField("vehicleMake", "Vehicle make", "Toyota"),
      textField("vehicleModel", "Vehicle model", "Corolla"),
      textField("yearRange", "Compatible years", "2008-2018"),
      textField("engineType", "Engine / displacement", "1.8L petrol / 2.0 diesel"),
      textField("transmission", "Transmission", "Automatic / Manual / CVT"),
      textField("position", "Position", "Front / Rear / Left / Right"),
      textField("material", "Material / construction", "Ceramic / Steel / Rubber"),
      textField("countryOfOrigin", "Country of origin", "Japan / Germany"),
      COMMON_WARRANTY,
    ],
  },
  tyre: {
    groupKeys: ["tyreSize", "treadPattern"],
    variantKeys: ["loadIndex", "speedRating", "manufactureDateCode"],
    fields: [
      textField("tyreSize", "Tyre size", "205/55 R16"),
      textField("width", "Width", "205 mm"),
      textField("aspectRatio", "Aspect ratio", "55"),
      textField("rimSize", "Rim size", "16 inches"),
      textField("loadIndex", "Load index", "91"),
      textField("speedRating", "Speed rating", "V / H / W"),
      textField("treadPattern", "Tread / pattern", "Touring / All-terrain"),
      textField("manufactureDateCode", "Manufacture / DOT code", "DOT 2326"),
      textField("tubeless", "Tubeless", "Yes / No", { options: ["Yes", "No"] }),
      COMMON_WARRANTY,
    ],
  },
  battery: {
    groupKeys: ["batteryType", "capacityAh"],
    variantKeys: ["voltage", "coldCrankingAmps", "terminalLayout"],
    fields: [
      textField("batteryType", "Battery type", "AGM / Lead-acid / EFB"),
      textField("voltage", "Voltage", "12 V / 24 V"),
      textField("capacityAh", "Capacity", "45 Ah / 70 Ah / 100 Ah"),
      textField("coldCrankingAmps", "Cold cranking amps (CCA)", "600 A"),
      textField("terminalLayout", "Terminal layout", "L+ / R+"),
      textField("dimensions", "Dimensions", "L x W x H"),
      textField("vehicleCompatibility", "Vehicle compatibility", "Sedan / SUV / Truck / specific models"),
      COMMON_WARRANTY,
    ],
  },
  fluid: {
    groupKeys: ["fluidType", "viscosity"],
    variantKeys: ["volumeSize", "specificationStandard"],
    fields: [
      textField("fluidType", "Fluid / lubricant type", "Engine oil / Coolant / ATF"),
      textField("viscosity", "Viscosity / grade", "5W-30 / 10W-40"),
      textField("volumeSize", "Pack volume", "1 L / 4 L / 5 L"),
      textField("specificationStandard", "Specification / approval", "API SP / ACEA C3"),
      textField("vehicleCompatibility", "Vehicle / engine compatibility", "Petrol / Diesel / Toyota WS"),
      textField("productTechnology", "Technology", "Synthetic / Semi-synthetic / Mineral"),
      textField("batchNumber", "Batch / lot number", "Batch reference"),
    ],
  },
};

const BEAUTY_PROFILES = {
  skincare: {
    groupKeys: ["productLine", "productFunction"],
    variantKeys: ["volumeSize", "skinHairType", "scent"],
    fields: [
      textField("productLine", "Product line / range", "Vitamin C / Hydra / Repair"),
      textField("productFunction", "Function / concern", "Hydration / Acne / Brightening"),
      textField("volumeSize", "Size / volume", "50 ml / 250 g"),
      textField("skinHairType", "Skin type", "Dry / Oily / Combination / Sensitive"),
      textField("formulation", "Formulation / texture", "Cream / Gel / Oil / Serum"),
      textField("keyIngredients", "Key ingredients", "Niacinamide, Vitamin C, Shea butter"),
      textField("spf", "SPF", "SPF 30 / SPF 50"),
      textField("scent", "Scent / fragrance", "Unscented / Vanilla"),
      textField("batchNumber", "Batch / lot number", "LOT-2409"),
      dateField("expiryDate", "Expiry date"),
    ],
  },
  makeup: {
    groupKeys: ["productLine", "productType"],
    variantKeys: ["shade", "shadeCode", "finish"],
    fields: [
      textField("productLine", "Product line / range", "Fit Me / Studio Fix"),
      textField("productType", "Makeup type", "Foundation / Powder / Lipstick"),
      textField("shade", "Shade / colour", "Warm Caramel"),
      textField("shadeCode", "Shade code", "06 / NC45"),
      textField("finish", "Finish", "Matte / Dewy / Satin / Gloss"),
      textField("coverage", "Coverage", "Light / Medium / Full"),
      textField("skinHairType", "Skin type", "Dry / Oily / All skin types"),
      textField("volumeSize", "Size / volume", "30 ml / 8 g"),
      textField("waterproof", "Waterproof", "Yes / No", { options: ["Yes", "No"] }),
      textField("batchNumber", "Batch / lot number", "LOT-2409"),
      dateField("expiryDate", "Expiry date"),
    ],
  },
  fragrance: {
    groupKeys: ["fragranceName", "concentration"],
    variantKeys: ["volumeSize", "scentFamily", "targetGender"],
    fields: [
      textField("fragranceName", "Fragrance / line", "Product fragrance name"),
      textField("concentration", "Concentration", "EDP / EDT / Parfum / Body mist"),
      textField("volumeSize", "Bottle size", "30 ml / 50 ml / 100 ml"),
      textField("scentFamily", "Scent family", "Woody / Floral / Fresh / Oriental"),
      textField("topNotes", "Top notes", "Citrus, bergamot"),
      textField("baseNotes", "Base notes", "Musk, vanilla"),
      textField("targetGender", "Target", "Men / Women / Unisex"),
      textField("batchNumber", "Batch / lot number", "Batch reference"),
    ],
  },
  haircare: {
    groupKeys: ["productLine", "productFunction"],
    variantKeys: ["volumeSize", "skinHairType", "scent"],
    fields: [
      textField("productLine", "Product line / range", "Repair / Moisture / Growth"),
      textField("productFunction", "Function", "Shampoo / Conditioner / Treatment / Oil"),
      textField("skinHairType", "Hair type", "Natural / Relaxed / Curly / Dry"),
      textField("volumeSize", "Size / volume", "250 ml / 500 ml"),
      textField("formulation", "Formulation", "Cream / Oil / Gel / Sulfate-free"),
      textField("keyIngredients", "Key ingredients", "Argan oil / Shea butter"),
      textField("scent", "Scent", "Coconut / Unscented"),
      textField("batchNumber", "Batch / lot number", "LOT-2409"),
      dateField("expiryDate", "Expiry date"),
    ],
  },
  hairExtension: {
    groupKeys: ["hairType", "texture"],
    variantKeys: ["length", "colour", "density"],
    fields: [
      textField("hairType", "Hair type", "Human hair / Synthetic / Blend"),
      textField("texture", "Texture", "Straight / Body wave / Kinky / Curly"),
      textField("length", "Length", "12 inch / 20 inch / 30 inch"),
      textField("colour", "Colour", "1B / Natural black / Burgundy"),
      textField("density", "Density / weight", "150% / 180% / 100 g"),
      textField("laceType", "Lace / closure type", "13x4 frontal / 5x5 closure"),
      textField("capSize", "Cap size", "Small / Medium / Large"),
      textField("origin", "Hair origin", "Brazilian / Peruvian / Indian"),
    ],
  },
  generic: {
    groupKeys: ["productLine", "productType"],
    variantKeys: ["volumeSize", "shade", "colour"],
    fields: [
      textField("productLine", "Product line / range", "Product range"),
      textField("productType", "Type / style", "Product type"),
      textField("shade", "Shade / colour", "Shade / colour"),
      textField("volumeSize", "Size / volume", "50 ml / 250 g"),
      textField("skinHairType", "Skin / hair type", "Dry skin / natural hair"),
      textField("formulation", "Formulation / material", "Cream / Gel / Powder"),
      textField("batchNumber", "Batch / lot number", "LOT-2409"),
      dateField("expiryDate", "Expiry date"),
    ],
  },
};

const PHONE_CATEGORY_PROFILE = {
  Smartphones: "smartphone",
  "Feature Phones": "featurePhone",
  Tablets: "tablet",
  Laptops: "laptop",
  "Desktop Computers": "desktop",
  Monitors: "monitor",
  "Wall Chargers": "charger",
  "Fast Chargers": "charger",
  "Wireless Chargers": "charger",
  "Laptop Chargers": "charger",
  "Car Chargers": "charger",
  "USB Cables": "cable",
  "Type-C Cables": "cable",
  "Lightning Cables": "cable",
  "Power Banks": "powerBank",
  "Wired Earphones": "audio",
  "Wireless Earbuds": "audio",
  Headphones: "audio",
  "Bluetooth Speakers": "audio",
  "Smart Watches": "smartwatch",
  "Memory Cards": "storage",
  "USB Flash Drives": "storage",
  "External SSDs": "storage",
  "External Hard Drives": "storage",
  "Storage Devices": "storage",
  "Routers and MiFi": "network",
  Modems: "network",
};

const PROVISION_BEVERAGES = new Set([
  "Soft Drinks", "Malt and Energy Drinks", "Bottled Water", "Fruit Juice", "Tea and Coffee",
]);
const PROVISION_HOUSEHOLD = new Set([
  "Toiletries", "Tissue and Paper Products", "Laundry Products", "Cleaning Supplies",
  "Household Essentials", "Personal Care", "Baby Products",
]);

const ELECTRICAL_CABLES = new Set(["Electrical Cables and Wires", "Conduits and Trunking"]);
const ELECTRICAL_LIGHTING = new Set(["LED Bulbs", "Lighting Fixtures"]);
const ELECTRICAL_TV = new Set(["Televisions", "Monitors"]);
const ELECTRICAL_AC = new Set(["Air Conditioners"]);
const ELECTRICAL_POWER = new Set(["Solar Accessories", "Inverters", "Voltage Regulators", "UPS Systems"]);
const ELECTRICAL_APPLIANCES = new Set([
  "Ceiling Fans", "Standing Fans", "Refrigerators", "Freezers", "Microwaves", "Electric Irons",
  "Blenders", "Kettles", "Rice Cookers", "Washing Machines", "Speakers and Sound Systems", "Small Appliances",
]);

const AUTO_TYRES = new Set(["Tyres and Tubes", "Wheel Accessories"]);
const AUTO_BATTERIES = new Set(["Car Batteries"]);
const AUTO_FLUIDS = new Set(["Engine Oil and Lubricants", "Coolants and Fluids"]);

const BEAUTY_SKINCARE = new Set([
  "Body Lotions", "Body Creams", "Body Oils", "Face Creams", "Facial Cleansers", "Serums",
  "Sunscreen", "Soaps and Shower Gels", "Deodorants", "Skincare Sets", "Baby Skin Care", "Personal Care",
]);
const BEAUTY_MAKEUP = new Set([
  "Lip Products", "Foundation and Powder", "Eye Makeup", "Makeup Accessories", "Nail Products",
]);
const BEAUTY_FRAGRANCE = new Set(["Perfumes and Fragrances"]);
const BEAUTY_HAIRCARE = new Set([
  "Hair Creams", "Hair Oils", "Shampoo and Conditioner", "Hair Treatments", "Hair Relaxers", "Barber Products",
]);
const BEAUTY_EXTENSIONS = new Set(["Wigs and Extensions", "Braiding Hair"]);

export const RETAIL_BRAND_SUGGESTIONS = Object.freeze({
  provision_mini_mart: [
    "Nestlé", "Unilever", "PZ Cussons", "Promasidor", "Fan Milk", "Coca-Cola", "Pepsi", "Kasapreko",
    "Twellium", "Olam", "GBfoods", "Wilmar", "Kellogg's", "Nasco", "Generic / Unbranded",
  ],
  phone_electronics_accessories: [
    "Apple", "Samsung", "Google", "Huawei", "Xiaomi", "Redmi", "Tecno", "Infinix", "itel", "Nokia",
    "OnePlus", "Oppo", "Vivo", "Honor", "Realme", "Motorola", "Sony", "HP", "Dell", "Lenovo", "Asus",
    "Acer", "Microsoft", "MSI", "LG", "Anker", "Oraimo", "JBL", "Baseus", "UGREEN", "SanDisk", "Kingston",
    "Seagate", "Western Digital", "TP-Link", "D-Link", "Generic / Unbranded",
  ],
  electrical_electronics: [
    "Samsung", "LG", "Hisense", "TCL", "Nasco", "Midea", "Bruhm", "Binatone", "Philips", "Panasonic",
    "Schneider Electric", "ABB", "Legrand", "Siemens", "Chint", "Hager", "Bosch", "Ingco", "Oraimo",
    "Generic / Unbranded",
  ],
  auto_spare_parts: [
    "Toyota", "Honda", "Nissan", "Hyundai", "Kia", "Mercedes-Benz", "BMW", "Volkswagen", "Ford", "Chevrolet",
    "Mitsubishi", "Suzuki", "Mazda", "Denso", "Bosch", "NGK", "Brembo", "KYB", "Sachs", "Gates", "Mann-Filter",
    "Mobil", "Shell", "Castrol", "TotalEnergies", "Generic / Aftermarket",
  ],
  cosmetics_beauty: [
    "Nivea", "Dove", "Vaseline", "CeraVe", "Neutrogena", "The Ordinary", "L'Oréal", "Maybelline", "MAC",
    "Revlon", "Fenty Beauty", "Black Opal", "SheaMoisture", "Cantu", "ORS", "Dark & Lovely", "Mielle",
    "Generic / Unbranded",
  ],
});

function profileFor(businessType, category) {
  if (businessType === "phone_electronics_accessories") {
    return PHONE_PROFILES[PHONE_CATEGORY_PROFILE[category] || "accessory"];
  }

  if (businessType === "provision_mini_mart") {
    if (PROVISION_BEVERAGES.has(category)) return PROVISION_PROFILES.beverage;
    if (PROVISION_HOUSEHOLD.has(category)) return PROVISION_PROFILES.household;
    return PROVISION_PROFILES.grocery;
  }

  if (businessType === "electrical_electronics") {
    if (ELECTRICAL_CABLES.has(category)) return ELECTRICAL_PROFILES.cable;
    if (ELECTRICAL_LIGHTING.has(category)) return ELECTRICAL_PROFILES.lighting;
    if (ELECTRICAL_TV.has(category)) return ELECTRICAL_PROFILES.television;
    if (ELECTRICAL_AC.has(category)) return ELECTRICAL_PROFILES.airConditioner;
    if (ELECTRICAL_POWER.has(category)) return ELECTRICAL_PROFILES.powerSystem;
    if (ELECTRICAL_APPLIANCES.has(category)) return ELECTRICAL_PROFILES.appliance;
    return ELECTRICAL_PROFILES.generic;
  }

  if (businessType === "auto_spare_parts") {
    if (AUTO_TYRES.has(category)) return AUTO_PROFILES.tyre;
    if (AUTO_BATTERIES.has(category)) return AUTO_PROFILES.battery;
    if (AUTO_FLUIDS.has(category)) return AUTO_PROFILES.fluid;
    return AUTO_PROFILES.part;
  }

  if (businessType === "cosmetics_beauty") {
    if (BEAUTY_SKINCARE.has(category)) return BEAUTY_PROFILES.skincare;
    if (BEAUTY_MAKEUP.has(category)) return BEAUTY_PROFILES.makeup;
    if (BEAUTY_FRAGRANCE.has(category)) return BEAUTY_PROFILES.fragrance;
    if (BEAUTY_HAIRCARE.has(category)) return BEAUTY_PROFILES.haircare;
    if (BEAUTY_EXTENSIONS.has(category)) return BEAUTY_PROFILES.hairExtension;
    return BEAUTY_PROFILES.generic;
  }

  return { fields: [], groupKeys: [], variantKeys: [] };
}

export function retailSpecificationFields(businessType, category) {
  return profileFor(businessType, category).fields || [];
}

export function retailBrandSuggestions(businessType) {
  return RETAIL_BRAND_SUGGESTIONS[businessType] || [];
}

function valueFor(product, key) {
  const value = product?.retailDetails?.[key];
  return value === null || value === undefined ? "" : String(value).trim();
}

export function retailProductGroupLabel(product, businessType) {
  const profile = profileFor(businessType, product?.category || "");
  const brand = String(product?.brand || "").trim() || "Unbranded";
  const identity = (profile.groupKeys || [])
    .map((key) => valueFor(product, key))
    .filter(Boolean)
    .slice(0, 2);

  return [brand, ...identity].join(" · ");
}

export function retailProductVariantSummary(product, businessType, limit = 4) {
  const profile = profileFor(businessType, product?.category || "");
  const fieldMap = new Map((profile.fields || []).map((field) => [field.key, field.label]));
  const parts = [];

  (profile.variantKeys || []).forEach((key) => {
    const value = valueFor(product, key);
    if (!value) return;
    const label = fieldMap.get(key) || key;
    parts.push(`${label}: ${value}`);
  });

  return parts.slice(0, limit).join(" · ");
}

export function retailDetailEntries(product, businessType) {
  const profile = profileFor(businessType, product?.category || "");
  const entries = (profile.fields || [])
    .map((field) => {
      const value = valueFor(product, field.key);
      return value ? { key: field.key, label: field.label, value } : null;
    })
    .filter(Boolean);

  const additional = Array.isArray(product?.retailDetails?.additionalSpecifications)
    ? product.retailDetails.additionalSpecifications
        .map((item, index) => {
          const label = String(item?.label || "").trim();
          const value = String(item?.value || "").trim();
          return label && value
            ? { key: `additional-${index}-${label}`, label, value }
            : null;
        })
        .filter(Boolean)
    : [];

  return [...entries, ...additional];
}

function flattenValue(value, output) {
  if (value === null || value === undefined || value === "") return;
  if (Array.isArray(value)) {
    value.forEach((item) => flattenValue(item, output));
    return;
  }
  if (typeof value === "object") {
    Object.values(value).forEach((item) => flattenValue(item, output));
    return;
  }
  output.push(String(value));
}

export function retailSearchValues(product) {
  const output = [];
  flattenValue(product?.retailDetails || {}, output);
  return output;
}
