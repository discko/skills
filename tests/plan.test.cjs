const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {randomUUID} = require('node:crypto');
const script = fs.readFileSync(require('node:path').join(__dirname, '../skills/html-plan/assets/plan.js'), 'utf8');

function setup({clipboard = 'ok', host = 'missing', typed = false, savedDecisions = {}, tableMode = false} = {}) {
  const classes = () => {
    const set = new Set();
    return {add: x => set.add(x), remove: x => set.delete(x), contains: x => set.has(x),
      toggle(x, on) { if (on) set.add(x); else set.delete(x); }};
  };
  const element = extra => ({value: '', textContent: '', disabled: false, hidden: true, dataset: {}, classList: classes(), ...extra});
  const nodes = new Map();
  const $ = key => {if (!nodes.has(key)) nodes.set(key, element()); return nodes.get(key);};
  const state = {schemaVersion: 1, planId: 'plan', documentId: 'doc', documentRevision: 2, reviewRevision: 3,
    savedAt: 'previous-save', lastRequest: {id: 'old'}, previousFeedback: [],
    review: {decisions: savedDecisions, comments: {}, struck: [], edits: {}, seen: [], note: ''}};
  state.decisionDefaults = {choice: 'A'};
  $('#html-plan-state').textContent = JSON.stringify(state);
  const decision = element({dataset: {decision: 'choice'}, value: 'A', closest: () => ({dataset: {claim: 'item'}})});
  const comment = element({dataset: {comment: 'item'}});
  const strike = element({dataset: {strike: 'item'}, checked: false});
  const edit = element({dataset: {edit: 'code'}});
  const selectors = {'[data-decision]': [decision], '[data-comment]': [comment], '[data-strike]': [strike], '[data-edit]': [edit]};
  const checkbox = element({dataset: {decision: 'enabled', kind: 'checkbox'}, checked: false});
  function group(id, kind, values) {
    const inputs = values.map(value => element({value, checked: false}));
    return element({dataset: {decision: id, kind}, inputs,
      querySelector: () => inputs.find(input => input.checked),
      querySelectorAll: selector => selector === 'input:checked' ? inputs.filter(input => input.checked) : inputs});
  }
  const radio = group('mode', 'radio', ['A', 'B']);
  const multi = group('fields', 'checkboxes', ['中文 </script> " &', 'B', 'C']);
  if (typed) selectors['[data-decision]'].push(checkbox, radio, multi);
  for (const el of selectors['[data-decision]']) el.closest = selector => selector === '[hidden]' ? null : {dataset: {claim: 'item'}};
  const search = element(), filter = element({value: 'all'}), count = element();
  for (const el of [search, filter]) {
    el.handlers = {}; el.addEventListener = (name, fn) => {el.handlers[name] = fn;};
  }
  const row = element({dataset: {claim: 'item'}, querySelector: selector => selector === '[data-comment]' ? comment : {textContent: 'search-api'},
    querySelectorAll: selector => selector === '[data-decision]' ? [decision] : []});
  const table = {querySelector: selector => ({'[data-table-search]': search, '[data-table-filter]': filter, '[data-table-count]': count})[selector],
    querySelectorAll: () => [row]};
  if (tableMode) selectors['[data-review-table]'] = [table];
  const windowEvents = {}, documentEvents = {}, timers = new Map();
  let timerId = 0, copied, writes = 0, finishCopy;
  const document = {title: '计划中文', querySelector: $, documentElement: {cloneNode: () => ({})},
    querySelectorAll: selector => selectors[selector] || (selector === 'input, textarea, select, button' ? [...nodes.values(), decision, comment, strike, edit] : []),
    addEventListener: (name, fn) => {documentEvents[name] = fn;}};
  const window = {addEventListener: (name, fn) => {windowEvents[name] = fn;}, postMessage(message) {
    if (host === 'missing') return;
    const result = message.payload.action === 'ping' ? {ok: ['ok', 'old'].includes(host), version: 'test', capabilities: host === 'ok' ? ['typed-decisions'] : []} :
      host === 'ok' ? {ok: true, reviewRevision: 4, savedAt: 'now'} : {ok: false, code: host, message: '保存被拒绝'};
    windowEvents.message({source: window, data: {channel: 'html-plan:response', requestId: message.requestId, result}});
  }};
  const navigator = clipboard === 'missing' ? {} : {clipboard: {writeText: async text => {
    writes++;
    if (clipboard === 'denied') throw new Error('NotAllowedError');
    if (clipboard === 'deferred') await new Promise(resolve => {finishCopy = resolve;});
    copied = text;
  }}};
  vm.runInNewContext(script, {document, window, navigator, location: {href: 'file:///plan.html'},
    crypto: {randomUUID}, setTimeout(fn, ms) {const id = ++timerId; timers.set(id, {fn, ms}); return id;}, clearTimeout: id => timers.delete(id)});
  return {$, comment, decision, strike, edit, checkbox, radio, multi, row, count,
    filter(value) {filter.value = value; filter.handlers.input(); documentEvents.input({target: {matches: () => true}});},
    search(value) {search.value = value; search.handlers.input(); documentEvents.input({target: {matches: () => true}});}, get copied() {return JSON.parse(copied);}, get writes() {return writes;},
    finishCopy() {finishCopy();},
    input() {documentEvents.input();}, expire(ms) {for (const [id, timer] of [...timers]) if (timer.ms === ms) {timers.delete(id); timer.fn();}},
    dirty() {let prevented = false; windowEvents.beforeunload({preventDefault() {prevented = true;}}); return prevented;}};
}

