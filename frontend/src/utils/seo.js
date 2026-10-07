// Update this origin, public/robots.txt and public/sitemap.xml together when moving domains.
export const SITE_ORIGIN = "https://stockflow-web-btlh.onrender.com";
export const HOME_TITLE = "StockFlow Ghana | Inventory & Sales Software for Shops";
export const HOME_DESCRIPTION = "Manage shop inventory, sales, invoices, customer debt and staff with StockFlow Ghana. Built for boutiques, mini marts, building materials and other retail shops.";
export function metadataForPath(pathname) {
  const path = pathname.replace(/\/+$/, "") || "/";
  const pages = {
    "/": [HOME_TITLE, HOME_DESCRIPTION],
    "/terms": ["Terms of Service | StockFlow Ghana", "Read the terms for using StockFlow Ghana, including accounts, business records, subscriptions and online shops."],
    "/privacy": ["Privacy Policy | StockFlow Ghana", "Learn how StockFlow Ghana processes account, business and customer information, and how to contact us about privacy."],
  };
  const shop = /^\/shops\/[^/]+$/.test(path);
  const page = pages[path];
  return {
    title: page?.[0] || (shop ? "Online Shop | StockFlow Ghana" : "Account Access | StockFlow Ghana"),
    description: page?.[1] || (shop ? "Browse products from an independent business on StockFlow Ghana." : "Sign in to access your authorised StockFlow account."),
    indexable: Boolean(page || shop),
    canonical: page || shop ? SITE_ORIGIN + path : null,
    home: path === "/",
  };
}
function meta(attribute, key, value) {
  let node = document.head.querySelector(`meta[${attribute}="${key}"]`);
  if (!node) { node = document.createElement("meta"); node.setAttribute(attribute, key); document.head.appendChild(node); }
  node.setAttribute("content", value);
}
export function applyPageMetadata(pathname) {
  const data = metadataForPath(pathname);
  document.title = data.title;
  meta("name", "description", data.description);
  meta("name", "robots", data.indexable ? "index, follow" : "noindex, follow");
  for (const [prefix, attribute] of [["og", "property"], ["twitter", "name"]]) {
    meta(attribute, `${prefix}:title`, data.title);
    meta(attribute, `${prefix}:description`, data.description);
    meta(attribute, `${prefix}:image`, SITE_ORIGIN + "/images/landing/hero-tablet.jpg");
  }
  let canonical = document.head.querySelector('link[rel="canonical"]');
  if (data.canonical) {
    if (!canonical) { canonical = document.createElement("link"); canonical.rel = "canonical"; document.head.appendChild(canonical); }
    canonical.href = data.canonical;
    meta("property", "og:url", data.canonical);
  } else {
    canonical?.remove();
    document.head.querySelector('meta[property="og:url"]')?.remove();
  }
  let schema = document.getElementById("stockflow-public-schema");
  if (data.home) {
    if (!schema) { schema = document.createElement("script"); schema.id = "stockflow-public-schema"; schema.type = "application/ld+json"; document.head.appendChild(schema); }
    schema.textContent = JSON.stringify({
      "@context": "https://schema.org",
      "@graph": [
        { "@type": "Organization", "@id": SITE_ORIGIN + "/#organization", name: "StockFlow Ghana", url: SITE_ORIGIN + "/", logo: SITE_ORIGIN + "/logo.svg" },
        { "@type": "WebSite", "@id": SITE_ORIGIN + "/#website", name: "StockFlow Ghana", alternateName: "StockFlow", url: SITE_ORIGIN + "/", publisher: { "@id": SITE_ORIGIN + "/#organization" } },
      ],
    });
  } else schema?.remove();
}
