'use strict';
const assert = require('assert');
global.window = {location: {hostname: '192.168.11.1'}};
const sandbox = {module: {exports: {}}, window, clearTimeout: () => {}, setTimeout: () => 1};
require('vm').runInNewContext(require('fs').readFileSync(require('path').join(__dirname, 'gl-sdk4-ui-openclash.common.js'), 'utf8'), sandbox);
const view = sandbox.module.exports;
assert.equal(view.computed.dashboardUrl.call({status: {dashboard_port: 9090}}), 'http://192.168.11.1:9090/ui/');
assert.equal(view.computed.dashboardUrl.call({status: {dashboard_port: 9191}}), 'http://192.168.11.1:9191/ui/');
assert.equal(view.computed.dashboardUrl.call({status: {dashboard_port: 9090, dashboard_path: '/ui/metacubexd/'}}), 'http://192.168.11.1:9090/ui/metacubexd/');
assert.equal(view.computed.dashboardUrl.call({status: {dashboard_port: 99999}}), 'http://192.168.11.1:9090/ui/');
window.location.hostname = '2001:db8::1';
assert.equal(view.computed.dashboardUrl.call({status: null}), 'http://[2001:db8::1]:9090/ui/');
window.location.hostname = '[2001:db8::1]';
assert.equal(view.computed.dashboardUrl.call({status: null}), 'http://[2001:db8::1]:9090/ui/');
window.location.hostname = '192.168.11.1';
function h(tag, data, children) {
  if (arguments.length === 2 && (typeof data === 'string' || Array.isArray(data))) return {tag, data: {}, children: data};
  return {tag, data: data || {}, children};
}
function links(tree, result = []) {
  if (!tree || typeof tree !== 'object') return result;
  if (Array.isArray(tree)) { tree.forEach(x => links(x, result)); return result; }
  if (tree.tag === 'a') result.push(tree);
  links(tree.children, result);
  return result;
}
const context = Object.assign(view.data(), {
  status: {installed: true, running: true, dashboard_port: 9090},
  disabled: false, busy: false, dirty: false,
  dashboardUrl: 'http://192.168.11.1:9090/ui/'
});
const button = links(view.render.call(context, h)).find(x => x.children === 'Clash 控制面板 ↗');
assert(button);
assert.equal(button.data.attrs.href, 'http://192.168.11.1:9090/ui/');
assert.equal(button.data.attrs.target, '_blank');
assert.equal(button.data.attrs.rel, 'noopener noreferrer');
assert(!button.data.attrs.href.includes('secret'));
context.status.running = false;
const stopped = links(view.render.call(context, h)).find(x => x.children === 'Clash 控制面板 ↗');
assert.equal(stopped.data.attrs.href, undefined);
assert.equal(stopped.data.attrs['aria-disabled'], 'true');
console.log('PASS: dashboard link, configured port, IPv6 hosts, stopped state, no controller credential in URL');
function text(tree) {
  if (typeof tree === 'string') return tree;
  if (Array.isArray(tree)) return tree.map(text).join(' ');
  return tree && typeof tree === 'object' ? text(tree.children) : '';
}
context.status.subscription = {available: true, upload: 1073741824, download: 1073741824, total: 107374182400, expire: 1893456000, updated_at: 1791172800};
let output = text(view.render.call(context, h));
assert(output.includes('98.00 GiB'));
assert(output.includes('2.00 GiB / 100.00 GiB'));
assert(output.includes('到期时间'));
context.status.subscription = {available: false, refreshing: true};
output = text(view.render.call(context, h));
assert(output.includes('正在向订阅服务查询额度'));
assert(!output.includes('0.00 GiB'));
context.status.subscription = {available: true, upload: 100, download: 100, total: 0, expire: 0, stale: true, error: '刷新失败'};
output = text(view.render.call(context, h));
assert(output.includes('未设置额度上限'));
assert(output.includes('未设置到期时间'));
assert(output.includes('上次成功取得的数据'));
console.log('PASS: numeric quota display, GiB units, loading without fake zero, unset limits, stale/error state');
(async function () {
  const instance = Object.assign(view.data(), {status: {installed: true}, draft: {enabled: true, mode: 'global', operation_mode: 'fake-ip', ipv6_enabled: true}});
  Object.keys(view.methods).forEach(key => instance[key] = view.methods[key].bind(instance));
  instance.schedulePoll = () => {};
  window.$request = () => Promise.resolve({installed: true, enabled: true, mode: 'rule', operation_mode: 'fake-ip', ipv6_enabled: true, subscription: {available: false}});
  instance.fetchStatus(false);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(instance.status.mode, 'rule');
  assert.equal(instance.draft.mode, 'global');
  instance.discard();
  assert.equal(instance.draft.mode, 'rule');
  console.log('PASS: automatic status refresh preserves unsaved edits; explicit discard restores current settings');
})().catch(error => { console.error(error); process.exitCode = 1; });
