// Small UI toolkit: DOM builder, formatting, toast, drawer, modal.
// Text always goes in as text nodes, never as HTML, so user data cannot inject markup.

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "style" && typeof value === "object") Object.assign(el.style, value);
    else if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
    else if (key === "dataset") Object.assign(el.dataset, value);
    else if (value === true) el.setAttribute(key, "");
    else el.setAttribute(key, value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

const ICON_PATHS = {
  dashboard: "M4 13h6V4H4v9Zm0 7h6v-5H4v5Zm10 0h6v-9h-6v9Zm0-16v5h6V4h-6Z",
  clients: "M16 11a4 4 0 1 0-4-4 4 4 0 0 0 4 4Zm-8 1a3 3 0 1 0-3-3 3 3 0 0 0 3 3Zm0 2c-2.7 0-6 1.3-6 3.5V20h6v-2.5c0-1.2.5-2.3 1.4-3.2A9 9 0 0 0 8 14Zm8-1c-3 0-7 1.5-7 4v3h14v-3c0-2.5-4-4-7-4Z",
  deals: "M3 5h4v14H3V5Zm7 0h4v9h-4V5Zm7 0h4v6h-4V5Z",
  tasks: "M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2Z",
  users: "M12 12a5 5 0 1 0-5-5 5 5 0 0 0 5 5Zm0 2c-3.3 0-10 1.7-10 5v3h20v-3c0-3.3-6.7-5-10-5Z",
  trash: "M9 3h6l1 2h4v2H4V5h4l1-2Zm-3 6h12l-1 12H7L6 9Z",
};

export function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", ICON_PATHS[name]);
  path.setAttribute("fill", "currentColor");
  svg.append(path);
  return svg;
}

// --- labels and formatting ---

export const STAGE_LABELS = {
  new: "New",
  qualified: "Qualified",
  proposal: "Proposal",
  negotiation: "Negotiation",
  won: "Won",
  lost: "Lost",
};

export const STATUS_LABELS = {
  new: "New",
  in_progress: "In progress",
  regular: "Regular customer",
  rejected: "Rejected",
};

export const stageLabel = (stage) => STAGE_LABELS[stage] || stage;
export const statusLabel = (status) => STATUS_LABELS[status] || status;
export const stageColor = (stage) => `var(--stage-${stage}, var(--ink-faint))`;

// The app targets German businesses: euro amounts and dates in German format.
const money = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
const moneyExact = new Intl.NumberFormat("de-DE", { style: "currency", currency: "EUR" });
const dateFmt = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat("de-DE", {
  day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
});

export const formatMoney = (value, exact = false) => (exact ? moneyExact : money).format(Number(value || 0));
export const formatDate = (iso) => (iso ? dateFmt.format(new Date(iso)) : "");
export const formatDateTime = (iso) => (iso ? dateTimeFmt.format(new Date(iso)) : "");

export function relativeDue(iso) {
  if (!iso) return { text: "No due date", late: false };
  const due = new Date(iso);
  const now = new Date();
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((startOfDay(due) - startOfDay(now)) / 86400000);
  const late = due < now;
  if (days === 0) return { text: late ? "Today, overdue" : "Today", late };
  if (days === 1) return { text: "Tomorrow", late };
  if (days === -1) return { text: "Yesterday", late };
  if (days < 0) return { text: `${-days} days overdue`, late };
  if (days < 7) return { text: `In ${days} days`, late };
  return { text: formatDate(iso), late };
}

// <input type="datetime-local"> works in local time without an offset.
export function toLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
export const fromLocalInput = (value) => (value ? new Date(value).toISOString() : null);

// --- toast ---

export function toast(message, type = "info") {
  const el = h("div", { class: `toast ${type === "error" ? "error" : ""}` }, message);
  document.getElementById("toasts").append(el);
  setTimeout(() => el.remove(), type === "error" ? 5000 : 2600);
}

// --- overlays (drawer and modal share the close logic) ---

function openOverlay(panel) {
  const previousFocus = document.activeElement;
  const backdrop = h("div", { class: "overlay" });
  const close = () => {
    backdrop.remove();
    panel.remove();
    document.removeEventListener("keydown", onKey);
    if (previousFocus && previousFocus.focus) previousFocus.focus();
  };
  const onKey = (event) => {
    if (event.key === "Escape") close();
  };
  backdrop.addEventListener("click", close);
  document.addEventListener("keydown", onKey);
  document.body.append(backdrop, panel);
  const first = panel.querySelector("input, select, textarea, button:not(.close)");
  (first || panel).focus();
  return close;
}

export function openDrawer({ title, subtitle, body }) {
  const closeButton = h("button", { class: "close", "aria-label": "Close" }, "×");
  const panel = h(
    "aside",
    { class: "drawer", role: "dialog", "aria-modal": "true", "aria-label": title, tabindex: "-1" },
    h("div", { class: "drawer-head" }, h("div", {}, h("h2", {}, title), subtitle ? h("p", {}, subtitle) : null), closeButton),
    h("div", { class: "drawer-body" }, body),
  );
  const close = openOverlay(panel);
  closeButton.addEventListener("click", close);
  return close;
}

/**
 * Form in a modal. `fields`: [{name, label, type, options, value, required, ...}]
 * `onSubmit(values)` may throw; the error is shown and the modal stays open.
 */
export function formModal({ title, fields, submitLabel, onSubmit, extraActions = [] }) {
  const error = h("p", { class: "form-error", hidden: true });
  const submit = h("button", { class: "btn btn-primary", type: "submit" }, submitLabel);
  const form = h(
    "form",
    { class: "form-grid", novalidate: false },
    fields.map(fieldElement),
    error,
    h("div", { class: "form-actions" }, extraActions, h("button", { class: "btn", type: "button", onclick: () => close() }, "Cancel"), submit),
  );
  const panel = h("div", { class: "modal", role: "dialog", "aria-modal": "true", "aria-label": title }, h("h2", {}, title), form);
  const close = openOverlay(panel);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(form).entries());
    submit.disabled = true;
    error.hidden = true;
    try {
      await onSubmit(values);
      close();
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
    } finally {
      submit.disabled = false;
    }
  });
  return close;
}

export function fieldElement(field) {
  const id = `f-${field.name}-${Math.random().toString(36).slice(2, 7)}`;
  let control;
  const common = { id, name: field.name, class: "input", required: field.required, placeholder: field.placeholder };
  if (field.type === "select") {
    control = h(
      "select",
      common,
      field.options.map(([value, label]) => h("option", { value, selected: String(value) === String(field.value ?? "") }, label)),
    );
  } else if (field.type === "textarea") {
    control = h("textarea", common, field.value ?? "");
  } else {
    control = h("input", {
      ...common,
      type: field.type || "text",
      value: field.value ?? "",
      min: field.min,
      step: field.step,
      minlength: field.minlength,
      autocomplete: field.autocomplete || "off",
      inputmode: field.inputmode,
    });
  }
  return h("div", { class: "field" }, h("label", { for: id }, field.label), control);
}

export function confirmAction(message) {
  // Native confirm() is blocked inside some sandboxed iframes; fall back to "yes".
  try {
    return window.confirm(message);
  } catch {
    return true;
  }
}

export function debounce(fn, ms = 250) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}
