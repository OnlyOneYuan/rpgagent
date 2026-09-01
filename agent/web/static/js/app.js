/* 冒险世界 · 前端逻辑 */
"use strict";

const state = {
  token: localStorage.getItem("rpg_token") || "",
  player: null,
  meta: null,
  ws: null,
  onlinePlayers: [],
  chatLog: [],
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, html) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (html !== undefined) node.innerHTML = html;
  return node;
};

/* ==================== Toast ==================== */
let toastTimer = null;
function toast(msg, isError = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show" + (isError ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.className = "toast"), 2600);
}

/* ==================== API ==================== */
async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const resp = await fetch(path, { ...options, headers });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.detail || `请求失败 (${resp.status})`);
  }
  return data;
}

function authedApi(path, options = {}) {
  return api(path, {
    ...options,
    headers: { ...(options.headers || {}), Authorization: `Bearer ${state.token}` },
  });
}

/* ==================== 登录 / 注册 ==================== */
function switchAuthTab(tab) {
  document.querySelectorAll(".auth-tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  $("#login-form").classList.toggle("hidden", tab !== "login");
  $("#register-form").classList.toggle("hidden", tab !== "register");
  $("#auth-error").textContent = "";
}

async function loadRaces() {
  try {
    const data = await api("/api/races");
    const box = $("#race-options");
    box.innerHTML = "";
    data.races.forEach((race, i) => {
      const desc = race.talents.length
        ? race.talents.map((t) => t.name + "·" + t.description).join("，")
        : "均衡发展，无特殊天赋";
      const opt = el("div", "race-option" + (i === 0 ? " selected" : ""));
      opt.dataset.race = race.name;
      opt.innerHTML = `<div class="race-name">${race.name}</div><div class="race-desc">${desc}</div>`;
      opt.addEventListener("click", () => {
        box.querySelectorAll(".race-option").forEach((o) => o.classList.remove("selected"));
        opt.classList.add("selected");
      });
      box.appendChild(opt);
    });
  } catch (e) {
    console.warn(e);
  }
}

function enterGame(token, player) {
  state.token = token;
  state.player = player;
  localStorage.setItem("rpg_token", token);
  $("#auth-screen").classList.add("hidden");
  $("#game-screen").classList.remove("hidden");
  renderAll();
  connectWs();
}

function handleAuthError(e) {
  $("#auth-error").textContent = e.message || "操作失败";
}

async function init() {
  await loadRaces();

  document.querySelectorAll(".auth-tab").forEach((tab) =>
    tab.addEventListener("click", () => switchAuthTab(tab.dataset.tab))
  );

  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const data = await api("/api/login", {
        method: "POST",
        body: JSON.stringify({
          name: $("#login-name").value.trim(),
          password: $("#login-password").value,
        }),
      });
      enterGame(data.token, data.player);
    } catch (err) {
      handleAuthError(err);
    }
  });

  $("#register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const race = document.querySelector(".race-option.selected")?.dataset.race || "人类";
    try {
      const data = await api("/api/register", {
        method: "POST",
        body: JSON.stringify({
          name: $("#reg-name").value.trim(),
          password: $("#reg-password").value,
          race,
        }),
      });
      enterGame(data.token, data.player);
    } catch (err) {
      handleAuthError(err);
    }
  });

  // 已有会话：尝试恢复
  if (state.token) {
    try {
      const data = await authedApi("/api/player");
      state.player = data.player;
      $("#auth-screen").classList.add("hidden");
      $("#game-screen").classList.remove("hidden");
      renderAll();
      connectWs();
    } catch (e) {
      localStorage.removeItem("rpg_token");
    }
  }
}

/* ==================== 导航 ==================== */
function switchView(view) {
  document.querySelectorAll(".nav-item").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === view)
  );
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  $("#view-" + view).classList.add("active");
  if (view === "multiplayer") renderMultiplayer();
}

