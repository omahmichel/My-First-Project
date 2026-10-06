import { apiRequest } from "./api";

function supported() {
  return Boolean(window.PublicKeyCredential && navigator.credentials);
}

function decodeBase64Url(value) {
  const padding = "=".repeat((4 - (value.length % 4)) % 4);
  const base64 = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
  const binary = window.atob(base64);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0)).buffer;
}

function encodeBase64Url(value) {
  const bytes = new Uint8Array(value);
  let binary = "";
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return window.btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function creationOptions(options) {
  return {
    ...options,
    challenge: decodeBase64Url(options.challenge),
    user: { ...options.user, id: decodeBase64Url(options.user.id) },
    excludeCredentials: (options.excludeCredentials ?? []).map((item) => ({
      ...item,
      id: decodeBase64Url(item.id),
    })),
  };
}

function requestOptions(options) {
  return {
    ...options,
    challenge: decodeBase64Url(options.challenge),
    allowCredentials: (options.allowCredentials ?? []).map((item) => ({
      ...item,
      id: decodeBase64Url(item.id),
    })),
  };
}

function serializeRegistration(credential) {
  return {
    id: credential.id,
    rawId: encodeBase64Url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment ?? null,
    clientExtensionResults: credential.getClientExtensionResults?.() ?? {},
    response: {
      clientDataJSON: encodeBase64Url(credential.response.clientDataJSON),
      attestationObject: encodeBase64Url(credential.response.attestationObject),
      transports: credential.response.getTransports?.() ?? [],
    },
  };
}

function serializeAuthentication(credential) {
  return {
    id: credential.id,
    rawId: encodeBase64Url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment ?? null,
    clientExtensionResults: credential.getClientExtensionResults?.() ?? {},
    response: {
      clientDataJSON: encodeBase64Url(credential.response.clientDataJSON),
      authenticatorData: encodeBase64Url(credential.response.authenticatorData),
      signature: encodeBase64Url(credential.response.signature),
      userHandle: credential.response.userHandle
        ? encodeBase64Url(credential.response.userHandle)
        : null,
    },
  };
}

function friendlyError(error) {
  if (error?.name === "NotAllowedError") {
    return new Error("Biometric/passkey sign-in was cancelled or timed out.");
  }
  if (error?.name === "InvalidStateError") {
    return new Error("This passkey is already registered on this account.");
  }
  if (error?.name === "SecurityError") {
    return new Error("Biometric sign-in requires StockFlow to run on its trusted HTTPS domain.");
  }
  return error instanceof Error ? error : new Error("Biometric sign-in could not be completed.");
}

export function passkeysSupported() {
  return supported();
}

export async function registerStockFlowPasskey(label = "This device") {
  if (!supported()) throw new Error("This browser or device does not support passkeys.");
  try {
    const start = await apiRequest("/auth/passkeys/register/options/", {
      method: "POST",
      body: JSON.stringify({}),
    });
    const credential = await navigator.credentials.create({
      publicKey: creationOptions(start.options),
    });
    if (!credential) throw new Error("No biometric/passkey credential was created.");
    return apiRequest("/auth/passkeys/register/verify/", {
      method: "POST",
      body: JSON.stringify({
        challengeId: start.challengeId,
        credential: serializeRegistration(credential),
        label,
      }),
    });
  } catch (error) {
    throw friendlyError(error);
  }
}

export async function authenticateWithStockFlowPasskey(email) {
  if (!supported()) throw new Error("This browser or device does not support passkeys.");
  try {
    const start = await apiRequest("/auth/passkeys/login/options/", {
      method: "POST",
      body: JSON.stringify({ email }),
      skipAuthRefresh: true,
    });
    const credential = await navigator.credentials.get({
      publicKey: requestOptions(start.options),
    });
    if (!credential) throw new Error("No biometric/passkey credential was selected.");
    return apiRequest("/auth/passkeys/login/verify/", {
      method: "POST",
      body: JSON.stringify({
        challengeId: start.challengeId,
        credential: serializeAuthentication(credential),
      }),
      skipAuthRefresh: true,
    });
  } catch (error) {
    throw friendlyError(error);
  }
}
