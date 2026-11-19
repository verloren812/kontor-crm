import { api } from "../api.js";
import { setOverdueBadge } from "../app.js";
import { confirmAction, formModal, fromLocalInput, h, icon, relativeDue, toast } from "../ui.js";

function group(tasks) {
  const now = new Date();
  const endOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
  const endOfWeek = new Date(endOfToday.getTime() + 6 * 86400000);
  const groups = { overdue: [], today: [], week: [], later: [], none: [] };
  for (const task of tasks) {
    if (!task.due_date) groups.none.push(task);
    else {
      const due = new Date(task.due_date);
      if (due < now) groups.overdue.push(task);
      else if (due < endOfToday) groups.today.push(task);
      else if (due < endOfWeek) groups.week.push(task);
      else groups.later.push(task);
    }
  }
  return groups;
}

const GROUP_TITLES = { overdue: "Overdue", today: "Today", week: "Next 7 days", later: "Later", none: "No due date" };

export async function renderTasks(main) {
  let showDone = false;
  const list = h("div");

  function row(task) {
    const due = relativeDue(task.due_date);
    const checkbox = h("input", {
      type: "checkbox",
      checked: task.is_done,
      "aria-label": `Mark "${task.title}" as ${task.is_done ? "open" : "done"}`,
      onchange: async () => {
        try {
          await api.updateTask(task.id, { is_done: !task.is_done });
          toast(task.is_done ? "Task reopened" : "Task done");
          load();
        } catch (err) {
          toast(err.message, "error");
        }
      },
    });
    return h(
      "div",
      { class: `task-row ${task.is_done ? "done" : ""}` },
      checkbox,
      h("div", {}, h("div", { class: "title" }, task.title), h("div", { class: "deal" }, task.deal_title), task.description ? h("div", { class: "faint", style: { fontSize: "13px" } }, task.description) : null),
      h("span", { class: `when ${due.late && !task.is_done ? "late" : ""}` }, due.text),
      h(
        "button",
        {
          class: "icon-btn",
          type: "button",
          "aria-label": `Delete "${task.title}"`,
          onclick: async () => {
            if (!confirmAction(`Delete "${task.title}"?`)) return;
            await api.deleteTask(task.id).catch((err) => toast(err.message, "error"));
            load();
          },
        },
        icon("trash"),
      ),
    );
  }

  async function load() {
    const tasks = await api.tasks({ is_done: showDone });
    if (!showDone) setOverdueBadge(tasks.filter((t) => t.due_date && new Date(t.due_date) < new Date()).length);
    if (!tasks.length) {
      list.replaceChildren(h("div", { class: "panel panel-body" }, h("p", { class: "empty" }, showDone ? "No completed tasks yet." : "All caught up. Add a follow-up for one of your deals.")));
      return;
    }
    if (showDone) {
      list.replaceChildren(h("div", { class: "panel" }, tasks.map(row)));
      return;
    }
    const groups = group(tasks);
    list.replaceChildren(
      ...Object.entries(groups)
        .filter(([, items]) => items.length)
        .map(([key, items]) =>
          h("section", { class: `task-group ${key}` }, h("h2", {}, GROUP_TITLES[key], h("span", {}, items.length)), h("div", { class: "panel" }, items.map(row))),
        ),
    );
  }

  const tabs = h(
    "div",
    { class: "tabs", role: "group", "aria-label": "Show" },
    [["Open", false], ["Done", true]].map(([label, value]) =>
      h("button", {
        type: "button",
        "aria-pressed": String(value === showDone),
        onclick: (e) => {
          showDone = value;
          tabs.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === e.currentTarget)));
          load();
        },
      }, label),
    ),
  );

  async function newTask() {
    const deals = await api.deals();
    if (!deals.length) {
      toast("Create a deal first: every task belongs to a deal.", "error");
      return;
    }
    formModal({
      title: "New task",
      submitLabel: "Add task",
      fields: [
        { name: "title", label: "Task", required: true, placeholder: "e.g. Send updated proposal" },
        { name: "deal_id", label: "Deal", type: "select", options: deals.map((d) => [d.id, `${d.title} (${d.client_name})`]) },
        { name: "due_date", label: "Due", type: "datetime-local" },
        { name: "description", label: "Notes (optional)", type: "textarea" },
      ],
      onSubmit: async (values) => {
        await api.createTask({
          title: values.title,
          deal_id: Number(values.deal_id),
          due_date: fromLocalInput(values.due_date),
          description: values.description || null,
        });
        toast("Task added");
        load();
      },
    });
  }

  main.replaceChildren(
    h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Tasks"), h("p", {}, "Follow-ups for your deals, sorted by due date.")), h("button", { class: "btn btn-primary", onclick: newTask }, "New task")),
    h("div", { class: "toolbar" }, tabs),
    list,
  );
  await load();
}
