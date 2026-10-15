const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '../skills/html-plan/assets/extension/background.js'), 'utf8');

function setup(error = null) {
  let listener, forwarded;
  const chrome = {runtime: {id: 'our-extension', getURL: p => `chrome-extension://our-extension/${p}`,
    onMessage: {addListener: fn => {listener = fn;}},
    sendNativeMessage: (_name, message, cb) => {forwarded = message; chrome.runtime.lastError = error; cb({ok: true, reviewRevision: 1});}}};
  vm.runInNewContext(script, {chrome, URL, TextEncoder});
  return {send(payload, sender = {}) {let response; listener({type: 'html-plan:bridge', payload},
    {id: 'our-extension', frameId: 0, url: 'file:///Users/test/a%20b.html#section', ...sender}, r => {response = r;});
    return {response, forwarded};}};
}
test('destination is taken from sender, never from payload', () => {
  const {response, forwarded} = setup().send({action: 'save', fileUrl: 'file:///wrong.html', path: '/wrong', requestId: 'one', review: {}});
  assert.equal(response.ok, true);
  assert.equal(forwarded.fileUrl, 'file:///Users/test/a%20b.html');
  assert.equal(forwarded.protocol, 'html-plan/v1');
  assert.equal(forwarded.path, undefined);
});
test('rejects remote pages, child frames and other extensions', () => {
  for (const sender of [{url: 'https://example.com/'}, {frameId: 3}, {id: 'other'}]) {
    const {response, forwarded} = setup().send({action: 'save'}, sender);
    assert.equal(response.ok, false);
    assert.equal(forwarded, undefined);
  }
});
test('popup can ping but cannot save', () => {
  const popup = {url: 'chrome-extension://our-extension/popup.html', frameId: undefined};
  assert.equal(setup().send({action: 'ping'}, popup).response.ok, true);
  assert.equal(setup().send({action: 'save'}, popup).response.ok, false);
});
test('native errors become explicit page errors', () => {
  const {response} = setup({message: 'not registered'}).send({action: 'ping'});
  assert.equal(response.code, 'HOST_UNAVAILABLE');
  assert.match(response.message, /not registered/);
});

const popupScript = fs.readFileSync(path.join(__dirname, '../skills/html-plan/assets/extension/popup.js'), 'utf8');
function popupContext(chrome, navigator = {}) {
  const elements = new Map();
  const document = {querySelector(selector) {
    if (!elements.has(selector)) elements.set(selector, {textContent: '', hidden: true, value: '', focus() {}, select() {this.selected = true;}});
    return elements.get(selector);
  }};
  vm.runInNewContext(popupScript, {document, navigator, chrome});
  return selector => document.querySelector(selector);
}
test('local file preview works without Chrome APIs and offers a copyable address', async () => {
  let copied;
  const $ = popupContext(undefined, {clipboard: {writeText: async text => {copied = text;}}});
  assert.match($('#file').textContent, /普通文件预览/);
  assert.equal($('#manual').hidden, false);
  assert.equal($('#settings-address').value, 'chrome://extensions/');
  await $('#settings').onclick();
  assert.equal(copied, 'chrome://extensions/');
  assert.match($('#message').textContent, /已复制/);
});
test('unavailable clipboard selects the address for manual copy', async () => {
  const $ = popupContext({});
  await $('#settings').onclick();
  assert.equal($('#settings-address').selected, true);
  assert.match($('#message').textContent, /手动复制/);
});
test('installed popup opens its own Chrome settings', async () => {
  let opened;
  const $ = popupContext({runtime: {id: 'installed-id', sendMessage: (_m, cb) => cb({ok: true, version: '0.1.0'})},
    extension: {isAllowedFileSchemeAccess: cb => cb(true)}, tabs: {create: (options, cb) => {opened = options.url; cb();}}});
  await $('#settings').onclick();
  assert.equal(opened, 'chrome://extensions/?id=installed-id');
  assert.match($('#host').textContent, /已连接/);
});
