// Stores only lightweight browser state; business records remain in Django.
// The legacy prefix value is retained so existing browser sessions keep working.
const STORAGE_PREFIX = "stockflow_demo_";

export function loadStoredValue(key, fallback) {
  try {
    const value = window.localStorage.getItem(`${STORAGE_PREFIX}${key}`);
    return value ? JSON.parse(value) : fallback;
  } catch (error) {
    console.error(`Unable to read ${key} from local storage`, error);
    return fallback;
  }
}

export function saveStoredValue(key, value) {
  try {
    window.localStorage.setItem(`${STORAGE_PREFIX}${key}`, JSON.stringify(value));
  } catch (error) {
    console.error(`Unable to save ${key} to local storage`, error);
  }
}

export function clearStoredValues() {
  Object.keys(window.localStorage)
    .filter((key) => key.startsWith(STORAGE_PREFIX))
    .forEach((key) => window.localStorage.removeItem(key));
}