/* ==================== 渲染：角色属性 ==================== */
function renderCharacter() {
  const p = state.player;
  const s = p.stats;
  const view = $("#view-character");
  const paramLabels = state.meta.param_labels;
  const resLabels = state.meta.res_labels;
  const baseLabels = state.meta.base_labels;

  const totalLevels = Object.values(p.chara.param.params).reduce((a, x) => a + x.level, 0);
  const expNeed = p.level * 100;

  const head = el("div", "char-head", `
    <div class="big-avatar">🧙</div>
    <div>
      <div class="char-name">${esc(p.name)}</div>
      <div class="char-tags">
        <span class="tag race">${esc(p.chara.race.name)}</span>
        <span class="tag">Lv.${p.level}</span>
        <span class="tag">💰 ${p.gold} 金币</span>
        <span class="tag">总属性等级 ${totalLevels}</span>
      </div>
      <div class="exp-bar-wrap">
        <div class="exp-bar"><div class="exp-bar-fill" style="width:${Math.min(100, (p.exp / expNeed) * 100)}%"></div></div>
        <div class="exp-text">经验 ${p.exp} / ${expNeed}</div>
      </div>
    </div>
  `);

  // 基础属性
  const baseCard = el("div", "card stat-card", `<div class="talent-name" style="margin-bottom:8px">⚡ 基础属性</div>`);
  Object.entries(baseLabels).forEach(([key, label]) => {
    const v = s[key];
    const bonus = v.bonus ? `<span class="stat-bonus">+${v.bonus} 装备</span>` : "";
    baseCard.appendChild(el("div", "stat-row",
      `<span class="stat-name">${label}</span><span><span class="stat-value">${v.total}</span>${bonus}</span>`));
  });

  // 能力属性（可训练）
  const paramCard = el("div", "card stat-card", `<div class="talent-name" style="margin-bottom:8px">📈 能力属性</div>`);
  Object.entries(paramLabels).forEach(([key, label]) => {
    const v = s[key];
    const bonus = v.bonus ? `<span class="stat-bonus">+${v.bonus}</span>` : "";
    paramCard.appendChild(el("div", "param-row", `
      <div class="param-info">
        <div class="param-name">${label}</div>
        <div class="param-sub">Lv.${v.level} · 成长积累 ${v.base}</div>
      </div>
      <div class="param-value">${v.total}${bonus ? " " + bonus : ""}</div>
      <button class="train-btn" data-param="${key}">训练(💰10)</button>
    `));
  });
  paramCard.querySelectorAll(".train-btn").forEach((btn) =>
    btn.addEventListener("click", () => train(btn.dataset.param))
  );

  // 抗性
  const resCard = el("div", "card stat-card", `<div class="talent-name" style="margin-bottom:8px">🛡️ 元素抗性</div>`);
  const resGrid = el("div", "res-chip-list");
  Object.entries(resLabels).forEach(([key, label]) => {
    const v = s[key];
    resGrid.appendChild(el("div", "res-chip",
      `<span class="res-name">${label}</span><span class="res-val">${v.total}${v.bonus ? " +" + v.bonus : ""}</span>`));
  });
  resCard.appendChild(resGrid);

  // 天赋
  const talentCard = el("div", "card", `<div class="talent-name" style="margin-bottom:10px">✨ 天赋</div>`);
  const talentList = el("div", "talent-list");
  p.chara.talents.forEach((t) => {
    talentList.appendChild(el("div", "talent-item", `
      <div class="talent-icon">✨</div>
      <div><div class="talent-name">${esc(t.name)}</div>
      <div class="talent-desc">${esc(t.description || "无描述")}</div></div>
    `));
  });
  if (!p.chara.talents.length) talentList.appendChild(el("div", "empty-tip", "暂无天赋"));
  talentCard.appendChild(talentList);

  view.innerHTML = "";
  view.appendChild(head);
  const grid = el("div", "stat-grid");
  grid.append(baseCard, paramCard, resCard);
  view.appendChild(grid);
  view.appendChild(talentCard);
}

