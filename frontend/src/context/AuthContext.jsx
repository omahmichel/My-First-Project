import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { apiRequest } from "../services/api";
import { loadStoredValue, saveStoredValue } from "../services/storage";

const AuthContext = createContext(null);

// Maps the Django user shape to the existing frontend user shape.
function normalizeUser(account) {
  if (!account) return null;

  return {
    id: account.id,
    name: account.full_name ?? account.name ?? "StockFlow User",
    email: account.email ?? "",
    phone: account.phone ?? "",
    role: account.role ?? "account",
    isActive: account.is_active ?? true,
    dateJoined: account.date_joined ?? null,
  };
}

// Keeps only non-secret details needed by email verification and onboarding.
function sanitizePendingRegistration(registration) {
  if (!registration) return null;

  return {
    name: registration.name?.trim() ?? "",
    businessName: registration.businessName?.trim() ?? "",
    email: registration.email?.trim().toLowerCase() ?? "",
    phone: registration.phone?.trim() ?? "",
  };
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() =>
    loadStoredValue("auth_user", null),
  );
  const [pendingRegistration, setPendingRegistration] = useState(() => {
    const storedRegistration = loadStoredValue(
      "pending_registration",
      null,
    );
    const safeRegistration = sanitizePendingRegistration(
      storedRegistration,
    );

    // Removes any password left by the older immediate-registration flow.
    if (storedRegistration) {
      saveStoredValue("pending_registration", safeRegistration);
    }

    return safeRegistration;
  });
  const [isInitializing, setIsInitializing] = useState(true);

  // Clears all authentication state without depending on the API response.
  const clearAuthentication = useCallback(() => {
    setUser(null);
    saveStoredValue("auth_user", null);
    window.localStorage.removeItem("stockflow_access_token");
    window.localStorage.removeItem("stockflow_refresh_token");
  }, []);

  // Verifies a saved access token before protected routes are displayed.
  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      const accessToken = window.localStorage.getItem(
        "stockflow_access_token",
      );

      if (!accessToken) {
        if (!cancelled) {
          clearAuthentication();
          setIsInitializing(false);
        }
        return;
      }

      try {
        const account = await apiRequest("/auth/me/");

        if (!cancelled) {
          const nextUser = normalizeUser(account);
          setUser(nextUser);
          saveStoredValue("auth_user", nextUser);
        }
      } catch {
        if (!cancelled) clearAuthentication();
      } finally {
        if (!cancelled) setIsInitializing(false);
      }
    }

    restoreSession();

    return () => {
      cancelled = true;
    };
  }, [clearAuthentication]);

  // Ends the visible session when automatic token refresh is no longer possible.
  useEffect(() => {
    function handleAuthenticationExpiry() {
      clearAuthentication();
      setPendingRegistration(null);
      saveStoredValue("pending_registration", null);
    }

    window.addEventListener(
      "stockflow:auth-expired",
      handleAuthenticationExpiry,
    );

    return () => {
      window.removeEventListener(
        "stockflow:auth-expired",
        handleAuthenticationExpiry,
      );
    };
  }, [clearAuthentication]);

  // Authenticates with Django and stores both JWT tokens safely in this browser.
  async function login({ email, password }) {
    if (!email?.trim() || !password?.trim()) {
      throw new Error("Enter your email and password.");
    }

    const response = await apiRequest("/auth/login/", {
      method: "POST",
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
        password,
      }),
    });

    window.localStorage.setItem("stockflow_access_token", response.access);
    window.localStorage.setItem("stockflow_refresh_token", response.refresh);

    const nextUser = normalizeUser(response.user);
    setUser(nextUser);
    saveStoredValue("auth_user", nextUser);
    return nextUser;
  }

  // Starts registration by sending an OTP without creating the account yet.
  async function register(payload) {
    if (
      !payload.name?.trim() ||
      !payload.email?.trim() ||
      !payload.password?.trim()
    ) {
      throw new Error("Complete all required registration fields.");
    }

    if (payload.password.length < 8) {
      throw new Error("Password must contain at least 8 characters.");
    }

    const registration = {
      ...payload,
      name: payload.name.trim(),
      businessName: payload.businessName?.trim() ?? "",
      email: payload.email.trim().toLowerCase(),
    };

    await apiRequest("/auth/register/", {
      method: "POST",
      body: JSON.stringify({
        email: registration.email,
        full_name: registration.name,
        phone: registration.phone?.trim() ?? "",
        password: registration.password,
        password_confirm: registration.password,
      }),
    });

    const safeRegistration = sanitizePendingRegistration(registration);
    setPendingRegistration(safeRegistration);
    saveStoredValue("pending_registration", safeRegistration);
    return safeRegistration;
  }

  // Creates the account and stores JWT credentials after OTP verification.
  async function verifyRegistrationOtp({ email, otp }) {
    const response = await apiRequest("/auth/register/verify/", {
      method: "POST",
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
        otp: otp.trim(),
      }),
    });

    window.localStorage.setItem(
      "stockflow_access_token",
      response.access,
    );
    window.localStorage.setItem(
      "stockflow_refresh_token",
      response.refresh,
    );

    const nextUser = normalizeUser(response.user);
    setUser(nextUser);
    saveStoredValue("auth_user", nextUser);
    return nextUser;
  }

  // Requests a replacement code for the current pending registration.
  async function resendRegistrationOtp(email) {
    return apiRequest("/auth/register/resend/", {
      method: "POST",
      body: JSON.stringify({
        email: email.trim().toLowerCase(),
      }),
    });
  }

  // Finalizes the local onboarding state after Django creates the business.
  function completeOnboarding() {
    setPendingRegistration(null);
    saveStoredValue("pending_registration", null);
  }

  // Blacklists the refresh token and always removes local credentials.
  async function logout() {
    const refreshToken = window.localStorage.getItem(
      "stockflow_refresh_token",
    );

    try {
      if (refreshToken) {
        await apiRequest("/auth/logout/", {
          method: "POST",
          body: JSON.stringify({ refresh: refreshToken }),
          // Logout should never rotate an already-expired access token.
          skipAuthRefresh: true,
        });
      }
    } catch {
      // Local logout still succeeds when the token is already invalid.
    } finally {
      clearAuthentication();
      setPendingRegistration(null);
      saveStoredValue("pending_registration", null);
    }
  }

  const value = useMemo(
    () => ({
      user,
      pendingRegistration,
      isAuthenticated: Boolean(user),
      isInitializing,
      login,
      register,
      verifyRegistrationOtp,
      resendRegistrationOtp,
      completeOnboarding,
      logout,
    }),
    [isInitializing, pendingRegistration, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }

  return context;
}
