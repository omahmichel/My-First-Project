const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api";

// This wrapper is prepared for the Django REST API integration phase.
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
    throw new Error(errorData.detail ?? "The request could not be completed.");
  }

  if (response.status === 204) return null;
  return response.json();
}