/* ==================== 渲染：装备 ==================== */
function renderEquipment() {
  const p = state.player;
  const view = $("#view-equipment");
  const slotOrder = ["weapon", "armor", "helmet", "boots", "necklace", "ring"];
  const slotIcons = { weapon: "🗡️", armor: "🛡️", helmet: "⛑️", boots: "👢", necklace: "📿", ring: "💍" };

  const left = el("div", "card", `<div class="section-title">装备栏</div>`);
  const slotGrid = el("div", "slot-grid");

  slotOrder.forEach((slotKey) => {
    const slotMeta = state.meta.slots[slotKey];
    const item = p.equipped[slotKey];
    const card = el("div", "slot-card" + (item ? " filled" : ""));
    if (item) {
      const color = state.meta.rarity[item.rarity].color;
      card.innerHTML = `
        <div class="slot-icon">${slotIcons[slotKey]}</div>
        <div class="slot-name">${slotMeta.label}</div>
        <div class="slot-item-name" style="color:${color}">${esc(item.name)}</div>
        <div class="slot-item-bonus">${statText(item.stats)}</div>
      `;
      const actions = el("div", "slot-actions");
      const btn = el("button", "btn btn-ghost", "卸下");
      btn.style.cssText = "font-size:12px;padding:4px 12px;";
      btn.addEventListener("click", () => unequip(slotKey));
      actions.appendChild(btn);
      card.appendChild(actions);
    } else {
      card.innerHTML = `
        <div class="slot-icon">${slotIcons[slotKey]}</div>
        <div class="slot-name">${slotMeta.label}</div>
        <div class="slot-item-name" style="color:var(--text-dim);font-weight:400">空</div>
      `;
    }
    slotGrid.appendChild(card);
  });
  left.appendChild(slotGrid);

  const right = el("div", "card", `<div class="section-title">背包 (${p.inventory.length})</div>`);
  const itemGrid = el("div", "item-grid");
  if (!p.inventory.length) {
    itemGrid.appendChild(el("div", "empty-tip", "背包空空如也"));
  }
  p.inventory.forEach((item) => {
    const color = state.meta.rarity[item.rarity].color;
    const card = el("div", "item-card", `
      <div class="item-rarity" style="background:${color}"></div>
      <div class="item-name" style="color:${color}">${esc(item.name)}</div>
      <div class="item-slot">${state.meta.slots[item.slot].label} · ${state.meta.rarity[item.rarity].label}</div>
      <div class="item-stats">${statLines(item.stats)}</div>
      ${item.require || (item.required_level > 1) ? `<div class="item-req">需求：${reqText(item.require, item.required_level)}</div>` : ""}
      ${item.description ? `<div class="item-desc">${esc(item.description)}</div>` : ""}
      <div class="item-actions"><button class="btn btn-primary equip-btn" style="width:100%;font-size:13px">装备</button></div>
    `);
    card.querySelector(".equip-btn").addEventListener("click", () => equip(item.item_id));
    itemGrid.appendChild(card);
  });
  right.appendChild(itemGrid);

  view.innerHTML = "";
  const layout = el("div", "equip-layout");
  layout.append(left, right);
  view.appendChild(layout);
}

function statText(stats) {
  return Object.entries(stats)
    .map(([k, v]) => `${labelOf(k)} +${v}`)
    .join(" · ");
}

function statLines(stats) {
  return Object.entries(stats)
    .map(([k, v]) => `<div class="item-stat">${labelOf(k)} <span class="plus">+${v}</span></div>`)
    .join("");
}

function reqText(require, requiredLevel) {
  const parts = [];
  if (requiredLevel > 1) parts.push(`等级≥${requiredLevel}`);
  Object.entries(require || {}).forEach(([k, v]) => parts.push(`${labelOf(k)}≥${v}`));
  return parts.join("，");
}

function labelOf(key) {
  const m = state.meta;
  return m.base_labels[key] || m.param_labels[key] || m.res_labels[key] || key;
}

