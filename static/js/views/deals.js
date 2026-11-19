import { api } from "../api.js";
import { state } from "../app.js";
import {
  confirmAction, fieldElement, formatDateTime, formatMoney, formModal, fromLocalInput, h,
  openDrawer, relativeDue, stageColor, stageLabel, toast,
} from "../ui.js";

const stageOptions = () => state.config.deal_stages.map((s) => [s, stageLabel(s)]);

export async function newDealModal({ clientId, onCreated } = {}) {
  const clients = await api.clients();
  if (!clients.length) {
    toast("Add a client first: every deal belongs to a client.", "error");
    return;
  }
  formModal({
    title: "New deal",
    submitLabel: "Create deal",
    fields: [
      { name: "client_id", label: "Client", type: "select", value: clientId, options: clients.map((c) => [c.id, c.name]) },
      { name: "title", label: "Title", required: true, placeholder: "e.g. Online shop" },
      { name: "amount", label: "Value (€)", type: "number", min: "0", step: "0.01", value: "0", inputmode: "decimal", required: true },
      { name: "stage", label: "Stage", type: "select", value: "new", options: stageOptions() },
    ],
    onSubmit: async (values) => {
      const deal = await api.createDeal({ ...values, client_id: Number(values.client_id) });
      toast("Deal created");
      onCreated && onCreated(deal);
    },
  });
}

/** Deal details: edit, stage history, tasks. Also opened from the client drawer. */
export async function openDealDrawer(dealId, onChange = () => {}) {
  const [deal, history, tasks] = await Promise.all([
    api.deal(dealId),
    api.dealHistory(dealId),
    api.tasks({ deal_id: dealId }),
  ]);

  const form = h(
    "form",
    { class: "form-grid" },
    fieldElement({ name: "title", label: "Title", value: deal.title, required: true }),
    h(
      "div",
      { class: "row-2" },
      fieldElement({ name: "amount", label: "Value (€)", type: "number", min: "0", step: "0.01", value: deal.amount, inputmode: "decimal" }),
      fieldElement({ name: "stage", label: "Stage", type: "select", value: deal.stage, options: stageOptions() }),
    ),
    h(
      "div",
      { class: "form-actions" },
      h("button", { class: "btn btn-danger spacer", type: "button", onclick: remove }, "Delete deal"),
      h("button", { class: "btn btn-primary", type: "submit" }, "Save changes"),
    ),
  );
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api.updateDeal(deal.id, Object.fromEntries(new FormData(form).entries()));
      toast("Changes saved");
      close();
      onChange();
    } catch (err) {
      toast(err.message, "error");
    }
  });

  async function remove() {
    if (!confirmAction(`Delete "${deal.title}" and its tasks?`)) return;
    try {
      await api.deleteDeal(deal.id);
      toast("Deal deleted");
      close();
      onChange();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  const taskTitle = h("input", { class: "input", placeholder: "New follow-up, e.g. Call back", "aria-label": "New task title", required: true });
  const taskDue = h("input", { class: "input", type: "datetime-local", "aria-label": "Due date" });
  const taskItems = h("ul", { class: "mini-list" });
  const renderTasks = (list) => {
    taskItems.replaceChildren(
      ...(list.length
        ? list.map((t) => {
            const due = relativeDue(t.due_date);
            return h("li", {}, h("span", { style: t.is_done ? { textDecoration: "line-through", color: "var(--ink-faint)" } : {} }, t.title), h("span", { class: due.late && !t.is_done ? "faint" : "muted" }, t.is_done ? "Done" : due.text));
          })
        : [h("li", { class: "faint" }, "No tasks yet.")]),
    );
  };
  renderTasks(tasks);
  const taskForm = h(
    "form",
    { class: "form-grid", style: { marginTop: "10px" } },
    h("div", { class: "row-2" }, taskTitle, taskDue),
    h("div", { class: "form-actions" }, h("button", { class: "btn", type: "submit" }, "Add task")),
  );
  taskForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api.createTask({ title: taskTitle.value, due_date: fromLocalInput(taskDue.value), deal_id: deal.id });
      taskTitle.value = "";
      taskDue.value = "";
      renderTasks(await api.tasks({ deal_id: deal.id }));
      toast("Task added");
      onChange();
    } catch (err) {
      toast(err.message, "error");
    }
  });

  const timeline = h(
    "ol",
    { class: "timeline" },
    history.map((change) =>
      h(
        "li",
        { style: { "--stage-color": stageColor(change.to_stage) } },
        change.from_stage ? `${stageLabel(change.from_stage)} to ${stageLabel(change.to_stage)}` : `Created in ${stageLabel(change.to_stage)}`,
        h("small", {}, `${formatDateTime(change.changed_at)}${change.changed_by_name ? `, by ${change.changed_by_name}` : ""}`),
      ),
    ),
  );

  const close = openDrawer({
    title: deal.title,
    subtitle: `${deal.client_name}, ${formatMoney(deal.amount, true)}`,
    body: [
      form,
      h("section", {}, h("h3", {}, "Tasks"), taskItems, taskForm),
      h("section", {}, h("h3", {}, "Stage history"), timeline),
      state.isAdmin ? h("p", { class: "faint", style: { margin: 0, fontSize: "13px" } }, `Owner: ${state.userName(deal.owner_id)}`) : null,
    ],
  });
}

