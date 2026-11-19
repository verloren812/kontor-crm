import { api } from "../api.js";
import { state } from "../app.js";
import {
  confirmAction, debounce, fieldElement, formatDate, formatMoney, formModal, h, openDrawer,
  stageLabel, statusLabel, toast,
} from "../ui.js";
import { newDealModal, openDealDrawer } from "./deals.js";

const statusOptions = () => state.config.client_statuses.map((s) => [s, statusLabel(s)]);

function clientFields(client = {}) {
  return [
    { name: "name", label: "Company or name", value: client.name, required: true, placeholder: "e.g. Nordlicht Logistik GmbH" },
    { name: "phone", label: "Phone", type: "tel", value: client.phone, required: true, placeholder: "+49 151 2345678", inputmode: "tel" },
    { name: "email", label: "E-mail (optional)", type: "email", value: client.email, placeholder: "info@company.de" },
    { name: "status", label: "Status", type: "select", value: client.status || "new", options: statusOptions() },
  ];
}

async function openClientDrawer(client, refresh) {
  const deals = await api.deals({ client_id: client.id });

  const form = h(
    "form",
    { class: "form-grid" },
    clientFields(client).map(fieldElement),
    h(
      "div",
      { class: "form-actions" },
      state.isAdmin ? h("button", { class: "btn btn-danger spacer", type: "button", onclick: remove }, "Delete client") : null,
      h("button", { class: "btn btn-primary", type: "submit" }, "Save changes"),
    ),
  );
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api.updateClient(client.id, Object.fromEntries(new FormData(form).entries()));
      toast("Changes saved");
      close();
      refresh();
    } catch (err) {
      toast(err.message, "error");
    }
  });

  async function remove() {
    if (!confirmAction(`Delete ${client.name}? Their deals and tasks are deleted too.`)) return;
    try {
      await api.deleteClient(client.id);
      toast("Client deleted");
      close();
      refresh();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  const dealList = h(
    "ul",
    { class: "mini-list" },
    deals.length
      ? deals.map((deal) =>
          h(
            "li",
            {},
            h("button", { class: "link", type: "button", onclick: () => { close(); openDealDrawer(deal.id, refresh); } }, deal.title),
            h("span", { class: "muted num" }, `${stageLabel(deal.stage)}, ${formatMoney(deal.amount)}`),
          ),
        )
      : h("li", { class: "faint" }, "No deals with this client yet."),
  );

  const close = openDrawer({
    title: client.name,
    subtitle: `Client since ${formatDate(client.created_at)}${state.isAdmin ? `, owner: ${state.userName(client.owner_id)}` : ""}`,
    body: [
      form,
      h(
        "section",
        {},
        h("h3", {}, "Deals"),
        dealList,
        h(
          "div",
          { class: "form-actions" },
          h("button", { class: "btn", type: "button", onclick: () => { close(); newDealModal({ clientId: client.id, onCreated: refresh }); } }, "New deal"),
        ),
      ),
    ],
  });
}

export async function renderClients(main) {
  const filters = { search: "", status: "" };
  const tbody = h("tbody");
  const count = h("p", {});

  async function load() {
    const clients = await api.clients(filters);
    count.textContent = `${clients.length} ${clients.length === 1 ? "client" : "clients"}`;
    tbody.replaceChildren(
      ...(clients.length
        ? clients.map((client) =>
            h(
              "tr",
              { class: "clickable", tabindex: "0", onclick: () => openClientDrawer(client, load), onkeydown: (e) => e.key === "Enter" && openClientDrawer(client, load) },
              h("td", { class: "name" }, client.name),
              h("td", { class: "num" }, client.phone),
              h("td", {}, client.email || h("span", { class: "faint" }, "–")),
              h("td", {}, h("span", { class: `pill ${client.status}` }, statusLabel(client.status))),
              state.isAdmin ? h("td", { class: "muted" }, state.userName(client.owner_id)) : null,
            ),
          )
        : [h("tr", {}, h("td", { colspan: 5, class: "empty" }, filters.search || filters.status ? "No clients match these filters." : "No clients yet. Add your first client."))]),
    );
  }

  const search = h("input", { class: "input search", type: "search", placeholder: "Search name, phone or e-mail", "aria-label": "Search clients" });
  search.addEventListener("input", debounce(() => { filters.search = search.value; load(); }));
  const status = h(
    "select",
    { class: "input", "aria-label": "Filter by status", onchange: (e) => { filters.status = e.target.value; load(); } },
    h("option", { value: "" }, "All statuses"),
    statusOptions().map(([value, label]) => h("option", { value }, label)),
  );

  const newClient = () =>
    formModal({
      title: "New client",
      submitLabel: "Add client",
      fields: clientFields(),
      onSubmit: async (values) => {
        await api.createClient(values);
        toast("Client added");
        load();
      },
    });

  main.replaceChildren(
    h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Clients"), count), h("button", { class: "btn btn-primary", onclick: newClient }, "New client")),
    h("div", { class: "toolbar" }, search, status),
    h(
      "div",
      { class: "panel table-wrap" },
      h(
        "table",
        { class: "data" },
        h("thead", {}, h("tr", {}, h("th", {}, "Name"), h("th", {}, "Phone"), h("th", {}, "E-mail"), h("th", {}, "Status"), state.isAdmin ? h("th", {}, "Owner") : null)),
        tbody,
      ),
    ),
  );
  await load();
}
