// Entry point: login screen, app shell and hash router (#/dashboard, #/clients, ...).
import { api, auth } from "./api.js";
import { h, icon, toast } from "./ui.js";
import { renderDashboard } from "./views/dashboard.js";
import { renderClients } from "./views/clients.js";
import { renderDeals } from "./views/deals.js";
import { renderTasks } from "./views/tasks.js";
import { renderUsers } from "./views/users.js";

const root = document.getElementById("app");

// Shared state for all views.
export const state = {
  config: { deal_stages: [], closed_stages: [], client_statuses: [], demo_mode: false, demo_accounts: [] },
  me: null,
  users: [], // admins only: used to show who owns what
  get isAdmin() {
    return this.me && this.me.role === "admin";
  },
  userName(id) {
    if (id == null) return "Unassigned";
    if (this.me && id === this.me.id) return "You";
    const user = this.users.find((u) => u.id === id);
    return user ? user.username : `User #${id}`;
  },
};

const ROUTES = {
  dashboard: { label: "Overview", icon: "dashboard", render: renderDashboard },
  deals: { label: "Pipeline", icon: "deals", render: renderDeals },
  clients: { label: "Clients", icon: "clients", render: renderClients },
  tasks: { label: "Tasks", icon: "tasks", render: renderTasks },
  users: { label: "Team", icon: "users", render: renderUsers, adminOnly: true },
};

function brand() {
  return h("div", { class: "brand" }, h("span", { class: "brand-mark", "aria-hidden": "true" }, h("span")), h("span", { class: "brand-name" }, "Kontor CRM"));
}

// --- login ---

function renderLogin() {
  const error = h("p", { class: "form-error", role: "alert", hidden: true });
  const username = h("input", { class: "input", id: "login-user", name: "username", autocomplete: "username", required: true });
  const password = h("input", { class: "input", id: "login-pass", name: "password", type: "password", autocomplete: "current-password", required: true });
  const submit = h("button", { class: "btn btn-primary", type: "submit" }, "Sign in");

  async function signIn(user, pass) {
    submit.disabled = true;
    error.hidden = true;
    try {
      const { access_token } = await api.login(user, pass);
      auth.set(access_token);
      await start();
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
      submit.disabled = false;
    }
  }

  const form = h(
    "form",
    { onsubmit: (e) => { e.preventDefault(); signIn(username.value, password.value); } },
    h("div", { class: "field" }, h("label", { for: "login-user" }, "Username"), username),
    h("div", { class: "field" }, h("label", { for: "login-pass" }, "Password"), password),
    error,
    submit,
  );

  const demo = state.config.demo_mode && state.config.demo_accounts.length
    ? h(
        "div",
        { class: "demo-box" },
        h("p", {}, "This is a public demo with fictional data. Pick an account to look around:"),
        h(
          "div",
          { class: "demo-accounts" },
          state.config.demo_accounts.map((account) =>
            h(
              "button",
              { class: "demo-account", type: "button", onclick: () => signIn(account.username, account.password) },
              h("span", {}, account.username),
              h("small", {}, account.role === "admin" ? "Admin, sees everything" : "Sales manager"),
            ),
          ),
        ),
      )
    : null;

  root.replaceChildren(
    h(
      "main",
      { class: "login" },
      h(
        "div",
        { class: "login-panel" },
        brand(),
        h("h1", {}, "Sign in"),
        h("p", { class: "muted", style: { margin: 0 } }, "Clients, deals and follow-ups in one place."),
        form,
        demo,
      ),
    ),
  );
  username.focus();
}

// --- shell & routing ---

let main;
let navLinks = {};

function renderShell() {
  navLinks = {};
  const nav = h(
    "nav",
    { class: "nav", "aria-label": "Main" },
    Object.entries(ROUTES)
      .filter(([, route]) => !route.adminOnly || state.isAdmin)
      .map(([key, route]) => {
        const link = h("a", { href: `#/${key}` }, icon(route.icon), h("span", { class: "label" }, route.label));
        navLinks[key] = link;
        return link;
      }),
  );
  main = h("main", { class: "main", id: "main", tabindex: "-1" });
  root.replaceChildren(
    h(
      "div",
      { class: "shell" },
      h(
        "aside",
        { class: "sidebar" },
        brand(),
        nav,
        h(
          "div",
          { class: "sidebar-foot" },
          h("strong", {}, state.me.username),
          h("span", { class: "role" }, state.isAdmin ? "Admin" : "Sales manager"),
          h("br"),
          h("button", { type: "button", onclick: logout }, "Sign out"),
        ),
      ),
      main,
    ),
  );
}

export function setOverdueBadge(count) {
  const link = navLinks.tasks;
  if (!link) return;
  link.querySelector(".count")?.remove();
  if (count > 0) link.append(h("span", { class: "count", title: `${count} overdue` }, count));
}

async function route() {
  if (!state.me) return;
  const key = (location.hash.replace(/^#\/?/, "").split("?")[0] || "dashboard");
  const target = ROUTES[key] && (!ROUTES[key].adminOnly || state.isAdmin) ? key : "dashboard";
  for (const [name, link] of Object.entries(navLinks)) {
    if (name === target) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  document.title = `${ROUTES[target].label} - Kontor CRM`;
  main.replaceChildren(h("p", { class: "loading" }, "Loading…"));
  try {
    await ROUTES[target].render(main);
  } catch (err) {
    main.replaceChildren(h("p", { class: "form-error" }, err.message));
  }
}

function logout() {
  auth.clear();
  state.me = null;
  history.replaceState(null, "", location.pathname);
  renderLogin();
}

async function start() {
  try {
    state.me = await api.me();
  } catch {
    auth.clear();
    renderLogin();
    return;
  }
  state.users = state.isAdmin ? await api.users().catch(() => []) : [];
  renderShell();
  await route();
}

auth.onUnauthorized(() => {
  if (state.me) toast("Your session has expired. Please sign in again.", "error");
  state.me = null;
  renderLogin();
});
window.addEventListener("hashchange", route);

(async function boot() {
  state.config = await api.config().catch(() => state.config);
  if (auth.token) await start();
  else renderLogin();
})();