/* ==================== 渲染：任务 ==================== */
function renderQuests() {
  const p = state.player;
  const view = $("#view-quests");
  const groups = {
    available: { title: "📜 可接取任务", items: [], badge: "status-available", label: "可接取" },
    accepted: { title: "🔥 进行中", items: [], badge: "status-accepted", label: "进行中" },
    completed: { title: "✅ 已完成", items: [], badge: "status-completed", label: "已完成" },
  };
  p.tasks.forEach((t) => {
    const g = groups[t.status];
    if (g) g.items.push(t);
  });

  view.innerHTML = "";
  const columns = el("div", "quest-columns");
  Object.values(groups).forEach((g) => {
    const col = el("div", "card", `<div class="section-title">${g.title} (${g.items.length})</div>`);
    if (!g.items.length) {
      col.appendChild(el("div", "empty-tip", "暂无任务"));
    }
    g.items.forEach((t) => {
      const card = el("div", "quest-card");
      const rewards = [];
      if (t.reward_gold) rewards.push(`💰 ${t.reward_gold} 金币`);
      if (t.reward_exp) rewards.push(`⚡ ${t.reward_exp} 经验`);
      Object.entries(t.reward_param || {}).forEach(([k, v]) => rewards.push(`${labelOf(k)} +${v}`));
      card.innerHTML = `
        <div class="quest-title">
          ${esc(t.name)}
          <span class="status-badge ${g.badge}">${g.label}</span>
        </div>
        <div class="quest-desc">${esc(t.description || "无描述")}</div>
        <div class="quest-rewards">${rewards.map((r) => `<span class="reward-chip">${r}</span>`).join("")}</div>
      `;
      const actions = el("div", "quest-actions");
      if (t.status === "available") {
        const btn = el("button", "btn btn-primary", "接受任务");
        btn.addEventListener("click", () => acceptTask(t.task_id));
        actions.appendChild(btn);
      } else if (t.status === "accepted") {
        const btn = el("button", "btn btn-gold", "完成任务");
        btn.addEventListener("click", () => completeTask(t.task_id));
        actions.appendChild(btn);
      }
      if (actions.childNodes.length) card.appendChild(actions);
      col.appendChild(card);
    });
    columns.appendChild(col);
  });
  view.appendChild(columns);
}

/* ==================== 渲染：多人 ==================== */
function renderMultiplayer() {
  const view = $("#view-multiplayer");
  view.innerHTML = "";
  const layout = el("div", "mp-layout");

  // 玩家列表
  const left = el("div", "card", `<div class="section-title">在线玩家</div>`);
  const list = el("div", "player-list");
  const all = state.onlinePlayers.slice();
  if (!all.length) {
    list.appendChild(el("div", "empty-tip", "暂无其他玩家，邀请好友来冒险吧"));
  }
  all.forEach((pl) => {
    const row = el("div", "mp-player");
    row.innerHTML = `
      <div class="mp-avatar">🧙</div>
      <div>
        <div class="mp-name">${esc(pl.name)}</div>
        <div class="mp-level">Lv.${pl.level}</div>
      </div>
      <span class="mp-status ${pl.online ? "on" : "off"}">${pl.online ? "在线" : "离线"}</span>
    `;
    if (pl.name !== state.player.name) {
      const btn = el("button", "btn btn-ghost steal-btn", "偷窃");
      btn.addEventListener("click", () => steal(pl.name));
      row.appendChild(btn);
    }
    list.appendChild(row);
  });
  left.appendChild(list);

  // 聊天
  const right = el("div", "card chat-panel", `<div class="section-title">世界频道</div>`);
  const log = el("div", "chat-log");
  log.id = "chat-log";
  state.chatLog.forEach((m) => appendChatNode(log, m));
  right.appendChild(log);
  const inputRow = el("div", "chat-input-row");
  const input = el("input", "");
  input.placeholder = "输入消息，按回车发送…";
  input.id = "chat-input";
  const sendBtn = el("button", "btn btn-primary", "发送");
  sendBtn.addEventListener("click", sendChat);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });
  inputRow.append(input, sendBtn);
  right.appendChild(inputRow);

  layout.append(left, right);
  view.appendChild(layout);
}

function appendChat(msg) {
  state.chatLog.push(msg);
  if (state.chatLog.length > 100) state.chatLog.shift();
  const log = $("#chat-log");
  if (log) appendChatNode(log, msg);
}

function appendChatNode(log, msg) {
  const node = el("div", "chat-msg" + (msg.type === "system" ? " system" : ""));
  if (msg.type === "system") {
    node.innerHTML = `<span class="time">[${msg.time}]</span>${esc(msg.msg)}`;
  } else {
    node.innerHTML = `<span class="time">[${msg.time}]</span><span class="from">${esc(msg.from)}:</span>${esc(msg.msg)}`;
  }
  log.appendChild(node);
  log.scrollTop = log.scrollHeight;
}

