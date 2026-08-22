/* EasyTHS 内嵌 Web 控制台
 *
 * 零依赖单页应用：页面与静态资源公开，所有数据请求走 /api/v1，
 * 服务启用认证时自动出现 API Key 登录（密钥仅存于本机 localStorage）。
 * 操作表单由 /operations/ 返回的参数 JSON Schema 动态生成，
 * 新增操作插件无需修改本文件。
 */
"use strict";

const API_BASE = "/api/v1";
const KEY_STORAGE = "easyths_api_key";
/* 服务端阻塞等待上限 55s，超时（408）后由前端继续发起下一轮 */
const RESULT_POLL_TIMEOUT = 55;

const state = {
  apiKey: localStorage.getItem(KEY_STORAGE) || "",
  authRequired: false,
  operations: {},
  accounts: [],
  currentAccount: "",
  focusId: null,
  activeOp: null,
  recent: [],
  timers: [],
};

/* ============ 通用 DOM 工具 ============ */

const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    /* 空字符串是合法值（如 <option value="">），只跳过未提供的属性 */
    if (value === undefined || value === null) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2), value);
    } else node.setAttribute(key, value);
  }
  for (const child of children) {
    if (child === null || child === undefined) continue;
    node.append(child);
  }
  return node;
}

function fmt(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : String(Math.round(value * 1000) / 1000);
  }
  return String(value);
}

let toastTimer = null;
function toast(message, isError = false) {
  const node = $("toast");
  node.textContent = message;
  node.className = isError ? "err" : "";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.add("hidden"), 3200);
}

/* ============ API 层（统一信封） ============ */

async function rawApi(path, { method = "GET", body, withKey = true } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (withKey && state.apiKey) headers["Authorization"] = `Bearer ${state.apiKey}`;
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  let envelope = null;
  try {
    envelope = await response.json();
  } catch {
    /* 非 JSON 响应按无信封处理 */
  }
  return { status: response.status, envelope };
}

async function api(path, options = {}) {
  const { status, envelope } = await rawApi(path, options);
  if (status === 401) {
    handleAuthLost();
    throw new Error("unauthorized");
  }
  if (status === 429) {
    toast("请求过于频繁，请稍后再试", true);
    throw new Error("rate_limited");
  }
  if (status >= 400) {
    throw new Error(envelope ? envelope.message || `请求失败 (${status})` : `请求失败 (${status})`);
  }
  return envelope;
}

/* ============ 启动与认证 ============ */

async function init() {
  let probe;
  try {
    probe = await rawApi("/system/health", { withKey: false });
  } catch {
    showFatal("服务不可达，请确认 API 服务已启动");
    return;
  }
  if (probe.status === 403) {
    showFatal("当前 IP 不在服务白名单内，无法访问");
    return;
  }
  if (probe.status !== 401) {
    enterApp();
    return;
  }
  /* 需要认证：有已存密钥则静默验证，否则弹出登录 */
  state.authRequired = true;
  $("logout-btn").classList.remove("hidden");
  if (state.apiKey) {
    const verify = await rawApi("/system/health");
    if (verify.status !== 401) {
      enterApp();
      return;
    }
    state.apiKey = "";
    localStorage.removeItem(KEY_STORAGE);
  }
  $("login-overlay").classList.remove("hidden");
  $("api-key-input").focus();
}

async function handleLogin(event) {
  event.preventDefault();
  const input = $("api-key-input");
  const key = input.value.trim();
  if (!key) return;
  $("login-error").classList.add("hidden");
  state.apiKey = key;
  const verify = await rawApi("/system/health");
  if (verify.status === 401) {
    $("login-error").textContent = "API Key 无效，请重新输入";
    $("login-error").classList.remove("hidden");
    state.apiKey = "";
    return;
  }
  if (verify.status === 403) {
    state.apiKey = "";
    showFatal("当前 IP 不在服务白名单内，无法访问");
    return;
  }
  localStorage.setItem(KEY_STORAGE, key);
  $("login-overlay").classList.add("hidden");
  enterApp();
}

