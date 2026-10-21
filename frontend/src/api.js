import axios from "axios";

// One place to change the backend address.
export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

const TOKEN_KEY = "tp_token";
const USER_KEY = "tp_user";

export const api = axios.create({
  baseURL: API_BASE,
  // Generation walks Google Places, Gemini and OR-Tools, so be generous.
  timeout: 180000,
});

// --------------------------------------------------------------------------- //
// auth session (token + user kept in localStorage)
// --------------------------------------------------------------------------- //

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function getCurrentUserId() {
  return getStoredUser()?.user_id ?? null;
}

function setSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

// Attach the bearer token to every request once signed in.
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export async function register(email, password) {
  const { data } = await api.post("/auth/register", { email, password });
  setSession(data.access_token, data.user);
  return data.user;
}

export async function login(email, password) {
  const { data } = await api.post("/auth/login", { email, password });
  setSession(data.access_token, data.user);
  return data.user;
}

export function logout() {
  clearSession();
}

/** Validate a stored token against the backend; returns the user or null. */
export async function fetchMe() {
  if (!getToken()) return null;
  try {
    const { data } = await api.get("/auth/me");
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    return data.user;
  } catch {
    clearSession();
    return null;
  }
}

// --------------------------------------------------------------------------- //
// trip helpers
// --------------------------------------------------------------------------- //

export function deleteTrip(tripId) {
  return api.delete(`/trips/${tripId}`).then((res) => res.data);
}

export function droppedMessage(dropped) {
  if (!dropped || dropped.length === 0) return null;
  const names = dropped.map((item) => item.place_name).join(", ");
  return `${names} no longer fit${dropped.length === 1 ? "s" : ""} the daily window and was removed.`;
}

/** Ask what an edit would do. Nothing is written. */
export function previewStopChange(tripId, stopId, body) {
  return api.post(`/trips/${tripId}/stops/${stopId}/preview`, body).then((res) => res.data);
}

/** Rough "how many stops fit" hint for the day-window form. */
export function estimateStopsInWindow(start, end) {
  const toMinutes = (value) => {
    const [hours, minutes] = String(value).split(":").map(Number);
    return hours * 60 + minutes;
  };
  const span = toMinutes(end) - toMinutes(start);
  if (!Number.isFinite(span) || span <= 0) return 0;
  // ~75 min of visiting plus ~30 min of travel per stop.
  return Math.max(1, Math.floor(span / 105));
}

export function formatWindowHint(start, end) {
  const stops = estimateStopsInWindow(start, end);
  if (!stops) return "End time must be after the start time";
  return `about ${stops} stop${stops === 1 ? "" : "s"} including travel`;
}
