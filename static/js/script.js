/* SpamGuard AI - front-end logic. Talks to the Flask REST API; all user text is inserted with textContent. */
(function () {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);

  async function api(path, options = {}) {
    const headers = { "X-Requested-With": "XMLHttpRequest" };
    let body = options.body;
    if (body !== undefined && !(body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(body);
    }
    const res = await fetch(path, {
      method: options.method || "GET", headers, body, credentials: "same-origin",
    });
    let data = null;
    try { data = await res.json(); } catch (e) { /* non-JSON response */ }
    if (!res.ok) {
      const err = new Error((data && data.error) || "Request failed (" + res.status + ")");
      err.status = res.status;
      throw err;
    }
    return data;
  }

  function showAlert(message, type) {
    const box = $("#formAlert");
    if (!box) return;
    box.textContent = "";
    if (!message) return;
    const div = document.createElement("div");
    div.className = "alert alert-" + (type || "danger") + " py-2 mb-0";
    div.setAttribute("role", "alert");
    div.textContent = message;
    box.appendChild(div);
  }

  function setBusy(button, busy) {
    button.disabled = busy;
    const spinner = $(".spinner-border", button);
    if (spinner) spinner.classList.toggle("d-none", !busy);
  }

  function fmtDate(iso) { return iso ? new Date(iso).toLocaleString() : ""; }
  function pct(n) { return (Math.round(n * 100) / 100).toFixed(2).replace(/\.?0+$/, "") + "%"; }

  function badge(prediction) {
    const span = document.createElement("span");
    const spam = prediction === "spam";
    span.className = "badge rounded-pill " + (spam ? "badge-spam" : "badge-ham");
    span.textContent = spam ? "SPAM" : "NOT SPAM";
    return span;
  }

  function cell(content, className) {
    const td = document.createElement("td");
    if (className) td.className = className;
    if (content instanceof Node) td.appendChild(content); else td.textContent = content;
    return td;
  }

  /* ---------- Navbar ---------- */
  const logoutBtn = $("#logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      try { await api("/api/logout", { method: "POST", body: {} }); } catch (e) { /* ignore */ }
      window.location.href = "/";
    });
  }

  /* ---------- Home ---------- */
  function initHome() {
    const textarea = $("#message");
    const detectBtn = $("#detectBtn");
    const resultCard = $("#resultCard");
    let lastMessageId = null;

    async function refreshStats() {
      try {
        const s = await api("/api/stats/summary");
        $("#statTotal").textContent = s.total.toLocaleString();
        $("#statSpam").textContent = s.spam.toLocaleString();
        $("#statHam").textContent = s.ham.toLocaleString();
      } catch (e) { /* counters are non-critical */ }
    }

    function render(r) {
      const spam = r.prediction === "spam";
      const spamPct = (r.spam_probability * 100);
      resultCard.classList.remove("d-none", "is-spam", "is-ham");
      resultCard.classList.add(spam ? "is-spam" : "is-ham");
      $("#resultIcon").className = "bi " + (spam ? "bi-exclamation-triangle-fill" : "bi-check-circle-fill");
      $("#resultTitle").textContent = r.label;
      $("#resultConfidence").textContent = pct(r.confidence_percent);
      // Big spam percentage display
      const bigEl = $("#spamPctBig");
      bigEl.textContent = pct(spamPct);
      bigEl.className = "sg-pct-big " + (spam ? "sg-pct-spam" : "sg-pct-ham");
      // Probability bar labels
      $("#spamPct").textContent = pct(spamPct);
      $("#hamPct").textContent = pct(r.ham_probability * 100);
      $("#spamBar").style.width = (r.spam_probability * 100) + "%";
      $("#hamBar").style.width = (r.ham_probability * 100) + "%";
      $("#resultAdvice").textContent = r.recommendation;
      $("#resultDisclaimer").textContent = r.disclaimer;
      $("#feedbackThanks").textContent = "";
      document.querySelectorAll("[data-feedback]").forEach((b) => { b.disabled = false; });
      resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    async function detect() {
      showAlert("");
      const text = textarea.value.trim();
      if (!text) { showAlert("Please enter a message first.", "warning"); textarea.focus(); return; }
      setBusy(detectBtn, true);
      try {
        const r = await api("/api/predict", { method: "POST", body: { message: text } });
        lastMessageId = r.id;
        render(r);
        refreshStats();
      } catch (e) {
        showAlert(e.message);
      } finally {
        setBusy(detectBtn, false);
      }
    }

    detectBtn.addEventListener("click", detect);
    textarea.addEventListener("keydown", (e) => { if (e.ctrlKey && e.key === "Enter") detect(); });
    textarea.addEventListener("input", () => { $("#charCount").textContent = textarea.value.length; });
    $("#clearBtn").addEventListener("click", () => {
      textarea.value = "";
      $("#charCount").textContent = "0";
      resultCard.classList.add("d-none");
      showAlert("");
      textarea.focus();
    });
    document.querySelectorAll(".example").forEach((btn) => {
      btn.addEventListener("click", () => {
        textarea.value = btn.dataset.text;
        $("#charCount").textContent = textarea.value.length;
        showAlert("");
        textarea.focus();
      });
    });
    document.querySelectorAll("[data-feedback]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!lastMessageId) return;
        try {
          await api("/api/feedback", { method: "POST",
            body: { message_id: lastMessageId, user_feedback: btn.dataset.feedback } });
          document.querySelectorAll("[data-feedback]").forEach((b) => { b.disabled = true; });
          $("#feedbackThanks").textContent = "Thanks for your feedback!";
        } catch (e) { $("#feedbackThanks").textContent = e.message; }
      });
    });
    refreshStats();
  }

  /* ---------- Auth forms ---------- */
  function safeNext() {
    const next = new URLSearchParams(window.location.search).get("next");
    return next && next.startsWith("/") && !next.startsWith("//") ? next : null;
  }

  function initLogin() {
    $("#loginForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      showAlert("");
      const btn = $("button[type=submit]", e.target);
      setBusy(btn, true);
      try {
        const r = await api("/api/login", { method: "POST",
          body: { email: $("#email").value, password: $("#password").value } });
        window.location.href = safeNext() || (r.user.role === "admin" ? "/dashboard" : "/");
      } catch (err) { showAlert(err.message); setBusy(btn, false); }
    });
  }

  function initRegister() {
    $("#registerForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      showAlert("");
      if ($("#password").value !== $("#confirm").value) { showAlert("Passwords do not match."); return; }
      const btn = $("button[type=submit]", e.target);
      setBusy(btn, true);
      try {
        await api("/api/register", { method: "POST",
          body: { name: $("#name").value, email: $("#email").value, password: $("#password").value } });
        window.location.href = "/";
      } catch (err) { showAlert(err.message); setBusy(btn, false); }
    });
  }

  /* ---------- History ---------- */
  function initHistory() {
    if (!$("#historyBody")) return; // not logged in
    const state = { page: 1, q: "", filter: "all" };
    let timer = null;

    function renderPagination(pages) {
      const ul = $("#pagination");
      ul.textContent = "";
      if (pages <= 1) return;
      const add = (label, page, disabled, active) => {
        const li = document.createElement("li");
        li.className = "page-item" + (disabled ? " disabled" : "") + (active ? " active" : "");
        const a = document.createElement("button");
        a.type = "button";
        a.className = "page-link";
        a.textContent = label;
        a.addEventListener("click", () => { state.page = page; load(); });
        li.appendChild(a);
        ul.appendChild(li);
      };
      add("Prev", state.page - 1, state.page === 1);
      const start = Math.max(1, state.page - 2), end = Math.min(pages, state.page + 2);
      for (let p = start; p <= end; p++) add(String(p), p, false, p === state.page);
      add("Next", state.page + 1, state.page === pages);
    }

    async function load() {
      showAlert("");
      const params = new URLSearchParams({ page: state.page, per_page: 10, filter: state.filter });
      if (state.q) params.set("q", state.q);
      try {
        const d = await api("/api/history?" + params.toString());
        if (d.pages > 0 && state.page > d.pages) { state.page = d.pages; return load(); }
        const body = $("#historyBody");
        body.textContent = "";
        d.items.forEach((m) => {
          const tr = document.createElement("tr");
          tr.appendChild(cell(m.message_text, "msg"));
          tr.appendChild(cell(badge(m.prediction)));
          tr.appendChild(cell(pct(m.confidence_percent)));
          tr.appendChild(cell(fmtDate(m.created_at), "text-nowrap"));
          const del = document.createElement("button");
          del.type = "button";
          del.className = "btn btn-sm btn-outline-danger";
          del.setAttribute("aria-label", "Delete record");
          del.innerHTML = '<i class="bi bi-trash"></i>';
          del.addEventListener("click", async () => {
            if (!window.confirm("Delete this record?")) return;
            try { await api("/api/history/" + m.id, { method: "DELETE" }); load(); }
            catch (err) { showAlert(err.message); }
          });
          tr.appendChild(cell(del, "text-end"));
          body.appendChild(tr);
        });
        $("#emptyState").classList.toggle("d-none", d.items.length > 0);
        $("#historyInfo").textContent = d.total + " record" + (d.total === 1 ? "" : "s") +
          (d.pages > 1 ? " · page " + d.page + " of " + d.pages : "");
        renderPagination(d.pages);
      } catch (err) {
        if (err.status === 401) { window.location.href = "/login?next=/history"; return; }
        showAlert(err.message);
      }
    }

    $("#searchInput").addEventListener("input", (e) => {
      clearTimeout(timer);
      timer = setTimeout(() => { state.q = e.target.value.trim(); state.page = 1; load(); }, 300);
    });
    $("#filterSelect").addEventListener("change", (e) => { state.filter = e.target.value; state.page = 1; load(); });
    $("#resetFilters").addEventListener("click", () => {
      $("#searchInput").value = ""; $("#filterSelect").value = "all";
      state.q = ""; state.filter = "all"; state.page = 1; load();
    });
    $("#clearHistoryBtn").addEventListener("click", async () => {
      if (!window.confirm("Delete ALL of your detection history? This cannot be undone.")) return;
      try { await api("/api/history", { method: "DELETE" }); state.page = 1; load(); }
      catch (err) { showAlert(err.message); }
    });
    load();
  }

  /* ---------- Admin dashboard ---------- */
  function initDashboard() {
    if (!$("#pieChart")) return; // forbidden view
    const RED = "#dc2626", GREEN = "#16a34a";
    let pie = null, bar = null;

    function drawCharts(d) {
      if (typeof Chart === "undefined") { showAlert("Chart library failed to load.", "warning"); return; }
      if (pie) pie.destroy();
      if (bar) bar.destroy();
      pie = new Chart($("#pieChart"), {
        type: "pie",
        data: { labels: ["Spam", "Not spam"],
          datasets: [{ data: [d.total_spam, d.total_ham], backgroundColor: [RED, GREEN] }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
      });
      bar = new Chart($("#barChart"), {
        type: "bar",
        data: { labels: d.daily.map((x) => x.date.slice(5)),
          datasets: [
            { label: "Spam", data: d.daily.map((x) => x.spam), backgroundColor: RED },
            { label: "Not spam", data: d.daily.map((x) => x.ham), backgroundColor: GREEN },
          ] },
        options: { responsive: true, maintainAspectRatio: false,
          scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
          plugins: { legend: { position: "bottom" } } },
      });
    }

    async function load() {
      try {
        const d = await api("/api/dashboard/stats");
        $("#dTotal").textContent = d.total_messages.toLocaleString();
        $("#dSpam").textContent = d.total_spam.toLocaleString();
        $("#dHam").textContent = d.total_ham.toLocaleString();
        $("#dPct").textContent = pct(d.spam_percentage);
        $("#dUsers").textContent = d.total_users;
        if (d.latest_model) {
          const m = d.latest_model;
          $("#modelInfo").textContent = m.model_name + " · accuracy " + pct(m.accuracy * 100) +
            ", precision " + pct(m.precision * 100) + ", recall " + pct(m.recall * 100) +
            ", F1 " + pct(m.f1_score * 100);
        }
        const body = $("#recentBody");
        body.textContent = "";
        d.recent.forEach((m) => {
          const tr = document.createElement("tr");
          tr.appendChild(cell(m.message_text, "msg"));
          tr.appendChild(cell(badge(m.prediction)));
          tr.appendChild(cell(pct(m.confidence_percent)));
          tr.appendChild(cell(fmtDate(m.created_at), "text-nowrap"));
          body.appendChild(tr);
        });
        $("#recentEmpty").classList.toggle("d-none", d.recent.length > 0);
        drawCharts(d);
      } catch (err) {
        if (err.status === 401) { window.location.href = "/login?next=/dashboard"; return; }
        showAlert(err.message);
      }
    }

    $("#trainForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      const file = $("#trainFile").files[0];
      const out = $("#trainResult");
      out.textContent = "";
      if (!file) { out.textContent = "Choose a CSV file first."; return; }
      const btn = $("button[type=submit]", e.target);
      setBusy(btn, true);
      try {
        const fd = new FormData();
        fd.append("file", file);
        const r = await api("/api/admin/train", { method: "POST", body: fd });
        out.textContent = r.message + " Selected: " + r.selected_model + " (" + r.dataset_size + " messages).";
        load();
      } catch (err) { out.textContent = err.message; }
      finally { setBusy(btn, false); }
    });

    load();
  }

  const page = document.body.dataset.page;
  if (page === "home") initHome();
  else if (page === "login") initLogin();
  else if (page === "register") initRegister();
  else if (page === "history") initHistory();
  else if (page === "dashboard") initDashboard();
})();