function handleAuthLost() {
  if (!$("login-overlay").classList.contains("hidden")) return;
  stopTimers();
  state.apiKey = "";
  localStorage.removeItem(KEY_STORAGE);
  $("app").classList.add("hidden");
  $("login-overlay").classList.remove("hidden");
  $("login-error").textContent = "API Key 已失效，请重新输入";
  $("login-error").classList.remove("hidden");
}

function showFatal(message) {
  $("fatal-message").textContent = message;
  $("fatal-overlay").classList.remove("hidden");
}

/* ============ 应用主流程 ============ */

async function enterApp() {
  $("app").classList.remove("hidden");
  try {
    const list = await api("/operations/");
    state.operations = list.data.operations;
  } catch {
    return; /* api() 已提示错误原因 */
  }
  renderSidebar();
  state.timers.push(setInterval(refreshHealth, 15000));
  state.timers.push(setInterval(refreshQueueStats, 5000));
  refreshHealth();
  refreshQueueStats();
  /* 账户缓存直接取服务端内存快照（启动初始化已有），无需执行 account_query */
  api("/system/status")
    .then((envelope) => {
      const data = envelope.data;
      $("version").textContent = `v${data.version}`;
      if (data.account) {
        if (Array.isArray(data.account.available_accounts)) {
          setAccounts(data.account.available_accounts);
        }
        setCurrentAccount(data.account.current_used_account);
      }
    })
    .catch(() => {});
  selectOperation("account_query");
}

function stopTimers() {
  for (const timer of state.timers) clearInterval(timer);
  state.timers = [];
}

async function refreshHealth() {
  try {
    const envelope = await api("/system/health");
    const healthy = envelope.data && envelope.data.status === "healthy";
    $("health-dot").className = `dot ${healthy ? "ok" : "bad"}`;
    $("health-text").textContent = healthy ? "运行正常" : envelope.message;
  } catch {
    $("health-dot").className = "dot bad";
    $("health-text").textContent = "状态未知";
  }
}

async function refreshQueueStats() {
  try {
    const envelope = await api("/queue/stats");
    const stats = envelope.data;
    $("queue-stats").textContent =
      `排队 ${stats.queued_count ?? 0} · 执行 ${stats.running_count ?? 0} · 累计 ${stats.total_processed ?? 0}`;
  } catch {
    /* 轮询失败不打扰，下一轮恢复 */
  }
}

/* ============ 侧边栏 ============ */

/* 展示分组（纯前端呈现层约定，未列出的操作归入"其他"） */
const OP_GROUPS = [
  ["交易", ["buy", "sell", "market_buy", "market_sell", "order_cancel"]],
  ["条件单", ["condition_buy", "condition_sell", "stop_loss_profit", "condition_order_query", "condition_order_cancel"]],
  ["查询", ["funds_query", "holding_query", "order_query", "historical_commission_query"]],
  ["国债逆回购", ["reverse_repo_buy", "reverse_repo_query"]],
  ["账户", ["account_query", "account_switch"]],
];

function renderSidebar() {
  const sidebar = $("sidebar");
  sidebar.textContent = "";
  const grouped = new Set(OP_GROUPS.flatMap(([, names]) => names));
  for (const [title, names] of OP_GROUPS) {
    sidebar.append(el("div", { class: "group-title", text: title }));
    for (const name of names) {
      if (state.operations[name]) sidebar.append(opButton(name));
    }
  }
  const others = Object.keys(state.operations).filter((name) => !grouped.has(name));
  if (others.length) {
    sidebar.append(el("div", { class: "group-title", text: "其他" }));
    for (const name of others) sidebar.append(opButton(name));
  }
}

function opButton(name) {
  const op = state.operations[name];
  return el(
    "button",
    {
      class: "op-item",
      type: "button",
      "data-op": name,
      text: op.description || name,
      title: name,
      onclick: () => selectOperation(name),
    }
  );
}

