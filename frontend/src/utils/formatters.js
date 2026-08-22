// Shared formatting functions keep money and dates consistent across the frontend.
export function formatCurrency(value = 0) {
  const amount = Number(value) || 0;
  const formattedAmount = new Intl.NumberFormat("en-GH", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amount);

  return `₵${formattedAmount}`;
}

export function formatNumber(value = 0, maximumFractionDigits = 2) {
  return new Intl.NumberFormat("en-GH", {
    maximumFractionDigits,
  }).format(Number(value) || 0);
}

export function formatDate(value) {
  if (!value) return "—";

  return new Intl.DateTimeFormat("en-GH", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

export function formatDateTime(value) {
  if (!value) return "—";

  return new Intl.DateTimeFormat("en-GH", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function createId(prefix = "item") {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}
