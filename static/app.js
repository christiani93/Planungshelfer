"use strict";

const $ = (id) => document.getElementById(id);

async function api(url, opts) {
  const res = await fetch(url, opts);
  return res.json();
}

function priBadge(p) {
  const map = { 1: ["p1", "klein"], 2: ["p2", "normal"], 3: ["p3", "wichtig"] };
  const [cls, label] = map[p] || map[2];
  return `<span class="badge ${cls}">${label}</span>`;
}

function fmtDue(d, overdue) {
  if (!d) return "";
  const cls = overdue ? "due late" : "due";
  return `<span class="${cls}">📅 ${d}</span>`;
}

function taskRow(t, inToday) {
  const meta = [];
  meta.push(priBadge(t.priority));
  if (t.est_min) meta.push(`<span>⏱ ${t.est_min} Min.</span>`);
  if (t.due_date) meta.push(fmtDue(t.due_date, t.overdue));
  if (t.source && t.source !== "manuell") meta.push(`<span>📥 ${escapeHtml(t.source)}</span>`);
  const done = t.status === "done";
  const toggleLabel = inToday ? "→ Backlog" : "→ Heute";
  const toggleTo = inToday ? 0 : 1;
  const actions = done
    ? `<button class="iconbtn del" data-del="${t.id}" title="Loeschen">🗑</button>`
    : `<button class="iconbtn" data-toggle="${t.id}" data-to="${toggleTo}">${toggleLabel}</button>
       <button class="iconbtn" data-remind="${t.id}" title="Erinnerung setzen">🔔</button>
       <button class="iconbtn del" data-del="${t.id}" title="Loeschen">🗑</button>`;
  return `
    <li class="task ${done ? "done" : ""} ${t.overdue ? "overdue" : ""}">
      <div class="check" data-done="${t.id}">✓</div>
      <div class="task-main">
        <div class="task-title">${escapeHtml(t.title)}</div>
        <div class="task-meta">${meta.join("")}</div>
      </div>
      <div class="task-actions">${actions}</div>
    </li>`;
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

async function load() {
  const s = await api("/api/state");
  // stats
  $("level").textContent = s.stats.level;
  $("streak").textContent = s.stats.streak;
  const pct = Math.round((s.stats.xp_in_level / s.stats.xp_per_level) * 100);
  $("xpfill").style.width = pct + "%";
  $("xptext").textContent = `${s.stats.xp_in_level} / ${s.stats.xp_per_level} XP`;
  $("todayCount").textContent = `${s.stats.done_today} / ${s.stats.today_total}`;

  // focus hint
  const openToday = s.today.filter((t) => t.status === "open").length;
  let hint = "";
  if (s.today.length === 0) hint = "Noch nichts fuer heute geplant — hol dir 1-3 Aufgaben aus dem Backlog. 👇";
  else if (openToday === 0) hint = "Alles fuer heute erledigt — stark! 🎉";
  else if (openToday > 5) hint = "Ganz schoen viel fuer heute. Weniger ist oft mehr — der Rest laeuft nicht weg.";
  $("focusHint").textContent = hint;

  // lists
  $("todayList").innerHTML = s.today.length
    ? s.today.map((t) => taskRow(t, true)).join("")
    : `<li class="empty">Leer. Plane deinen Tag mit ein paar Aufgaben.</li>`;
  $("backlogList").innerHTML = s.backlog.length
    ? s.backlog.map((t) => taskRow(t, false)).join("")
    : `<li class="empty">Backlog ist leer. 🌱</li>`;
  $("backlogCount").textContent = s.backlog.length ? `(${s.backlog.length})` : "";

  // Titel-Lookup fuer den 🔔-Button (vermeidet Attribut-Escaping).
  taskTitles = {};
  [...s.today, ...s.backlog].forEach((t) => { taskTitles[t.id] = t.title; });

  bindRows();
  loadReminders();
}

let taskTitles = {};

function renderPending(pending) {
  const box = $("pendingBox");
  if (!box) return;
  if (!pending.length) { box.innerHTML = ""; return; }
  box.innerHTML = pending
    .map(
      (rem) => `
    <div class="pending" data-pid="${rem.id}">
      <div class="pending-q">✅ ${escapeHtml(rem.message)}</div>
      <div class="pending-actions">
        <button class="add" data-confirm="${rem.id}">Ja</button>
        <button class="iconbtn" data-decline="${rem.id}">Nein</button>
      </div>
    </div>`
    )
    .join("");
  box.querySelectorAll("[data-confirm]").forEach((el) =>
    el.addEventListener("click", async () => {
      const res = await api(`/api/reminders/${el.dataset.confirm}/confirm`, { method: "POST" });
      toast(res.created ? "Erledigt — Folge-Erinnerung gesetzt. 👍" : "Notiert. 👍");
      loadReminders();
    })
  );
  box.querySelectorAll("[data-decline]").forEach((el) =>
    el.addEventListener("click", async () => {
      await api(`/api/reminders/${el.dataset.decline}/decline`, { method: "POST" });
      loadReminders();
    })
  );
}

function fmtRemAt(iso) {
  // 'YYYY-MM-DDTHH:MM' -> 'DD.MM. HH:MM'
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso || "");
  return m ? `${m[3]}.${m[2]}. ${m[4]}:${m[5]}` : iso;
}