/* ============ 动态表单（JSON Schema 驱动） ============ */

function selectOperation(name) {
  const op = state.operations[name];
  if (!op) return;
  state.activeOp = name;
  for (const node of document.querySelectorAll("#sidebar .op-item[data-op]")) {
    node.classList.toggle("active", node.dataset.op === name);
  }
  $("op-title").textContent = op.description || name;
  $("op-tag").textContent = name;
  $("op-tag").classList.remove("hidden");
  $("op-desc").textContent =
    `操作名 ${name} · ` +
    (Object.keys(schemaProperties(op).properties).length
      ? "参数提交后进入队列串行执行，结果在下方展示"
      : "无参数操作，点击执行即可");
  buildForm(op);
  renderCancelState();
}

function schemaProperties(op) {
  const schema = op.parameters || {};
  return { properties: schema.properties || {}, required: schema.required || [] };
}

/* anyOf 可空字段取非 null 分支作为约束来源 */
function resolveProp(prop) {
  if (Array.isArray(prop.anyOf)) {
    const sub = prop.anyOf.find((branch) => branch.type !== "null") || prop.anyOf[0] || {};
    return { schema: sub, nullable: true, default: prop.default };
  }
  return { schema: prop, nullable: false, default: prop.default };
}

function buildForm(op) {
  const form = $("op-form");
  form.textContent = "";
  const { properties, required } = schemaProperties(op);

  for (const [name, prop] of Object.entries(properties)) {
    form.append(fieldFor(name, prop, required.includes(name)));
  }
  if (op.supports_account_directive) {
    form.append(accountDirectiveField());
  }
  form.append(priorityField());

  if (!form.children.length) {
    form.append(el("p", { class: "muted", text: "该操作无参数" }));
  }
}

function fieldFor(name, prop, isRequired) {
  const { schema, nullable, default: defaultValue } = resolveProp(prop);
  const field = el("label", { class: "field" });
  field.append(el("span", { text: `${name}${isRequired ? " *" : ""}` }));

  let input;
  if (Array.isArray(schema.enum)) {
    input = el("select", { "data-name": name, "data-type": schema.type || "string" });
    if (!isRequired && defaultValue === undefined) {
      input.append(el("option", { value: "", text: "（不指定）" }));
    }
    for (const option of schema.enum) {
      const optionNode = el("option", { value: String(option), text: fmt(option) });
      if (defaultValue !== undefined && option === defaultValue) {
        optionNode.selected = true;
      }
      input.append(optionNode);
    }
    if (isRequired && defaultValue === undefined) {
      input.prepend(el("option", { value: "", text: "请选择", selected: "" }));
      input.required = true;
    }
  } else if (schema.type === "integer" || schema.type === "number") {
    const exclusiveMin = schema.exclusiveMinimum;
    input = el("input", {
      type: "number",
      "data-name": name,
      "data-type": schema.type,
      step: schema.type === "integer" ? "1" : "any",
      min: exclusiveMin !== undefined && schema.type === "integer"
        ? String(exclusiveMin + 1)
        : schema.minimum ?? exclusiveMin,
      max: schema.exclusiveMaximum !== undefined
        ? String(schema.exclusiveMaximum - 1)
        : schema.maximum,
      required: isRequired && !nullable ? "required" : undefined,
    });
    if (defaultValue !== undefined) input.value = String(defaultValue);
  } else if (name === "account_name") {
    /* account_switch 的切换目标取值是已知账户集合，用下拉替代自由文本 */
    input = el("select", { "data-name": name, "data-account": "target" });
    fillAccountOptions(input);
  } else {
    input = el("input", {
      type: "text",
      "data-name": name,
      "data-type": "string",
      placeholder: nullable ? "（可选）" : "",
      pattern: schema.pattern || undefined,
      required: isRequired && !nullable ? "required" : undefined,
    });
  }
  field.append(input, el("span", { class: "hint", text: prop.description || "" }));
  return field;
}