test('copy exports current review without reporting a save or clearing dirty state', async () => {
  const page = setup();
  page.comment.value = '中文 </script>\n" & 😊'; page.decision.value = 'B'; page.strike.checked = true;
  page.edit.value = 'updated code'; page.$('#overall-note').value = '总体意见'; page.input();
  await page.$('#copy-review').onclick();
  const payload = page.copied;
  assert.equal(payload.type, 'html-plan-review');
  assert.equal(payload.documentId, 'doc'); assert.equal(payload.documentRevision, 2); assert.equal(payload.baseReviewRevision, 3);
  assert.deepEqual(payload.review, {decisions: {choice: 'B'}, comments: {item: page.comment.value}, struck: ['item'], edits: {code: 'updated code'}, seen: [], note: '总体意见'});
  assert.equal(payload.savedAt, undefined); assert.equal(payload.lastRequest, undefined); assert.equal(payload.previousFeedback, undefined);
  assert.equal(page.dirty(), true); assert.match(page.$('#copy-toast').textContent, /已复制/);
  assert.equal(page.$('#save-status').textContent, '有未保存修改');
  page.comment.value = '再次修改'; await page.$('#copy-review').onclick();
  assert.equal(page.copied.review.comments.item, '再次修改');
  page.expire(5000); assert.equal(page.$('#copy-toast').hidden, true);
});

for (const clipboard of ['missing', 'denied']) test(`clipboard ${clipboard} shows failure toast and retains input`, async () => {
  const page = setup({clipboard}); page.comment.value = '保留我';
  await page.$('#copy-review').onclick();
  assert.match(page.$('#copy-toast').textContent, /复制失败/);
  assert.equal(page.$('#copy-toast').classList.contains('error'), true);
  assert.equal(page.$('#copy-review').disabled, false); assert.equal(page.comment.value, '保留我'); assert.equal(page.dirty(), true);
});

test('missing extension times out and suggests copying without losing review', async () => {
  const page = setup(); page.comment.value = '离线意见'; page.expire(15000); await Promise.resolve();
  assert.match(page.$('#connection-status').textContent, /复制反馈/);
  assert.equal(page.$('#copy-review').classList.contains('copy-suggested'), true);
  const save = page.$('#save').onclick(); page.expire(15000); await save;
  await page.$('#copy-review').onclick(); assert.equal(page.copied.review.comments.item, '离线意见');
});

