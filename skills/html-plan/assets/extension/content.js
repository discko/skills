"use strict";
window.addEventListener("message", event => {
  if (event.source !== window || event.data?.channel !== "html-plan:request") return;
  if (!document.querySelector('meta[name="html-plan"][content="1"]') || !document.querySelector("#html-plan-state")) return;
  const {requestId, payload} = event.data;
  if (typeof requestId !== "string" || requestId.length > 100) return;
  const respond = result => window.postMessage({channel: "html-plan:response", requestId, result}, "*");
  try {
    chrome.runtime.sendMessage({type: "html-plan:bridge", payload}, result => {
      const error = chrome.runtime.lastError;
      respond(error ? {ok: false, code: "EXTENSION_ERROR", message: "扩展连接失效，请保留输入并重新打开页面。"} : result);
    });
  } catch {
    respond({ok: false, code: "EXTENSION_ERROR", message: "扩展已更新，请下载反馈副本后重新打开页面。"});
  }
});