function accountDirectiveField() {
  const field = el("label", { class: "field" });
  field.append(el("span", { text: "account_name（指令）" }));
  const select = el("select", {
    "data-name": "account_name",
    "data-account": "directive",
  });
  fillAccountOptions(select);
  field.append(select, el("span", { class: "hint", text: "执行前先切换到该账户" }));
  return field;
}

function priorityField() {
  const field = el("label", { class: "field" });
  field.append(el("span", { text: "priority" }));
  field.append(
    el("input", {
      type: "number",
      "data-name": "priority",
      "data-extra": "",
      min: "0",
      max: "10",
      step: "1",
      value: "0",
    }),
    el("span", { class: "hint", text: "优先级，越大越先执行（0-10）" })
  );
  return field;
}

/* ============ 账户下拉 ============ */

/* 唯一数据源 state.accounts：构建表单时直接填充（select 可以尚未挂载），
 * 缓存或当前账户变化时对表单内已挂载的下拉整体刷新 */
function setAccounts(accounts) {
  state.accounts = accounts;
  renderAccountSelects();
}

function setCurrentAccount(name) {
  if (!name) return;
  if (name !== state.currentAccount) {
    state.currentAccount = name;
    renderAccountSelects();
  }
  $("current-account").textContent = name;
}

function renderAccountSelects() {
  for (const select of $("op-form").querySelectorAll("select[data-account]")) {
    fillAccountOptions(select);
  }
}

function fillAccountOptions(select) {
  const previous = select.value;
  const isDirective = select.dataset.account === "directive";
  select.textContent = "";
  if (!state.accounts.length) {
    select.append(
      el("option", {
        value: "",
        text: isDirective
          ? "账户列表为空（保留当前账户）"
          : "账户列表为空，请先执行「账户查询」",
      })
    );
  } else {
    select.append(
      el("option", {
        value: "",
        text: isDirective ? "当前账户（不切换）" : "请选择账户",
      })
    );
    for (const { account_name } of state.accounts) {
      select.append(
        el("option", {
          value: account_name,
          text:
            account_name === state.currentAccount
              ? `${account_name}（当前）`
              : account_name,
        })
      );
    }
  }
  select.required = !isDirective;
  /* 恢复刷新前的选择，不打断填写中的表单；已不存在的选择回退空值 */
  select.value = previous;
  if (select.selectedIndex === -1) select.value = "";
}

/* ============ 提交与结果跟踪 ============ */

async function submitOperation(event) {
  event.preventDefault();
  const name = state.activeOp;
  const op = state.operations[name];
  if (!name || !op) return;

  const payload = collectPayload(op);
  const submitBtn = $("submit-btn");
  submitBtn.disabled = true;
  try {
    const envelope = await api(`/operations/${name}`, { method: "POST", body: payload });
    if (envelope.data && envelope.data.operation_id) {
      toast(`已受理，排队位置 ${envelope.data.queue_position}`);
      trackOperation(envelope.data.operation_id, name);
    }
  } catch (error) {
    if (error.message !== "unauthorized") toast(error.message, true);
  } finally {
    submitBtn.disabled = false;
  }
}

function collectPayload(op) {
  const payload = {};
  for (const input of $("op-form").querySelectorAll("[data-name]")) {
    const raw = input.value.trim();
    if (raw === "") continue; /* 空值省略：服务端按默认值/可选处理 */
    const type = input.dataset.type;
    if (type === "integer" || type === "number") {
      payload[input.dataset.name] = Number(raw);
    } else {
      payload[input.dataset.name] = raw;
    }
  }
  return payload;
}

function trackOperation(operationId, name) {
  const entry = {
    id: operationId,
    name,
    status: "queued",
    time: new Date().toTimeString().slice(0, 8),
    envelope: null,
  };
  state.recent.unshift(entry);
  state.recent = state.recent.slice(0, 20);
  state.focusId = operationId;
  renderRecent();
  pollResult(entry);
}