function dealCard(deal, onOpen) {
  const card = h(
    "button",
    { class: "deal-card", type: "button", draggable: "true", dataset: { id: deal.id }, onclick: () => onOpen(deal.id) },
    h("b", {}, deal.title),
    h("span", { class: "client" }, deal.client_name),
    h(
      "span",
      { class: "meta" },
      h("span", { class: "amount num" }, formatMoney(deal.amount)),
      state.isAdmin ? h("span", { class: "faint" }, state.userName(deal.owner_id)) : null,
    ),
  );
  card.addEventListener("dragstart", (event) => {
    event.dataTransfer.setData("text/plain", String(deal.id));
    event.dataTransfer.effectAllowed = "move";
    card.classList.add("dragging");
  });
  card.addEventListener("dragend", () => card.classList.remove("dragging"));
  return card;
}

export async function renderDeals(main) {
  const deals = await api.deals();
  const byId = new Map(deals.map((d) => [d.id, d]));
  const refresh = () => renderDeals(main);
  const open = (id) => openDealDrawer(id, refresh).catch((err) => toast(err.message, "error"));

  const columns = state.config.deal_stages.map((stage) => {
    const items = deals.filter((d) => d.stage === stage);
    const total = items.reduce((sum, d) => sum + d.amount, 0);
    const cards = h("div", { class: "cards" }, items.map((d) => dealCard(d, open)));
    const column = h(
      "section",
      { class: "column", style: { "--stage-color": stageColor(stage) }, "aria-label": stageLabel(stage) },
      h("div", { class: "column-head" }, h("h2", {}, stageLabel(stage)), h("span", {}, items.length)),
      h("div", { class: "column-sum num" }, formatMoney(total)),
      cards,
    );

    column.addEventListener("dragover", (event) => {
      event.preventDefault();
      column.classList.add("drop-target");
    });
    column.addEventListener("dragleave", (event) => {
      if (!column.contains(event.relatedTarget)) column.classList.remove("drop-target");
    });
    column.addEventListener("drop", async (event) => {
      event.preventDefault();
      column.classList.remove("drop-target");
      const deal = byId.get(Number(event.dataTransfer.getData("text/plain")));
      if (!deal || deal.stage === stage) return;
      try {
        await api.updateDeal(deal.id, { stage });
        toast(`"${deal.title}" moved to ${stageLabel(stage)}`);
      } catch (err) {
        toast(err.message, "error");
      }
      refresh();
    });
    return column;
  });

  main.replaceChildren(
    h(
      "div",
      { class: "page-head" },
      h("div", {}, h("h1", {}, "Pipeline"), h("p", {}, "Drag a deal to another column to change its stage.")),
      h("button", { class: "btn btn-primary", onclick: () => newDealModal({ onCreated: refresh }) }, "New deal"),
    ),
    deals.length
      ? h("div", { class: "board" }, columns)
      : h("div", { class: "panel panel-body" }, h("p", { class: "empty" }, "No deals yet. Create the first one to fill the pipeline.")),
  );
}