async function loadReminders() {
  const r = await api("/api/reminders");
  const all = r.reminders || [];
  renderPending(all.filter((rem) => rem.pending));
  const active = all.filter((rem) => rem.active);
  const list = $("reminderList");
  if (!active.length) {
    list.innerHTML = `<li class="empty">Keine Erinnerungen gesetzt.</li>`;
    return;
  }
  list.innerHTML = active
    .map((rem) => {
      const badges = [];
      if (rem.recur === "weekly") badges.push(`<span class="badge p2">woechentlich</span>`);
      if (rem.kind === "confirm") badges.push(`<span class="badge p3">Ja/Nein</span>`);
      return `<li class="task">
        <div class="task-main">
          <div class="task-title">🔔 ${escapeHtml(rem.message)}</div>
          <div class="task-meta"><span class="due">📅 ${fmtRemAt(rem.remind_at)}</span> ${badges.join(" ")}</div>
        </div>
        <div class="task-actions">
          <button class="iconbtn del" data-remdel="${rem.id}" title="Erinnerung loeschen">🗑</button>
        </div>
      </li>`;
    })
    .join("");
  list.querySelectorAll("[data-remdel]").forEach((el) =>
    el.addEventListener("click", async () => {
      await api(`/api/reminders/${el.dataset.remdel}`, { method: "DELETE" });
      loadReminders();
    })
  );
}

function bindRows() {
  document.querySelectorAll("[data-done]").forEach((el) =>
    el.addEventListener("click", () => complete(el.dataset.done, el))
  );
  document.querySelectorAll("[data-toggle]").forEach((el) =>
    el.addEventListener("click", () => toggleToday(el.dataset.toggle, el.dataset.to))
  );
  document.querySelectorAll("[data-del]").forEach((el) =>
    el.addEventListener("click", () => del(el.dataset.del))
  );
  document.querySelectorAll("[data-remind]").forEach((el) =>
    el.addEventListener("click", () => prefillReminder(el.dataset.remind))
  );
}

function prefillReminder(taskId) {
  $("remTaskId").value = taskId;
  $("remMessage").value = taskTitles[taskId] || "";
  $("reminderCard").scrollIntoView({ behavior: "smooth", block: "center" });
  $("remAt").focus();
}

async function complete(id, el) {
  const r = await api(`/api/tasks/${id}/done`, { method: "POST" });
  if (r.ok && r.points) {
    burstConfetti(el);
    toast(`${r.message}  +${r.points} XP`);
  }
  await load();
}

async function toggleToday(id, to) {
  await api(`/api/tasks/${id}/today`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_today: Number(to) === 1 }),
  });
  await load();
}

async function del(id) {
  await api(`/api/tasks/${id}`, { method: "DELETE" });
  await load();
}

$("addForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    title: $("title").value,
    priority: $("priority").value,
    est_min: $("est_min").value,
    due_date: $("due_date").value,
    is_today: $("is_today").checked,
  };
  const r = await api("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (r.ok) {
    $("addForm").reset();
    $("is_today").checked = true;
    $("title").focus();
    await load();
  }
});

$("oneThingBtn").addEventListener("click", async () => {
  const r = await api("/api/one-thing");
  const box = $("oneThingBox");
  if (!r.task) {
    box.innerHTML = "Keine offenen Aufgaben — geniess die Pause. ☕";
  } else {
    const t = r.task;
    const min = t.est_min ? ` (ca. ${t.est_min} Min.)` : "";
    box.innerHTML = `Fang mit dieser einen Sache an:<br><b>${escapeHtml(t.title)}</b>${min}
      <br><button class="iconbtn" style="margin-top:8px" data-done="${t.id}">✓ Erledigt</button>`;
    box.querySelector("[data-done]").addEventListener("click", (e) =>
      complete(t.id, e.target)
    );
  }
  box.classList.remove("hidden");
});

// ------------------------------------------------------------ toast + confetti
let toastTimer;
function toast(msg) {
  let el = document.querySelector(".toast");
  if (!el) {
    el = document.createElement("div");
    el.className = "toast";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2500);
}

