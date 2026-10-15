// End-to-end test in an isolated Chromium profile. No normal Chrome profile edits.
// npm install --no-save playwright; npx playwright install chromium
// PLAYWRIGHT_MODULE / BROWSER_EXECUTABLE optionally select an existing runtime.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {execFileSync} = require('node:child_process');

const root = path.resolve(__dirname, '..');
const python = process.env.PYTHON || 'python3';
const scripts = path.join(root, 'skills/html-plan/scripts');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'html-plan-browser-'));
const profile = path.join(temp, 'profile');
const runtime = path.join(temp, 'runtime');
const extension = path.join(runtime, 'extension');
const extensionId = 'hlheonemgicdhgjghbfepkiddnlbmhml';
let context;
const py = (...args) => execFileSync(python, args, {encoding: 'utf8'});
async function until(fn, message) {
  for (let i = 0; i < 100; i++) {if (await fn()) return; await new Promise(r => setTimeout(r, 100));}
  throw new Error(message);
}

(async () => {
  py(path.join(scripts, 'setup.py'), 'install', '--root', runtime,
    '--manifest-dir', path.join(profile, 'NativeMessagingHosts'), '--no-register');
  context = await chromium.launchPersistentContext(profile, {headless: true,
    executablePath: process.env.BROWSER_EXECUTABLE || undefined, acceptDownloads: true,
    viewport: {width: 1280, height: 900},
    args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`]});
  const worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
  const ping = await worker.evaluate(() => new Promise(resolve => chrome.runtime.sendNativeMessage('com.html_plan.host',
    {protocol: 'html-plan/v1', action: 'ping'}, result => resolve(chrome.runtime.lastError ? {error: chrome.runtime.lastError.message} : result))));
  let mode = 'native-messaging';
  if (!ping?.ok) {
    // macOS Chromium may use the system's registered host location rather than
    // --user-data-dir. Keep the user's registration untouched: replace ONLY the
    // transport with an IPC harness. Real extension routing and Python framing run.
    mode = 'extension + real Python host (native transport harness)';
    await worker.evaluate(() => {
      globalThis.__hostQueue = []; globalThis.__hostCallbacks = new Map();
      chrome.runtime.sendNativeMessage = (name, message, callback) => {
        const id = crypto.randomUUID(); globalThis.__hostCallbacks.set(id, callback);
        globalThis.__hostQueue.push({id, message});
      };
    });
    const pump = setInterval(async () => {
      try {
        const messages = await worker.evaluate(() => globalThis.__hostQueue.splice(0));
        for (const {id, message} of messages) {
          const payload = Buffer.from(JSON.stringify(message));
          const header = Buffer.alloc(4); header.writeUInt32LE(payload.length);
          const output = execFileSync(python, [path.join(runtime, 'native-host/host.py')], {input: Buffer.concat([header, payload])});
          const result = JSON.parse(output.subarray(4).toString());
          await worker.evaluate(({id, result}) => {const callback = globalThis.__hostCallbacks.get(id); globalThis.__hostCallbacks.delete(id); callback(result);}, {id, result});
        }
      } catch { /* context may have closed */ }
    }, 40);
    pump.unref();
  }
  const first = await context.newPage(), second = await context.newPage();
  const errors = [];
  for (const page of [first, second]) page.on('pageerror', error => errors.push(error.message));
  const target = path.join(runtime, 'connection-test.html');
  const url = pathToFileURL(target).href;
  await first.goto(url); await second.goto(url);
  await until(async () => (await first.locator('#connection-status').textContent()).includes('已连接'), 'bridge did not connect');
  const comment = '中文 </script><script>坏代码</script> & 引号 " 😊';
  await first.locator('[data-comment="review-plan"]').fill(comment);
  await first.locator('#save-mode').selectOption('先下载副本');
  await first.locator('#overall-note').fill('跨平台连接测试');
  await first.locator('[data-strike="iterate-plan"]').check();
  await first.locator('#expand').click();
  await first.locator('[data-edit="schema-sample"]').fill('修改后的 schema\n{"limit": 500}');
  await first.locator('#save').click();
  await until(async () => (await first.locator('#save-status').textContent()).includes('已保存'), 'first save failed');
  let state = JSON.parse(py(path.join(scripts, 'plan.py'), 'review', target));
  assert.equal(state.review.comments['review-plan'], comment);
  assert.equal(state.reviewRevision, 1);
  assert.deepEqual(state.review.struck, ['iterate-plan']);
  assert.equal(state.review.edits['schema-sample'], '修改后的 schema\n{"limit": 500}');
  await second.locator('[data-comment="review-plan"]').fill('旧页面的输入不能丢');
  await second.locator('#save').click();
  await until(async () => (await second.locator('#save-status').textContent()).includes('保存被拒绝'), 'conflict not displayed');
  assert.equal(await second.locator('[data-comment="review-plan"]').inputValue(), '旧页面的输入不能丢');
  state = JSON.parse(py(path.join(scripts, 'plan.py'), 'review', target));
  assert.equal(state.reviewRevision, 1);
  assert.equal(state.review.comments['review-plan'], comment);
  await first.reload();
  assert.equal(await first.locator('[data-comment="review-plan"]').inputValue(), comment);
  assert.equal(await first.locator('#save-mode').inputValue(), '先下载副本');
  assert.equal(await first.locator('[data-strike="iterate-plan"]').isChecked(), true);
  await first.locator('#expand').click();
  assert.equal(await first.locator('[data-edit="schema-sample"]').inputValue(), '修改后的 schema\n{"limit": 500}');
  await until(async () => (await first.locator('#connection-status').textContent()).includes('已连接'), 'reconnect failed');
  await first.locator('[data-comment="review-plan"]').fill('下载副本中的新意见');
  const downloadEvent = first.waitForEvent('download');
  await first.locator('#download').click();
  const download = await downloadEvent;
  const copy = path.join(temp, 'download.html'); await download.saveAs(copy);
  const downloaded = JSON.parse(py(path.join(scripts, 'plan.py'), 'review', copy));
  assert.equal(downloaded.review.comments['review-plan'], '下载副本中的新意见');
  assert.equal(JSON.parse(py(path.join(scripts, 'plan.py'), 'review', target)).review.comments['review-plan'], comment);
  const copyPage = await context.newPage(); await copyPage.goto(pathToFileURL(copy).href);
  assert.equal(await copyPage.locator('[data-comment="review-plan"]').inputValue(), '下载副本中的新意见');
  const next = path.join(temp, 'v2.html');
  py(path.join(scripts, 'plan.py'), 'build', path.join(root, 'skills/html-plan/assets/example.json'), next, '--previous', target);
  const nextPage = await context.newPage(); await nextPage.goto(pathToFileURL(next).href);
  assert.equal(await nextPage.locator('[data-comment="review-plan"]').inputValue(), comment);
  assert.equal(await nextPage.locator('.version').textContent(), 'PLAN v2');
  const screenshots = path.join(root, 'test-results'); fs.mkdirSync(screenshots, {recursive: true});
  await first.screenshot({path: path.join(screenshots, 'desktop.png'), fullPage: true});
  await nextPage.setViewportSize({width: 390, height: 844});
  await nextPage.screenshot({path: path.join(screenshots, 'mobile.png'), fullPage: true});
  assert.equal(await nextPage.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ok: true, mode, checks: ['save', 'reopen', 'strike-and-edit', 'conflict-preserves-input', 'download', 'version-prefill', 'mobile-layout'], screenshots}));
})().finally(async () => {
  if (context) await context.close();
  fs.rmSync(temp, {recursive: true, force: true});
}).catch(error => {console.error(error); process.exitCode = 1;});
