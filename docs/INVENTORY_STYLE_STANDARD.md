# Shared inventory presentation

The Shoprite tile page is the visual reference. All Products, Tiles, Boutique and the configured RetailInventoryPage use InventoryTable from components/inventory/InventoryTable.

Existing and future retail business types should be registered through retailInventoryConfig and rendered with RetailInventoryPage; they inherit the same layout without route-specific table CSS. Keep product-specific labels, filters, units and actions in the configuration.

For a genuinely new inventory page, use stockflow-inventory-page, stockflow-inventory-panel, stockflow-inventory-toolbar and stockflow-inventory-table-wrapper around InventoryTable. Use stockflow-shared-records for the responsive table and data-label on every body cell. Shared summary/search/filter/action classes are defined in stockflow-inventory-system.css. Avoid fixed page-width tables or new route-specific palettes for record controls.

Validate desktop fit and phone record cards, long names, empty records, filters, pagination and edit/stock/status actions before release.
