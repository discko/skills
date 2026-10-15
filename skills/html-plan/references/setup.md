# 安装与诊断

需要本机 Chrome 与 Python 3.9+。macOS 用 `python3`，Windows 可用 `py -3`；先验证命令确实存在。host 无第三方 Python 依赖。

用绝对路径运行本 Skill 的 `scripts/setup.py install`。默认位置：

- macOS：`~/Library/Application Support/HtmlPlan/`
- Windows：`%LOCALAPPDATA%\HtmlPlan\`

这里保存 extension、native-host、启动脚本和连接测试页。每个项目不重复安装。

Mac 注册到用户 Chrome 的 NativeMessagingHosts 目录。Windows 注册到 HKCU 的 `Software\Google\Chrome\NativeMessagingHosts\com.html_plan.host`，不要求系统级安装。

安装器记录当前 `sys.executable`，生成 `.sh` 或 `.bat` 入口。Python 被移动或删除后重新运行安装器；不要依赖已删除的 venv。Windows 不使用 pythonw，它缺少本协议所需的标准流。

可选参数：

```text
setup.py install --root <稳定运行目录>
setup.py install --skill-dir <用户的Skill目录>/html-plan
setup.py doctor
setup.py uninstall
```

自定义 root 后，doctor/uninstall 使用同一参数。`--manifest-dir` 和 `--no-register` 用于隔离测试或自定义浏览器注册位置，普通安装无需设置。

初始化本地环境后：

1. Chrome 打开 `chrome://extensions`，开启开发者模式。
2. “加载已解压的扩展”，选择安装器返回的 extensionDirectory。
3. 扩展详情中开启“允许访问文件网址”。
4. 用 Chrome 打开 connection-test.html，修改意见并保存，再重新打开核对。

固定扩展 ID：`hlheonemgicdhgjghbfepkiddnlbmhml`。manifest.key 为公开公钥，不能当作凭据；仓库不包含私钥。

更新后在 Chrome 扩展管理页点“重新加载”，并重新打开已有计划页。已输入的意见先保存或下载。host 每次调用重新启动，无需管理后台进程。

`doctor` 的成功不证明 Chrome 已加载扩展。扩展弹窗检查文件授权和 native host 连接；页面保存再重开才是完整验证。

- HOST_UNAVAILABLE：检查 host 注册、Python 路径和扩展 ID，运行 doctor。
- BRIDGE_TIMEOUT：检查扩展是否加载及文件授权；旧标签页可能需要重开，先下载输入。
- REVISION_CONFLICT：其他标签页先保存了；当前输入保留，可下载后对照最新文件处理。
- DOCUMENT_CHANGED：文件身份或计划版本已变化；勿强制覆盖。
- IO_ERROR：文件被移动、只读或被其他程序占用。

卸载仅移除 host 注册及入口和运行代码。保留测试 HTML、扩展目录、Skill 与用户计划，浏览器扩展可在 Chrome 中手动移除。

0.2.0 新增布尔值与多选数组反馈。页面检测到 host 缺少 `typed-decisions` 能力时提示升级，并阻止向该旧 host 保存新类型，原输入仍可复制。重新运行 install 会更新 host，无需逐项目安装。旧 HTML 的正文和布局不会被自动改写。
