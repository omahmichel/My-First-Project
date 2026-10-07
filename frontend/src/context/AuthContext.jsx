import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { apiRequest, invalidateAuthRequests, loginOtpRequest } from "../services/api";
import { authenticateWithStockFlowPasskey, registerStockFlowPasskey } from "../services/passkeys";
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
    isPlatformAdmin: account.is_platform_admin === true,
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

const PENDING_LOGIN_KEY = "stockflow_pending_login";

function sanitizePendingLogin(pendingLogin) {
  if (!pendingLogin?.challengeId || !pendingLogin?.email) return null;

  const expiresAt = Number(pendingLogin.expiresAt) || 0;
  if (expiresAt && expiresAt <= Date.now()) return null;

  return {
    challengeId: String(pendingLogin.challengeId),
    email: String(pendingLogin.email).trim().toLowerCase(),
    expiresAt,
    resendAvailableAt: Number(pendingLogin.resendAvailableAt) || 0,
    emailDeliveryRequired: Boolean(pendingLogin.emailDeliveryRequired),
    loginMode: pendingLogin.loginMode === "admin" ? "admin" : "business",
  };
}

function loadPendingLogin() {
  try {
    const rawValue = window.sessionStorage.getItem(PENDING_LOGIN_KEY);
    return sanitizePendingLogin(rawValue ? JSON.parse(rawValue) : null);
  } catch {
    return null;
  }
}

function savePendingLogin(pendingLogin) {
  const safeValue = sanitizePendingLogin(pendingLogin);

  if (!safeValue) {
    window.sessionStorage.removeItem(PENDING_LOGIN_KEY);
    return null;
  }

  window.sessionStorage.setItem(
    PENDING_LOGIN_KEY,
    JSON.stringify(safeValue),
  );
  return safeValue;
}

export function AuthProvider({ children }) {
  const authVersion = useRef(0);
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
  const [pendingLogin, setPendingLogin] = useState(() => loadPendingLogin());
  const [isInitializing, setIsInitializing] = useState(true);

  // Clears all authentication state without depending on the API response.
  const clearAuthentication = useCallback(() => {
    authVersion.current += 1;
    invalidateAuthRequests();
    setUser(null);
    saveStoredValue("auth_user", null);
    window.localStorage.removeItem("stockflow_access_token");
    window.localStorage.removeItem("stockflow_refresh_token");
  }, []);

  // Verifies a saved access token before protected routes are displayed.
  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      if (loadPendingLogin()) { clearAuthentication(); setIsInitializing(false); return; }
      const version = authVersion.current;
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

        if (!cancelled && version === authVersion.current) {
          const nextUser = normalizeUser(account);
          setUser(nextUser);
          saveStoredValue("auth_user", nextUser);
        }
      } catch {
        if (!cancelled && version === authVersion.current) clearAuthentication();
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

  // Validates the password and stores only the short-lived 2FA challenge.
  async function login({ email, password, loginMode = "business" }) {
    if (!email?.trim() || !password?.trim()) {
      throw new Error("Enter your email and password.");
    }

    clearAuthentication();
    setPendingLogin(null);
    savePendingLogin(null);
    const version = authVersion.current;
    const normalizedEmail = email.trim().toLowerCase();
    const safeLoginMode = loginMode === "admin" ? "admin" : "business";
    const response = await loginOtpRequest("/auth/login/", {
      email: normalizedEmail,
      password,
      login_mode: safeLoginMode,
    });
    if (version !== authVersion.current) throw new Error("Sign-in changed. Please try again.");

    const now = Date.now();
    const nextPendingLogin = savePendingLogin({
      challengeId: response.challengeId,
      email: response.email ?? normalizedEmail,
      expiresAt: now + Number(response.expiresIn ?? 600) * 1000,
      resendAvailableAt:
        now + Math.max(60, Number(response.resendCooldown ?? 60)) * 1000,
      emailDeliveryRequired: Boolean(response.emailDeliveryRequired),
      loginMode: safeLoginMode,
    });

    if (!nextPendingLogin) {
      throw new Error("StockFlow could not start secure sign-in.");
    }

    setPendingLogin(nextPendingLogin);
    return nextPendingLogin;
  }

  // Completes 2FA, then stores JWT credentials for the authenticated session.
  async function verifyLoginOtp({ challengeId, otp }) {
    if (loadPendingLogin()?.challengeId !== challengeId) throw new Error("Please restart sign-in.");
    const version = authVersion.current;
    const response = await loginOtpRequest("/auth/login/verify/", { challengeId, otp: otp.trim() });
    if (version !== authVersion.current || loadPendingLogin()?.challengeId !== challengeId) throw new Error("Sign-in changed. Please try again.");

    window.localStorage.setItem("stockflow_access_token", response.access);
    window.localStorage.setItem("stockflow_refresh_token", response.refresh);

    const nextUser = normalizeUser(response.user);
    setUser(nextUser);
    saveStoredValue("auth_user", nextUser);
    setPendingLogin(null);
    savePendingLogin(null);
    return nextUser;
  }

  const sendLoginCode = useCallback(async (challengeId, replacement) => {
    const current = loadPendingLogin();
    if (current?.challengeId !== challengeId) throw new Error("Please restart sign-in.");
    const version = authVersion.current;
    if (replacement) {
      const waiting = savePendingLogin({ ...current, resendAvailableAt: Date.now() + 60000 });
      setPendingLogin(waiting);
    }
    const response = await loginOtpRequest(replacement ? "/auth/login/resend/" : "/auth/login/deliver/", { challengeId });
    if (version !== authVersion.current || loadPendingLogin()?.challengeId !== challengeId) throw new Error("Sign-in changed. Please try again.");
    const now = Date.now();
    const next = savePendingLogin({
      ...current, email: response.email ?? current.email,
      expiresAt: now + Number(response.expiresIn ?? 600) * 1000,
      resendAvailableAt: now + Number(response.resendCooldown ?? 60) * 1000,
      emailDeliveryRequired: false,
    });
    setPendingLogin(next);
    return next;
  }, []);
  const deliverLoginOtp = useCallback((id) => sendLoginCode(id, false), [sendLoginCode]);
  const resendLoginOtp = useCallback((id) => sendLoginCode(id, true), [sendLoginCode]);

  // Authenticates with a previously registered WebAuthn credential.
  async function loginWithPasskey(email) {
    const normalizedEmail = email?.trim().toLowerCase();
    if (!normalizedEmail) throw new Error("Enter your email address first.");
    clearAuthentication();
    setPendingLogin(null);
    savePendingLogin(null);
    const response = await authenticateWithStockFlowPasskey(normalizedEmail);
    window.localStorage.setItem("stockflow_access_token", response.access);
    window.localStorage.setItem("stockflow_refresh_token", response.refresh);
    const nextUser = normalizeUser(response.user);
    setUser(nextUser);
    saveStoredValue("auth_user", nextUser);
    return nextUser;
  }

  async function registerPasskey(label) {
    return registerStockFlowPasskey(label);
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
      setPendingLogin(null);
      savePendingLogin(null);
    }
  }

  const value = useMemo(
    () => ({
      user: pendingLogin ? null : user,
      pendingRegistration,
      pendingLogin,
      isAuthenticated: Boolean(user) && !pendingLogin,
      isInitializing,
      login,
      loginWithPasskey,
      registerPasskey,
      verifyLoginOtp,
      deliverLoginOtp,
      resendLoginOtp,
      register,
      verifyRegistrationOtp,
      resendRegistrationOtp,
      completeOnboarding,
      logout,
    }),
    [isInitializing, pendingLogin, pendingRegistration, user],
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
