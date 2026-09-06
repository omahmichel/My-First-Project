export function toNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}


export function formatNumber(value, maximumFractionDigits = 2) {
  return new Intl.NumberFormat("en-GH", {
    maximumFractionDigits,
  }).format(toNumber(value));
}


export function formatCurrency(value) {
  return `₵${new Intl.NumberFormat("en-GH", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(toNumber(value))}`;
}


export function formatPercent(value) {
  if (value === null || value === undefined || value === "") {
    return "Not available";
  }

  return `${formatNumber(value, 2)}%`;
}


export function formatDate(value) {
  if (!value) return "Not available";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return new Intl.DateTimeFormat("en-GH", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}


export function formatDateTime(value) {
  if (!value) return "Not available";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en-GH", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}


export function titleCase(value) {
  return String(value ?? "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