async function pollResult(entry) {
  for (;;) {
    let result;
    try {
      result = await rawApi(`/operations/${entry.id}/result?timeout=${RESULT_POLL_TIMEOUT}`);
    } catch {
      entry.status = "unknown";
      updateEntry(entry, null);
      await sleep(3000);
      continue;
    }
    if (result.status === 401) {
      handleAuthLost();
      return;
    }
    if (result.status === 404) {
      entry.status = "not_found";
      entry.envelope = result.envelope;
      updateEntry(entry, result.envelope);
      return;
    }
    if (result.status === 408) {
      entry.status = result.envelope ? result.envelope.status : entry.status;
      updateEntry(entry, result.envelope);
      continue; /* 仍在执行，继续下一轮长轮询 */
    }
    entry.status = result.envelope ? result.envelope.status : entry.status;
    entry.envelope = result.envelope;
    updateEntry(entry, result.envelope);
    return;
  }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function updateEntry(entry, envelope) {
  renderRecent();
  if (entry.id === state.focusId) {
    renderResult(entry, envelope);
    renderCancelState();
  }
}

async function cancelFocused() {
  const entry = state.recent.find((item) => item.id === state.focusId);
  if (!entry) return;
  try {
    await api(`/operations/${entry.id}`, { method: "DELETE" });
    toast("已发送取消请求");
  } catch (error) {
    if (error.message !== "unauthorized") toast(error.message, true);
  }
}

function renderCancelState() {
  const entry = state.recent.find((item) => item.id === state.focusId);
  const cancellable = entry && (entry.status === "queued" || entry.status === "running");
  $("cancel-btn").classList.toggle("hidden", !cancellable);
}

/* ============ 结果渲染 ============ */

const STATUS_LABELS = {
  queued: "排队中",
  running: "执行中",
  completed: "已完成",
  failed: "已失败",
  cancelled: "已取消",
  not_found: "结果丢失",
  unknown: "状态未知",
};

function renderResult(entry, envelope) {
  const panel = $("result-panel");
  panel.classList.remove("hidden");
  const status = envelope ? envelope.status : entry.status;
  const badge = $("result-status");
  badge.textContent = STATUS_LABELS[status] || status || "…";
  badge.className = `badge ${status || ""}`;

  $("result-message").textContent = envelope ? envelope.message : "等待执行结果…";

  const chips = $("result-meta");
  chips.textContent = "";
  if (envelope) {
    if (envelope.error_code) {
      chips.append(el("span", { class: "chip error", text: `错误码 ${envelope.error_code}` }));
    }
    if (envelope.current_used_account) {
      chips.append(el("span", { class: "chip", text: `账户 ${envelope.current_used_account}` }));
    }
    chips.append(el("span", { class: "chip", text: `${entry.name} · ${entry.time}` }));
    if (envelope.timestamp) {
      chips.append(el("span", { class: "chip", text: envelope.timestamp }));
    }
  }

  /* 账户缓存与顶栏当前账户随信封更新 */
  if (envelope && envelope.data && Array.isArray(envelope.data.available_accounts)) {
    setAccounts(envelope.data.available_accounts);
  }
  if (envelope) {
    setCurrentAccount(envelope.current_used_account);
  }

  const dataNode = $("result-data");
  dataNode.textContent = "";
  if (envelope && envelope.data !== null && envelope.data !== undefined) {
    const labels = fieldLabels(state.operations[entry.name]);
    dataNode.append(renderData(envelope.data, labels));
  } else if (envelope && envelope.success === false) {
    dataNode.append(el("p", { class: "muted", text: "失败响应无业务数据" }));
  }
}

/* 从 result_schema 提取字段中文名（含 $defs 嵌套行模型），供表格表头使用 */
function fieldLabels(op) {
  const labels = {};
  if (!op || !op.result_schema) return labels;
  const walk = (schema) => {
    if (!schema || typeof schema !== "object") return;
    for (const [field, prop] of Object.entries(schema.properties || {})) {
      if (prop && prop.description && !labels[field]) {
        labels[field] = prop.description.split("（")[0];
      }
    }
    for (const def of Object.values(schema.$defs || {})) walk(def);
  };
  walk(op.result_schema);
  return labels;
}

function renderData(data, labels) {
  if (Array.isArray(data)) {
    return arrayTable(data, labels);
  }
  if (data !== null && typeof data === "object") {
    const container = el("div");
    const kvRows = [];
    for (const [key, value] of Object.entries(data)) {
      if (Array.isArray(value)) {
        container.append(el("div", { class: "data-section-title", text: labels[key] || key }));
        container.append(arrayTable(value, labels));
      } else if (value !== null && typeof value === "object") {
        container.append(el("div", { class: "data-section-title", text: labels[key] || key }));
        container.append(renderData(value, labels));
      } else {
        kvRows.push([labels[key] || key, value]);
      }
    }
    if (kvRows.length) container.append(kvTable(kvRows));
    return container;
  }
  return el("p", { text: fmt(data) });
}

function arrayTable(items, labels) {
  if (!items.length || items.some((item) => item === null || typeof item !== "object")) {
    return el("pre", { class: "json-view", text: JSON.stringify(items, null, 2) });
  }
  const headers = [...new Set(items.flatMap((item) => Object.keys(item)))];
  const table = el("table");
  const headRow = el("tr");
  for (const header of headers) {
    headRow.append(el("th", { text: labels[header] || header }));
  }
  table.append(el("thead", {}, headRow));
  const body = el("tbody");
  for (const item of items) {
    const row = el("tr");
    for (const header of headers) {
      const value = item[header];
      row.append(
        el("td", {
          class: typeof value === "number" ? "num" : "",
          text: typeof value === "boolean" ? String(value) : fmt(value),
        })
      );
    }
    body.append(row);
  }
  table.append(body);
  return table;
}

function kvTable(rows) {
  const table = el("table", { class: "kv-table" });
  const body = el("tbody");
  for (const [key, value] of rows) {
    body.append(
      el(
        "tr",
        {},
        el("td", { text: key }),
        el("td", { class: typeof value === "number" ? "num" : "", text: fmt(value) })
      )
    );
  }
  table.append(body);
  return table;
}

/* ============ 最近操作列表 ============ */

function renderRecent() {
  const list = $("recent-list");
  list.textContent = "";
  if (!state.recent.length) {
    list.append(el("li", { class: "muted", text: "暂无记录" }));
    return;
  }
  for (const entry of state.recent) {
    list.append(
      el(
        "li",
        {
          onclick: () => focusEntry(entry),
        },
        el("span", { class: "time", text: entry.time }),
        el("span", { class: "flex-fill", text: entry.name }),
        el("span", {
          class: `badge ${entry.status || ""}`,
          text: STATUS_LABELS[entry.status] || entry.status || "…",
        })
      )
    );
  }
}

function focusEntry(entry) {
  state.focusId = entry.id;
  renderResult(entry, entry.envelope);
  renderCancelState();
  if (!entry.envelope || !isTerminal(entry.status)) {
    api(`/operations/${entry.id}/status`)
      .then((envelope) => {
        entry.status = envelope.status;
        if (!entry.envelope || isTerminal(envelope.status)) entry.envelope = envelope;
        updateEntry(entry, entry.envelope);
      })
      .catch(() => {});
  }
}

function isTerminal(status) {
  return status === "completed" || status === "failed" || status === "cancelled";
}

/* ============ 事件绑定与启动 ============ */

$("login-form").addEventListener("submit", handleLogin);
$("op-form").addEventListener("submit", submitOperation);
$("cancel-btn").addEventListener("click", cancelFocused);
$("logout-btn").addEventListener("click", () => {
  localStorage.removeItem(KEY_STORAGE);
  location.reload();
});

init();
