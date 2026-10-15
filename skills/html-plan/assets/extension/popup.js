(() => {
  "use strict";
  const $ = selector => document.querySelector(selector);
  const api = globalThis.chrome;
  const isExtension = Boolean(api?.runtime?.id && api?.extension?.isAllowedFileSchemeAccess && api?.tabs?.create);
  const address = isExtension ? "chrome://extensions/?id=" + api.runtime.id : "chrome://extensions/";
  $("#settings-address").value = address;

  $("#settings").onclick = async () => {
    if (isExtension) {
      api.tabs.create({url: address}, () => {
        if (api.runtime.lastError) {
          $("#manual").hidden = false;
          $("#message").textContent = "打开失败，请复制下面的地址到 Chrome 地址栏。";
        }
      });
      return;
    }
    try {
      await navigator.clipboard.writeText(address);
      $("#message").textContent = "已复制。请切换到 Google Chrome，粘贴到地址栏并打开。";
    } catch {
      $("#settings-address").focus();
      $("#settings-address").select();
      $("#message").textContent = "请手动复制选中的地址，粘贴到 Google Chrome 地址栏。";
    }
  };

  if (!isExtension) {
    $("#file").textContent = "当前是普通文件预览，无法检查扩展权限";
    $("#host").textContent = "请安装扩展后，从 Chrome 工具栏打开此弹窗";
    $("#hint").textContent = "首次安装：在 Codex 中说“初始化 html-plan 环境”，然后在 Chrome 的扩展管理页开启开发者模式，加载初始化程序提供的扩展目录，并允许访问文件网址。";
    $("#settings").textContent = "复制 Chrome 扩展设置地址";
    $("#manual").hidden = false;
    return;
  }
  api.extension.isAllowedFileSchemeAccess(allowed => {
    $("#file").textContent = allowed ? "✓ 已允许访问本地文件" : "尚未开启“允许访问文件网址”";
  });
  api.runtime.sendMessage({type: "html-plan:bridge", payload: {action: "ping"}}, result => {
    const error = api.runtime.lastError;
    $("#host").textContent = !error && result?.ok ? `✓ 保存程序 v${result.version} 已连接` : "保存程序未连接，请运行初始化";
  });
})();
