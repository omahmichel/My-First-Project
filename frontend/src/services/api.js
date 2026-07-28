const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api";

// Extracts a useful DRF validation message from detail or field errors.
function resolveApiErrorMessage(errorData) {
  if (typeof errorData === "string") return errorData;
  if (!errorData || typeof errorData !== "object") {
    return "The request could not be completed.";
  }

  if (typeof errorData.detail === "string") return errorData.detail;

  for (const value of Object.values(errorData)) {
    if (Array.isArray(value) && value.length > 0) {
      return String(value[0]);
    }

    if (typeof value === "string") return value;
  }

  return "The request could not be completed.";
}

// Sends an authenticated JSON request to the Django REST API.
export async function apiRequest(path, options = {}) {
  const accessToken = window.localStorage.getItem("stockflow_access_token");
  const headers = new Headers(options.headers ?? {});

  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const error = new Error(resolveApiErrorMessage(errorData));
    error.status = response.status;
    error.data = errorData;
    throw error;
  }

  if (response.status === 204) return null;
  return response.json();
}
