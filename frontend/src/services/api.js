const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api";

let activeRefreshRequest = null;

// Returns true only when a JWT access token is already expired (or about to expire).
// Malformed/opaque tokens fall back to the existing server-side 401 refresh path.
function isAccessTokenExpired(accessToken, clockSkewSeconds = 15) {
  if (!accessToken || typeof accessToken !== "string") return false;

  try {
    const tokenParts = accessToken.split(".");
    if (tokenParts.length !== 3) return false;

    const normalizedPayload = tokenParts[1]
      .replace(/-/g, "+")
      .replace(/_/g, "/");
    const paddedPayload = normalizedPayload.padEnd(
      normalizedPayload.length + ((4 - (normalizedPayload.length % 4)) % 4),
      "=",
    );
    const payload = JSON.parse(window.atob(paddedPayload));

    if (typeof payload.exp !== "number") return false;

    return payload.exp * 1000 <= Date.now() + clockSkewSeconds * 1000;
  } catch {
    return false;
  }
}

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

// Removes unusable credentials and tells AuthContext to end the session.
function clearExpiredSession() {
  window.localStorage.removeItem("stockflow_access_token");
  window.localStorage.removeItem("stockflow_refresh_token");
  window.dispatchEvent(new Event("stockflow:auth-expired"));
}

// Uses one shared refresh request when several API calls expire together.
async function refreshAccessToken() {
  const refreshToken = window.localStorage.getItem(
    "stockflow_refresh_token",
  );

  if (!refreshToken) {
    clearExpiredSession();
    throw new Error("Your session has expired. Please sign in again.");
  }

  if (!activeRefreshRequest) {
    activeRefreshRequest = fetch(`${API_BASE_URL}/auth/refresh/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ refresh: refreshToken }),
    })
      .then(async (response) => {
        const responseData = await response.json().catch(() => ({}));

        if (!response.ok || !responseData.access) {
          const error = new Error(
            resolveApiErrorMessage(responseData),
          );
          error.status = response.status;
          error.data = responseData;
          throw error;
        }

        window.localStorage.setItem(
          "stockflow_access_token",
          responseData.access,
        );

        // SimpleJWT returns a rotated refresh token when rotation is enabled.
        if (responseData.refresh) {
          window.localStorage.setItem(
            "stockflow_refresh_token",
            responseData.refresh,
          );
        }

        return responseData.access;
      })
      .catch(() => {
        clearExpiredSession();
        throw new Error(
          "Your session has expired. Please sign in again.",
        );
      })
      .finally(() => {
        activeRefreshRequest = null;
      });
  }

  return activeRefreshRequest;
}

// Creates request headers with the latest access token.
function buildRequestHeaders(options, accessToken) {
  const headers = new Headers(options.headers ?? {});

  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  } else {
    headers.delete("Authorization");
  }

  return headers;
}

// Sends an authenticated request and retries once after token refresh.
export async function apiRequest(path, options = {}) {
  const {
    skipAuthRefresh = false,
    ...fetchOptions
  } = options;

  const sendRequest = (accessToken) =>
    fetch(`${API_BASE_URL}${path}`, {
      ...fetchOptions,
      headers: buildRequestHeaders(fetchOptions, accessToken),
    });

  let accessToken = window.localStorage.getItem(
    "stockflow_access_token",
  );

  const refreshAllowedForPath =
    !skipAuthRefresh &&
    path !== "/auth/login/" &&
    path !== "/auth/register/" &&
    path !== "/auth/refresh/";

  // Avoid the routine first 401 in DevTools when the stored JWT has already
  // expired. The existing server-401 retry below remains the authority/fallback.
  if (
    refreshAllowedForPath &&
    isAccessTokenExpired(accessToken)
  ) {
    accessToken = await refreshAccessToken();
  }

  let response = await sendRequest(accessToken);

  if (
    refreshAllowedForPath &&
    response.status === 401
  ) {
    accessToken = await refreshAccessToken();
    response = await sendRequest(accessToken);
  }

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
