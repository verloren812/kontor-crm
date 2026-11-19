import { api } from "../api.js";
import { state } from "../app.js";
import { formatDate, formModal, h, toast } from "../ui.js";

export async function renderUsers(main) {
  const tbody = h("tbody");

  async function load() {
    state.users = await api.users();
    tbody.replaceChildren(
      ...state.users.map((user) => {
        const select = h(
          "select",
          {
            class: "input",
            style: { width: "auto" },
            "aria-label": `Role of ${user.username}`,
            disabled: user.id === state.me.id,
            title: user.id === state.me.id ? "You cannot change your own role" : null,
            onchange: async (e) => {
              try {
                await api.updateRole(user.id, e.target.value);
                toast(`${user.username} is now ${e.target.value === "admin" ? "an admin" : "a sales manager"}`);
              } catch (err) {
                toast(err.message, "error");
              }
              load();
            },
          },
          h("option", { value: "manager", selected: user.role === "manager" }, "Sales manager"),
          h("option", { value: "admin", selected: user.role === "admin" }, "Admin"),
        );
        return h(
          "tr",
          {},
          h("td", { class: "name" }, user.username, user.id === state.me.id ? h("span", { class: "faint" }, " (you)") : null),
          h("td", {}, select),
          h("td", { class: "muted num" }, formatDate(user.created_at)),
        );
      }),
    );
  }

  const newUser = () =>
    formModal({
      title: "New team member",
      submitLabel: "Create account",
      fields: [
        { name: "username", label: "Username", required: true, minlength: "3" },
        { name: "password", label: "Initial password (min. 8 characters)", type: "password", required: true, minlength: "8", autocomplete: "new-password" },
        { name: "role", label: "Role", type: "select", value: "manager", options: [["manager", "Sales manager"], ["admin", "Admin"]] },
      ],
      onSubmit: async (values) => {
        await api.createUser(values);
        toast(`Account for ${values.username} created`);
        load();
      },
    });

  main.replaceChildren(
    h(
      "div",
      { class: "page-head" },
      h("div", {}, h("h1", {}, "Team"), h("p", {}, "Managers see their own and unassigned clients. Admins see everything.")),
      h("button", { class: "btn btn-primary", onclick: newUser }, "New team member"),
    ),
    h(
      "div",
      { class: "panel table-wrap" },
      h("table", { class: "data" }, h("thead", {}, h("tr", {}, h("th", {}, "Username"), h("th", {}, "Role"), h("th", {}, "Since"))), tbody),
    ),
  );
  await load();
}
