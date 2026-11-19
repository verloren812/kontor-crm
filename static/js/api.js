// Thin wrapper around fetch: adds the token, turns API errors into readable messages.

const TOKEN_KEY = "kontor_token";

function storage(action, value) {
  // localStorage can be unavailable (privacy mode, sandboxed iframes).
  try {
    if (action === "get") return localStorage.getItem(TOKEN_KEY);
    if (action === "set") localStorage.setItem(TOKEN_KEY, value);
    if (action === "clear") localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* fall back to the in-memory token */
  }
  return null;
}

let memoryToken = storage("get");
let onUnauthorized = () => {};

export const auth = {
  get token() {
    return memoryToken;
  },
  set(token) {
    memoryToken = token;
    storage("set", token);
  },
  clear() {
    memoryToken = null;
    storage("clear");
  },
  onUnauthorized(handler) {
    onUnauthorized = handler;
  },
};

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function describe(detail) {
  if (!detail) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  // FastAPI validation errors: [{loc: [...], msg: "..."}]
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0];
    const field = (first.loc || []).filter((part) => part !== "body").join(".");
    const message = String(first.msg || "Invalid value").replace(/^Value error, /, "");
    const label = field ? field.charAt(0).toUpperCase() + field.slice(1).replace(/_/g, " ") : "";
    return label ? `${label}: ${message}` : message;
  }
  return "Something went wrong. Please try again.";
}

export async function request(method, path, body, { form = false } = {}) {
  const headers = {};
  if (memoryToken) headers.Authorization = `Bearer ${memoryToken}`;
  let payload;
  if (form) {
    payload = new URLSearchParams(body);
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(path, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "The server cannot be reached. Check your connection.");
  }

  if (response.status === 401 && memoryToken) {
    auth.clear();
    onUnauthorized();
  }
  if (response.status === 204) return null;

  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, describe(data && data.detail));
  return data;
}

function query(params = {}) {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return entries.length ? "?" + new URLSearchParams(entries).toString() : "";
}

export const api = {
  config: () => request("GET", "/api/config"),
  login: (username, password) => request("POST", "/api/auth/login", { username, password }, { form: true }),
  me: () => request("GET", "/api/users/me"),

  dashboard: () => request("GET", "/api/analytics/dashboard"),

  clients: (params) => request("GET", "/api/clients/" + query({ limit: 500, ...params })),
  createClient: (data) => request("POST", "/api/clients/", data),
  updateClient: (id, data) => request("PATCH", `/api/clients/${id}`, data),
  deleteClient: (id) => request("DELETE", `/api/clients/${id}`),

  deals: (params) => request("GET", "/api/deals/" + query({ limit: 500, ...params })),
  deal: (id) => request("GET", `/api/deals/${id}`),
  dealHistory: (id) => request("GET", `/api/deals/${id}/history`),
  createDeal: (data) => request("POST", "/api/deals/", data),
  updateDeal: (id, data) => request("PATCH", `/api/deals/${id}`, data),
  deleteDeal: (id) => request("DELETE", `/api/deals/${id}`),

  tasks: (params) => request("GET", "/api/tasks/" + query({ limit: 500, ...params })),
  createTask: (data) => request("POST", "/api/tasks/", data),
  updateTask: (id, data) => request("PATCH", `/api/tasks/${id}`, data),
  deleteTask: (id) => request("DELETE", `/api/tasks/${id}`),

  users: () => request("GET", "/api/users/"),
  createUser: (data) => request("POST", "/api/auth/register", data),
  updateRole: (id, role) => request("PATCH", `/api/users/${id}/role`, { role }),
};
