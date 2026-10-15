"use strict";
const HOST = "com.html_plan.host";
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "html-plan:bridge") return false;
  const fail = (code, text) => sendResponse({ok: false, code, message: text});
  if (sender.id !== chrome.runtime.id) { fail("INVALID_SOURCE", "消息来源不正确。"); return false; }
  const payload = message.payload;
  if (!payload || !["save", "ping"].includes(payload.action)) { fail("INVALID_MESSAGE", "不支持的操作。"); return false; }
  const popup = sender.url === chrome.runtime.getURL("popup.html");
  let url;
  try { url = new URL(sender.url); } catch { fail("INVALID_SOURCE", "无法识别当前文件。"); return false; }
  if (!(popup && payload.action === "ping") && (sender.frameId !== 0 || url.protocol !== "file:")) {
    fail("INVALID_SOURCE", "请从本地 HTML Plan 页面保存。"); return false;
  }
  url.hash = ""; url.search = "";
  // Build a fresh message; never accept a page-supplied destination or protocol.
  const native = {protocol: "html-plan/v1", action: payload.action};
  if (payload.action === "save") {
    Object.assign(native, {fileUrl: url.href, requestId: payload.requestId, planId: payload.planId,
      documentId: payload.documentId, documentRevision: payload.documentRevision,
      expectedReviewRevision: payload.expectedReviewRevision, review: payload.review});
  }
  if (new TextEncoder().encode(JSON.stringify(native)).length > 4 * 1024 * 1024) {
    fail("MESSAGE_TOO_LARGE", "反馈过大，请缩短内容。"); return false;
  }
  chrome.runtime.sendNativeMessage(HOST, native, result => {
    const error = chrome.runtime.lastError;
    if (error) { fail("HOST_UNAVAILABLE", "本地保存程序未连接：" + error.message); return; }
    sendResponse(result && typeof result.ok === "boolean" ? result : {ok: false, code: "INVALID_RESPONSE", message: "保存程序返回了无效结果。"});
  });
  return true;
});