const cv = $("confetti");
const ctx = cv.getContext("2d");
let parts = [];
function resize() {
  cv.width = window.innerWidth;
  cv.height = window.innerHeight;
}
window.addEventListener("resize", resize);
resize();

function burstConfetti(anchor) {
  const rect = anchor.getBoundingClientRect();
  const x = rect.left + rect.width / 2;
  const y = rect.top + rect.height / 2;
  const colors = ["#22c55e", "#fbbf24", "#38bdf8", "#f87171", "#a78bfa"];
  for (let i = 0; i < 60; i++) {
    parts.push({
      x, y,
      vx: (Math.random() - 0.5) * 9,
      vy: Math.random() * -9 - 3,
      g: 0.3 + Math.random() * 0.2,
      size: 4 + Math.random() * 5,
      color: colors[(i + Math.floor(x)) % colors.length],
      life: 60 + Math.random() * 30,
    });
  }
  if (parts.length) requestAnimationFrame(animate);
}

function animate() {
  ctx.clearRect(0, 0, cv.width, cv.height);
  parts = parts.filter((p) => p.life > 0);
  for (const p of parts) {
    p.vy += p.g;
    p.x += p.vx;
    p.y += p.vy;
    p.life--;
    ctx.fillStyle = p.color;
    ctx.fillRect(p.x, p.y, p.size, p.size);
  }
  if (parts.length) requestAnimationFrame(animate);
  else ctx.clearRect(0, 0, cv.width, cv.height);
}

// ------------------------------------------------------------ Web-Push
function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

async function refreshNotifState() {
  const btn = $("notifBtn");
  const hint = $("notifHint");
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    btn.style.display = "none";
    hint.textContent = "Dieses Geraet/Browser unterstuetzt keine Push-Benachrichtigungen.";
    return;
  }
  if (Notification.permission === "denied") {
    btn.textContent = "Blockiert";
    btn.disabled = true;
    hint.textContent = "Benachrichtigungen sind im Browser blockiert — in den Seiten-Einstellungen erlauben.";
    return;
  }
  const reg = await navigator.serviceWorker.getRegistration();
  const sub = reg && (await reg.pushManager.getSubscription());
  if (sub && Notification.permission === "granted") {
    btn.textContent = "Test senden";
    btn.dataset.mode = "test";
    hint.textContent = "Benachrichtigungen sind auf diesem Geraet aktiv. 🔔";
  } else {
    btn.textContent = "Aktivieren";
    btn.dataset.mode = "enable";
  }
}

async function enableNotifications() {
  try {
    const perm = await Notification.requestPermission();
    if (perm !== "granted") { toast("Benachrichtigungen nicht erlaubt."); return refreshNotifState(); }
    const cfg = await api("/api/push/config");
    if (!cfg.enabled || !cfg.key) { toast("Server: Push nicht konfiguriert."); return; }
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(cfg.key),
    });
    const json = sub.toJSON();
    const r = await api("/api/push/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint: sub.endpoint, keys: json.keys }),
    });
    if (r.ok) { toast("Benachrichtigungen aktiviert. 🔔"); }
    await refreshNotifState();
  } catch (e) {
    toast("Konnte Benachrichtigungen nicht aktivieren.");
  }
}

$("notifBtn").addEventListener("click", async () => {
  if ($("notifBtn").dataset.mode === "test") {
    const r = await api("/api/push/test", { method: "POST" });
    toast(r.sent ? `Test an ${r.sent} Geraet(e) gesendet.` : "Kein Geraet erreicht.");
  } else {
    await enableNotifications();
  }
});

// Folge-Erinnerung nur bei "mit Ja/Nein" anbieten
$("remConfirm").addEventListener("change", () => {
  $("followupBox").classList.toggle("hidden", !$("remConfirm").checked);
});

$("reminderForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    message: $("remMessage").value,
    remind_at: $("remAt").value,
    recur: $("remWeekly").checked ? "weekly" : "none",
    kind: $("remConfirm").checked ? "confirm" : "info",
    task_id: $("remTaskId").value || null,
  };
  if ($("remConfirm").checked && $("remFollowMsg").value.trim()) {
    const [h, m] = ($("remFollowTime").value || "06:00").split(":");
    body.followup = {
      message: $("remFollowMsg").value.trim(),
      weekday: Number($("remFollowWeekday").value),
      hour: Number(h),
      minute: Number(m),
    };
  }
  const r = await api("/api/reminders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (r.ok) {
    $("reminderForm").reset();
    $("remTaskId").value = "";
    $("followupBox").classList.add("hidden");
    toast("Erinnerung gespeichert.");
    loadReminders();
  } else {
    toast(r.error || "Fehler beim Speichern.");
  }
});

refreshNotifState();
load();
