// This service isolates localStorage so it can be replaced by Django API calls later.
const PREFIX = "stockflow_demo_";

export function loadStoredValue(key, fallback) {
  try {
    const value = window.localStorage.getItem(`${PREFIX}${key}`);
    return value ? JSON.parse(value) : fallback;
  } catch (error) {
    console.error(`Unable to read ${key} from local storage`, error);
    return fallback;
  }
}

export function saveStoredValue(key, value) {
  try {
    window.localStorage.setItem(`${PREFIX}${key}`, JSON.stringify(value));
  } catch (error) {
    console.error(`Unable to save ${key} to local storage`, error);
  }
}

export function clearDemoStorage() {
  Object.keys(window.localStorage)
    .filter((key) => key.startsWith(PREFIX))
    .forEach((key) => window.localStorage.removeItem(key));
}