for (const host of ['HOST_UNAVAILABLE', 'REVISION_CONFLICT']) test(`${host} preserves input and enables copying`, async () => {
  const page = setup({host}); await Promise.resolve(); page.comment.value = '失败后反馈';
  await page.$('#save').onclick(); await page.$('#copy-review').onclick();
  assert.equal(page.copied.baseReviewRevision, 3); assert.equal(page.copied.review.comments.item, '失败后反馈');
  assert.match(page.$('#save-status').textContent, /复制反馈/); assert.equal(page.dirty(), true);
});

test('successful save updates the base revision of later copied feedback', async () => {
  const page = setup({host: 'ok'}); await Promise.resolve(); page.comment.value = '已保存';
  await page.$('#save').onclick(); assert.equal(page.dirty(), false);
  page.comment.value = '保存后新意见'; await page.$('#copy-review').onclick();
  assert.equal(page.copied.baseReviewRevision, 4); assert.equal(page.copied.review.comments.item, '保存后新意见');
  assert.equal(page.dirty(), true);
});

test('copy finishing during a pending save does not leave its button disabled', async () => {
  const page = setup({clipboard: 'deferred'});
  const copy = page.$('#copy-review').onclick();
  const save = page.$('#save').onclick();
  page.finishCopy(); await copy;
  assert.equal(page.$('#copy-review').disabled, true);
  page.expire(15000); await save;
  assert.equal(page.$('#copy-review').disabled, false);
});


test('typed controls hydrate, copy and save booleans, radio strings and arrays without conversion', async () => {
  const page = setup({typed: true, host: 'ok', savedDecisions: {enabled: true, mode: 'B', fields: ['B']}});
  await Promise.resolve();
  assert.equal(page.checkbox.checked, true); assert.equal(page.radio.inputs[1].checked, true);
  assert.equal(page.multi.inputs[1].checked, true); assert.equal(page.dirty(), false);
  page.checkbox.checked = false;
  page.radio.inputs[0].checked = true; page.radio.inputs[1].checked = false;
  page.multi.inputs[0].checked = true;
  await page.$('#copy-review').onclick();
  assert.deepEqual(page.copied.review.decisions, {choice: 'A', enabled: false, mode: 'A', fields: ['中文 </script> " &', 'B']});
  await page.$('#save').onclick(); assert.equal(page.dirty(), false);
  page.multi.inputs.forEach(input => {input.checked = false;});
  page.radio.inputs.forEach(input => {input.checked = false;});
  await page.$('#copy-review').onclick();
  assert.deepEqual(page.copied.review.decisions.fields, []); assert.equal(page.copied.review.decisions.mode, '');
  assert.equal(page.copied.baseReviewRevision, 4);
});

test('old hosts produce an upgrade instruction while typed feedback remains copyable', async () => {
  const page = setup({typed: true, host: 'old'}); await Promise.resolve();
  assert.match(page.$('#connection-status').textContent, /0.2.0/);
  await page.$('#save').onclick();
  assert.match(page.$('#save-status').textContent, /setup.py install/);
  await page.$('#copy-review').onclick(); assert.equal(page.copied.review.decisions.enabled, false);
  assert.equal(page.copied.baseReviewRevision, 3);
});

test('table filters do not dirty the page or drop hidden feedback; changes compare against generated defaults', async () => {
  const page = setup({tableMode: true});
  assert.equal(page.row.hidden, false);
  page.filter('changed'); assert.equal(page.row.hidden, true); assert.equal(page.dirty(), false);
  page.decision.value = 'B'; page.filter('changed'); assert.equal(page.row.hidden, false);
  page.search('no-match'); assert.equal(page.row.hidden, true);
  await page.$('#copy-review').onclick(); assert.equal(page.copied.review.decisions.choice, 'B');
  page.search('search-api'); assert.equal(page.row.hidden, false); assert.equal(page.count.textContent, '1 / 1 行');
  page.decision.value = 'A'; page.comment.value = '依据不足'; page.search('依据不足');
  assert.equal(page.row.hidden, false);
});
