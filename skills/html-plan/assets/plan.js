(() => {
  "use strict";
  const $ = (selector) => document.querySelector(selector);
  const all = (selector) => [...document.querySelectorAll(selector)];
  const state = JSON.parse($("#html-plan-state").textContent);
  const status = $("#save-status"), connection = $("#connection-status");
  const savedReview = () => JSON.stringify(state.review);
  let persisted = savedReview(), busy = false, copying = false, retry = null;
  const pending = new Map();
  let toastTimer;
  function toast(message, error = false) {
    const el = $("#copy-toast");
    clearTimeout(toastTimer);
    el.textContent = message;
    el.classList.toggle("error", error);
    el.hidden = false;
    toastTimer = setTimeout(() => { el.hidden = true; }, 5000);
  }
  // Clone before adding user state to DOM. Export never serializes live controls/UI.
  const cleanDocument = document.documentElement.cloneNode(true);
  // Theme is page-local UI state, never review data or a stored preference.
  const themeMode = $("#theme-mode");
  themeMode.value = "system";
  themeMode.onchange = () => {
    if (themeMode.value === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = themeMode.value;
  };


  function readDecision(el) {
    if (el.dataset.kind === "checkbox") return el.checked;
    if (el.dataset.kind === "checkboxes") return [...el.querySelectorAll("input:checked")].map(input => input.value);
    if (el.dataset.kind === "radio") return el.querySelector("input:checked")?.value || "";
    return el.value;
  }
  function writeDecision(el, value) {
    if (el.dataset.kind === "checkbox") { el.checked = value === true; return; }
    if (["checkboxes", "radio"].includes(el.dataset.kind)) {
      el.querySelectorAll("input").forEach(input => {
        input.checked = el.dataset.kind === "radio" ? input.value === value : Array.isArray(value) && value.includes(input.value);
      });
      return;
    }
    el.value = value;
  }
  function collect() {
    const review = {decisions: {}, comments: {}, struck: [], edits: {}, seen: [...state.review.seen], note: $("#overall-note").value};
    all("[data-decision]").forEach(el => { review.decisions[el.dataset.decision] = readDecision(el); });
    all("[data-comment]").forEach(el => { if (el.value) review.comments[el.dataset.comment] = el.value; });
    all("[data-strike]").forEach(el => { if (el.checked) review.struck.push(el.dataset.strike); });
    all("[data-edit]").forEach(el => { review.edits[el.dataset.edit] = el.value; });
    return review;
  }
  function dirty() { return JSON.stringify(collect()) !== persisted; }
  function tell(text, error = false) {
    status.textContent = text;
    status.classList.toggle("error", error);
    status.dataset.dirty = String(!error && dirty());
  }
  function refresh() {
    all("[data-claim]").forEach(el => {
      const id = el.dataset.claim;
      el.classList.toggle("struck", Boolean(el.querySelector(`[data-strike="${id}"]`)?.checked));
      el.querySelector(".seen-badge").textContent = state.review.seen.includes(id) ? "已查看" : "待查看";
    });
    const count = all("[data-decision]").filter(el => !state.review.seen.includes(el.closest("[data-claim]").dataset.claim)).length;
    $("#review-count").textContent = count ? `${count} 个字段待查看` : "所有字段已查看";
  }
  for (const [selector, field, attribute] of [["[data-decision]", "decisions", "decision"], ["[data-comment]", "comments", "comment"], ["[data-edit]", "edits", "edit"]]) {
    all(selector).forEach(el => {
      if (Object.hasOwn(state.review[field], el.dataset[attribute])) {
        const value = state.review[field][el.dataset[attribute]];
        if (field === "decisions") writeDecision(el, value); else el.value = value;
      }
    });
  }
  all("[data-strike]").forEach(el => { el.checked = state.review.struck.includes(el.dataset.strike); });
  $("#overall-note").value = state.review.note;
  $("#history").hidden = !state.previousFeedback?.length;
  $("#history-content").textContent = JSON.stringify(state.previousFeedback || [], null, 2);
  // Defaults are part of the initial review, but are not treated as user approval.
  state.review = collect();
  persisted = savedReview();
  refresh();

  function filterTable(table) {
    const search = table.querySelector("[data-table-search]").value.trim().toLocaleLowerCase();
    const mode = table.querySelector("[data-table-filter]").value;
    const rows = [...table.querySelectorAll("[data-review-row]")];
    let visible = 0;
    rows.forEach(row => {
      const fields = [...row.querySelectorAll("[data-decision]")];
      const comment = row.querySelector("[data-comment]").value;
      const changed = Boolean(comment) || fields.some(el => JSON.stringify(readDecision(el)) !== JSON.stringify(state.decisionDefaults?.[el.dataset.decision]));
      const searchable = [row.querySelector("th").textContent, ...[...row.querySelectorAll("td")].filter(td => !td.querySelector("[data-decision], [data-comment]")).map(td => td.textContent),
        ...fields.map(el => JSON.stringify(readDecision(el))), comment].join(" ").toLocaleLowerCase();
      const match = searchable.includes(search) && (mode === "all" || (mode === "changed" ? changed : !state.review.seen.includes(row.dataset.claim)));
      row.hidden = !match;
      if (match) visible++;
    });
    table.querySelector("[data-table-count]").textContent = `${visible} / ${rows.length} 行`;
  }
  all("[data-review-table]").forEach(table => {
    for (const selector of ["[data-table-search]", "[data-table-filter]"]) {
      table.querySelector(selector).addEventListener("input", () => filterTable(table));
      table.querySelector(selector).addEventListener("change", () => filterTable(table));
    }
    // Keep an actively edited row visible until the user reapplies the filter.
    filterTable(table);
  });
  let hostNeedsUpgrade = false;
  const needsTypedDecisions = all("[data-decision]").some(el => ["checkbox", "checkboxes"].includes(el.dataset.kind));
  window.addEventListener("message", event => {
    if (event.source !== window || event.data?.channel !== "html-plan:response") return;
    const request = pending.get(event.data.requestId);
    if (!request) return;
    clearTimeout(request.timer);
    pending.delete(event.data.requestId);
    request.resolve(event.data.result);
  });
  function bridge(payload) {
    const requestId = crypto.randomUUID();
    return new Promise(resolve => {
      const timer = setTimeout(() => {
        pending.delete(requestId);
        resolve({ok: false, code: "BRIDGE_TIMEOUT", message: "未收到保存程序回复。输入已保留；可以复制反馈 JSON 回聊天，或下载 HTML。"});
      }, 15000);
      pending.set(requestId, {resolve, timer});
      window.postMessage({channel: "html-plan:request", requestId, payload}, "*");
    });
  }
  async function check() {
    $("#check").disabled = true;
    connection.textContent = "正在检查扩展与本地保存程序…";
    const result = await bridge({action: "ping"});
    hostNeedsUpgrade = result.ok && needsTypedDecisions && !result.capabilities?.includes("typed-decisions");
    connection.textContent = hostNeedsUpgrade ? "本地保存程序需升级到 0.2.0+（重新运行 setup.py install）；当前可复制反馈 JSON。" : result.ok ? `本地保存已连接 · v${result.version}` : "未连接本地保存程序，可复制反馈 JSON 并粘贴回聊天。";
    $("#copy-review").classList.toggle("copy-suggested", !result.ok || hostNeedsUpgrade);
    if (!busy && !status.classList.contains("error") && !state.savedAt) tell(dirty() ? "有未保存修改" : "可以开始审阅", false);
    else if (!busy && status.textContent === "正在检查连接…") tell("已载入保存的反馈");
    $("#check").disabled = false;
  }
  function edited(event) {
    if (event?.target?.matches?.("[data-table-search], [data-table-filter], #theme-mode")) return;
    refresh(); tell("有未保存修改");
  }
  document.addEventListener("input", edited);
  document.addEventListener("change", edited);
  // A deliberate click/focus records viewing; merely opening a document does not.
  function markSeen(event) {
    if (event.target.closest?.(".table-tools")) return;
    const claim = event.target.closest?.("[data-claim]");
    if (!claim || busy || state.review.seen.includes(claim.dataset.claim)) return;
    state.review.seen.push(claim.dataset.claim);
    refresh(); tell("有未保存修改");
  }
  document.addEventListener("click", markSeen);
  document.addEventListener("focusin", markSeen);
  $("#expand").onclick = () => all("details[data-claim]").forEach(el => { el.open = true; });
  $("#collapse").onclick = () => all("details[data-claim]").forEach(el => { el.open = false; });
  $("#expand").hidden = $("#collapse").hidden = !all("details[data-claim]").length;
  $("#next-decision").onclick = () => {
    const el = all("[data-decision]").find(el => !el.closest("[hidden]") && !state.review.seen.includes(el.closest("[data-claim]").dataset.claim));
    if (!el) return;
    let parent = el.parentElement;
    while (parent) { if (parent.tagName === "DETAILS") parent.open = true; parent = parent.parentElement; }
    el.scrollIntoView({behavior: "smooth", block: "center"}); (el.querySelector("input") || el).focus({preventScroll: true});
  };
  $("#check").onclick = check;
  $("#copy-review").onclick = async () => {
    if (busy || copying) return;
    const button = $("#copy-review");
    copying = true;
    button.disabled = true;
    try {
      const payload = {type: "html-plan-review", schemaVersion: 1, title: document.title,
        planId: state.planId, documentId: state.documentId, documentRevision: state.documentRevision,
        baseReviewRevision: state.reviewRevision, review: collect()};
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      toast("已复制反馈 JSON，请粘贴回聊天；原文件未更新。");
    } catch {
      toast("复制失败，浏览器未允许写入剪贴板。请重试或下载含反馈的 HTML。", true);
    } finally {
      copying = false;
      button.disabled = busy;
    }
  };
  $("#save").onclick = async () => {
    if (busy) return;
    if (hostNeedsUpgrade) {
      tell("保存程序版本过旧，请重新运行 setup.py install 升级；输入已保留，可复制反馈 JSON。", true);
      return;
    }
    if (!location.href.startsWith("file:")) {
      tell("此页面无法原地保存，请复制反馈 JSON 并粘贴回聊天。", true);
      $("#copy-review").classList.add("copy-suggested");
      return;
    }
    const review = collect(), signature = JSON.stringify(review);
    if (!retry || retry.signature !== signature) retry = {id: crypto.randomUUID(), signature};
    busy = true;
    const controls = all("input, textarea, select, button").filter(el => !el.disabled);
    controls.forEach(el => { el.disabled = true; });
    tell("正在保存…");
    const result = await bridge({action: "save", requestId: retry.id, planId: state.planId,
      documentId: state.documentId, documentRevision: state.documentRevision,
      expectedReviewRevision: state.reviewRevision, review});
    busy = false;
    controls.forEach(el => { el.disabled = false; });
    $("#copy-review").disabled = copying;
    if (result.ok) {
      state.review = review; state.reviewRevision = result.reviewRevision; state.savedAt = result.savedAt;
      persisted = signature; retry = null;
      tell(`已保存 · 反馈版本 ${state.reviewRevision}，可以回聊天继续`);
      connection.textContent = "反馈已写入当前 HTML 文件";
      $("#copy-review").classList.remove("copy-suggested");
    } else {
      const versions = result.code === "REVISION_CONFLICT" ? `（页面 ${result.expectedReviewRevision} / 文件 ${result.actualReviewRevision}）` : "";
      tell((result.message || "保存失败，输入已保留。") + versions + " 可复制反馈 JSON 回聊天。", true);
      $("#copy-review").classList.add("copy-suggested");
    }
  };
  $("#download").onclick = () => {
    const snapshot = structuredClone(state);
    snapshot.review = collect();
    delete snapshot.lastRequest;
    const clone = cleanDocument.cloneNode(true);
    clone.querySelector("#html-plan-state").textContent = JSON.stringify(snapshot, null, 2).replaceAll("<", "\\u003c");
    const blob = new Blob(["<!doctype html>\n", clone.outerHTML], {type: "text/html;charset=utf-8"});
    const url = URL.createObjectURL(blob), link = document.createElement("a");
    link.href = url;
    const filename = decodeURIComponent(location.pathname.split("/").pop() || "plan.html");
    link.download = filename.replace(/\.html?$/i, "") + ".review.html";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
    tell("已发起下载；原文件未更新，请保留下载的副本。");
  };
  window.addEventListener("beforeunload", event => { if (dirty() || busy) { event.preventDefault(); event.returnValue = ""; } });
  check();
})();
