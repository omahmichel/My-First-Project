// Shared Shoprite-style table contract. Industry pages supply their own columns,
// data-label cell headings, filters and actions; new inventory routes reuse this.
export default function InventoryTable({ className = "", children, ...props }) {
  return <table {...props} className={`data-table stockflow-premium-table stockflow-inventory-table ${className}`}>{children}</table>;
}