function sendChat() {
  const input = $("#chat-input");
  const text = input ? input.value.trim() : "";
  if (!text || !state.ws || state.ws.readyState !== WebSocket.OPEN) {
    toast("尚未连接到世界频道", true);
    return;
  }
  state.ws.send(JSON.stringify({ type: "chat", msg: text }));
  if (input) input.value = "";
}

/* ==================== WebSocket 多人联机 ==================== */
function connectWs() {
  if (!state.token) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws?token=${state.token}`);
  state.ws = ws;

  ws.onopen = () => {
    $("#online-dot").classList.add("on");
  };
  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === "online") {
      state.onlinePlayers = data.players.map((name) => ({ name, online: true }));
      if ($("#view-multiplayer").classList.contains("active")) renderMultiplayer();
      refreshOnlineBadge();
    } else if (data.type === "chat" || data.type === "system") {
      appendChat(data);
    } else if (data.type === "refresh") {
      refreshPlayer(); // 偷窃等玩家间物品变动后重新拉取数据
    }
  };
  ws.onclose = () => {
    $("#online-dot").classList.remove("on");
    setTimeout(connectWs, 3000); // 自动重连
  };
  ws.onerror = () => ws.close();
}

function refreshOnlineBadge() {
  // 简单的在线状态指示：由 ws onopen/onclose 控制
}

/* ==================== 操作 ==================== */
async function refreshPlayer() {
  const data = await authedApi("/api/player");
  state.player = data.player;
  renderAll();
}

function renderAll() {
  const active = document.querySelector(".nav-item.active")?.dataset.view || "character";
  renderCharacter();
  renderEquipment();
  renderQuests();
  if (active === "multiplayer") renderMultiplayer();
  updateSidebar();
  refreshOnlineBadge();
}

function updateSidebar() {
  const p = state.player;
  $("#mini-name").textContent = p.name;
  $("#mini-meta").textContent = `Lv.${p.level} · 💰 ${p.gold}`;
  $("#mini-avatar").textContent = "🧙";
}

async function train(param) {
  try {
    const data = await authedApi("/api/player/train", {
      method: "POST",
      body: JSON.stringify({ param_name: param }),
    });
    state.player = data.player;
    toast(data.message);
    renderAll();
  } catch (e) {
    toast(e.message, true);
  }
}

async function equip(itemId) {
  try {
    const data = await authedApi("/api/player/equip", {
      method: "POST",
      body: JSON.stringify({ item_id: itemId }),
    });
    state.player = data.player;
    toast(data.message);
    renderAll();
  } catch (e) {
    toast(e.message, true);
  }
}

async function unequip(slot) {
  try {
    const data = await authedApi("/api/player/unequip", {
      method: "POST",
      body: JSON.stringify({ slot }),
    });
    state.player = data.player;
    toast(data.message);
    renderAll();
  } catch (e) {
    toast(e.message, true);
  }
}

async function steal(target) {
  try {
    const data = await authedApi("/api/player/steal", {
      method: "POST",
      body: JSON.stringify({ target }),
    });
    state.player = data.player;
    toast(data.message);
    renderAll();
  } catch (e) {
    toast(e.message, true);
  }
}

async function acceptTask(taskId) {
  try {
    const data = await authedApi(`/api/player/tasks/${taskId}/accept`, { method: "POST" });
    state.player = data.player;
    toast(data.message);
    renderAll();
  } catch (e) {
    toast(e.message, true);
  }
}

async function completeTask(taskId) {
  try {
    const data = await authedApi(`/api/player/tasks/${taskId}/complete`, { method: "POST" });
    state.player = data.player;
    toast(data.message);
    renderAll();
  } catch (e) {
    toast(e.message, true);
  }
}

function logout() {
  if (state.ws) state.ws.close();
  localStorage.removeItem("rpg_token");
  location.reload();
}

/* ==================== 工具 ==================== */
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

/* ==================== 初始化 ==================== */
document.addEventListener("DOMContentLoaded", async () => {
  document.querySelectorAll(".nav-item").forEach((btn) =>
    btn.addEventListener("click", () => switchView(btn.dataset.view))
  );
  $("#logout-btn").addEventListener("click", logout);

  try {
    state.meta = await api("/api/meta");
  } catch (e) {
    console.warn(e);
  }

  await init();
});
