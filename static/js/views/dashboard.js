import { api } from "../api.js";
import { setOverdueBadge, state } from "../app.js";
import { formatMoney, h, relativeDue, stageColor, stageLabel } from "../ui.js";

function taskList(tasks, emptyText) {
  if (!tasks.length) return h("p", { class: "empty" }, emptyText);
  return h(
    "ul",
    { class: "task-list" },
    tasks.map((task) => {
      const due = relativeDue(task.due_date);
      return h(
        "li",
        {},
        h("div", {}, h("div", {}, task.title), h("small", { class: "muted" }, task.deal_title)),
        h("span", { class: `when ${due.late ? "late" : ""}` }, due.text),
      );
    }),
  );
}

function pipelineRibbon(data) {
  const closed = new Set(state.config.closed_stages);
  const open = data.deals_by_stage.filter((row) => !closed.has(row.stage));
  const openTotal = open.reduce((sum, row) => sum + row.total_amount, 0);
  const won = data.deals_by_stage.find((row) => row.stage === "won");
  const lost = data.deals_by_stage.find((row) => row.stage === "lost");

  const ribbon = open.length && openTotal > 0
    ? h(
        "div",
        { class: "ribbon", role: "img", "aria-label": "Open pipeline value by stage" },
        open.map((row, index) =>
          h(
            "div",
            {
              class: "ribbon-seg num",
              title: `${stageLabel(row.stage)}: ${formatMoney(row.total_amount)}`,
              style: { flex: `${row.total_amount} 1 0`, background: stageColor(row.stage), animationDelay: `${index * 70}ms` },
            },
            row.total_amount / openTotal > 0.12 ? formatMoney(row.total_amount) : "",
          ),
        ),
      )
    : h("p", { class: "empty" }, "No open deals. New deals appear here as soon as you add them in the pipeline.");

  return h(
    "section",
    { class: "panel" },
    h("div", { class: "panel-head" }, h("h2", {}, "Open pipeline"), h("a", { href: "#/deals" }, "Open board")),
    h(
      "div",
      { class: "ribbon-wrap" },
      ribbon,
      h(
        "div",
        { class: "ribbon-legend" },
        open.map((row) =>
          h(
            "div",
            { style: { borderColor: stageColor(row.stage) } },
            h("b", {}, stageLabel(row.stage)),
            h("span", { class: "num" }, `${row.count} ${row.count === 1 ? "deal" : "deals"}, ${formatMoney(row.total_amount)}`),
          ),
        ),
      ),
      h(
        "div",
        { class: "closed-line num" },
        h("span", {}, "Won: ", h("b", {}, `${won ? won.count : 0} deals, ${formatMoney(won ? won.total_amount : 0)}`)),
        h("span", {}, "Lost: ", h("b", {}, `${lost ? lost.count : 0} deals, ${formatMoney(lost ? lost.total_amount : 0)}`)),
      ),
    ),
  );
}

function managerBars(rows) {
  const max = Math.max(...rows.map((r) => r.total_amount), 1);
  return h(
    "section",
    { class: "panel" },
    h("div", { class: "panel-head" }, h("h2", {}, "Revenue by manager"), h("span", { class: "faint", style: { fontSize: "13px" } }, "dark: won, light: all deals")),
    h(
      "div",
      { class: "panel-body bars" },
      rows.map((row) =>
        h(
          "div",
          { class: "bar-row" },
          h("span", {}, row.username),
          h(
            "div",
            { class: "bar-track", role: "img", "aria-label": `${row.username}: won ${formatMoney(row.won_amount)} of ${formatMoney(row.total_amount)}` },
            h("div", { class: "bar-fill total", style: { width: `${(row.total_amount / max) * 100}%` } }),
            h("div", { class: "bar-fill won", style: { width: `${(row.won_amount / max) * 100}%` } }),
          ),
          h("span", { class: "num" }, formatMoney(row.won_amount)),
        ),
      ),
    ),
  );
}

export async function renderDashboard(main) {
  const data = await api.dashboard();
  setOverdueBadge(data.overdue_total);

  const winRate = data.win_rate == null ? "–" : `${Math.round(data.win_rate * 100)} %`;
  const greeting = state.isAdmin ? "Figures for the whole company." : "Your clients and deals.";

  main.replaceChildren(
    h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Overview"), h("p", {}, greeting))),
    h(
      "dl",
      { class: "kpis" },
      h("div", { class: "kpi" }, h("dt", {}, "Open pipeline"), h("dd", { class: "num" }, formatMoney(data.open_amount))),
      h("div", { class: "kpi" }, h("dt", {}, "Won"), h("dd", { class: "num" }, formatMoney(data.won_amount))),
      h("div", { class: "kpi" }, h("dt", {}, "Win rate"), h("dd", { class: "num" }, winRate, " ", h("small", {}, "of closed deals"))),
      h("div", { class: "kpi" }, h("dt", {}, "Clients"), h("dd", { class: "num" }, data.clients_count)),
    ),
    pipelineRibbon(data),
    h(
      "div",
      { class: "grid-2" },
      h(
        "section",
        { class: "panel" },
        h("div", { class: "panel-head" }, h("h2", {}, `Overdue (${data.overdue_total})`), h("a", { href: "#/tasks" }, "All tasks")),
        h("div", { class: "panel-body" }, taskList(data.overdue_tasks.slice(0, 6), "Nothing overdue.")),
      ),
      h(
        "section",
        { class: "panel" },
        h("div", { class: "panel-head" }, h("h2", {}, "Coming up")),
        h("div", { class: "panel-body" }, taskList(data.upcoming_tasks.slice(0, 6), "No open tasks. Add follow-ups to your deals.")),
      ),
      data.revenue_by_manager && data.revenue_by_manager.length ? managerBars(data.revenue_by_manager) : null,
    ),
  );
}
