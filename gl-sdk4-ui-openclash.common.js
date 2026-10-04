module.exports = (function () {
  'use strict';

  function bool(value) {
    return value === true || value === 1 || value === '1' || value === 'true';
  }

  function message(error) {
    if (!error) return '请求失败，请稍后重试。';
    var text = typeof error === 'string' ? error : error.message || error.error || JSON.stringify(error);
    return /timeout.*exceeded/i.test(text) ? '路由器请求超时，请检查连接后重试。' : text;
  }

  function unwrap(value) {
    if (value && value.error) throw new Error(message(value.error));
    if (value && value.success === false) throw new Error(value.message || '操作失败。');
    if (Array.isArray(value) && typeof value[0] === 'number') {
      if (value[0] !== 0) throw new Error('路由器请求失败（' + value[0] + '）。');
      return unwrap(value[1]);
    }
    if (value && Array.isArray(value.result)) return unwrap(value.result);
    if (value && value.result && typeof value.result === 'object') return unwrap(value.result);
    if (value && value.data && typeof value.data === 'object' && !Object.prototype.hasOwnProperty.call(value, 'installed')) return unwrap(value.data);
    return value;
  }

  function rpc(method, values) {
    var request = window.$rpcRequest || window.$request;
    if (typeof request !== 'function') return Promise.reject(new Error('管理页面的请求接口尚未加载，请刷新页面。'));
    return Promise.resolve().then(function () {
      return request('call', ['sid', 'openclash', method, values || {}]);
    }).then(unwrap);
  }

  function normalize(value) {
    if (!value || typeof value !== 'object' || !Object.prototype.hasOwnProperty.call(value, 'installed')) {
      throw new Error('路由器返回的 OpenClash 状态不完整，请刷新页面。');
    }
    return {
      installed: bool(value.installed),
      enabled: bool(value.enabled),
      running: bool(value.running),
      boot_enabled: bool(value.boot_enabled),
      mode: ['rule', 'global', 'direct'].indexOf(value.mode) >= 0 ? value.mode : 'rule',
      operation_mode: ['fake-ip', 'redir-host'].indexOf(value.operation_mode) >= 0 ? value.operation_mode : 'fake-ip',
      ipv6_enabled: bool(value.ipv6_enabled),
      ipv6_dns: bool(value.ipv6_dns),
      core_version: value.core_version || '',
      config_name: value.config_name || '',
      dashboard_port: Number(value.dashboard_port) || 9090,
      dashboard_path: value.dashboard_path === '/ui/metacubexd/' ? '/ui/metacubexd/' : '/ui/',
      subscription: value.subscription && typeof value.subscription === 'object' ? value.subscription : { available: false, error: '订阅信息暂不可用' },
      busy: bool(value.busy),
      dns_chain: value.dns_chain || '',
      last_error: value.last_error || '',
      last_message: value.last_message || ''
    };
  }

  function settings(status) {
    return {
      enabled: status.enabled,
      mode: status.mode,
      operation_mode: status.operation_mode,
      ipv6_enabled: status.ipv6_enabled
    };
  }

  function same(a, b) {
    return a.enabled === b.enabled && a.mode === b.mode && a.operation_mode === b.operation_mode && a.ipv6_enabled === b.ipv6_enabled;
  }

  var style = {
    page: { color: 'inherit', fontSize: '14px', lineHeight: '1.6', padding: '20px', maxWidth: '1000px', margin: '0 auto', boxSizing: 'border-box' },
    card: { padding: '22px', marginBottom: '18px', border: '1px solid rgba(128,128,128,.18)', borderRadius: '14px', background: 'rgba(128,128,128,.035)', boxShadow: '0 3px 14px rgba(0,0,0,.025)' },
    header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' },
    title: { margin: '0', fontSize: '22px', fontWeight: '600', color: 'inherit' },
    status: { display: 'inline-flex', alignItems: 'center', gap: '7px', fontSize: '14px' },
    meta: { marginTop: '12px', opacity: '0.72', fontSize: '13px', overflowWrap: 'anywhere' },
    row: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap', padding: '18px 0', borderBottom: '1px solid rgba(128,128,128,.16)' },
    label: { flex: '1 1 210px', minWidth: '0' },
    name: { fontSize: '15px', fontWeight: '500' },
    hint: { marginTop: '4px', fontSize: '13px', opacity: '0.7' },
    choices: { display: 'flex', gap: '8px', flexWrap: 'wrap' },
    choice: { color: 'inherit', background: 'transparent', border: '1px solid rgba(128,128,128,.35)', borderRadius: '5px', padding: '7px 12px', fontSize: '14px', lineHeight: '20px', cursor: 'pointer', minHeight: '36px' },
    button: { color: 'inherit', background: 'transparent', border: '1px solid rgba(128,128,128,.35)', borderRadius: '5px', padding: '8px 16px', fontSize: '14px', lineHeight: '20px', cursor: 'pointer', minHeight: '38px' },
    primary: { color: '#fff', background: 'var(--gl-color-primary, var(--primary-color, #368ad9))', borderColor: 'var(--gl-color-primary, var(--primary-color, #368ad9))' },
    controls: { display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', marginTop: '20px' },
    notice: { padding: '10px 12px', marginTop: '16px', border: '1px solid rgba(128,128,128,.3)', borderRadius: '5px', overflowWrap: 'anywhere' },
    link: { color: 'var(--gl-color-primary, var(--primary-color, #368ad9))', textDecoration: 'none' }
  };

  function bytes(value) {
    if (typeof value !== 'number' || !isFinite(value) || value < 0) return '—';
    return (value / 1073741824).toFixed(2) + ' GiB';
  }

  function date(value) {
    if (typeof value !== 'number' || !isFinite(value) || value <= 0) return '未提供';
    return new Date(value * 1000).toLocaleString('zh-CN', { hour12: false });
  }

  function merge(a, b) {
    var out = {};
    Object.keys(a).forEach(function (key) { out[key] = a[key]; });
    Object.keys(b || {}).forEach(function (key) { out[key] = b[key]; });
    return out;
  }

  return {
    name: 'OpenClashView',
    data: function () {
      return {
        status: null,
        draft: { enabled: false, mode: 'rule', operation_mode: 'fake-ip', ipv6_enabled: false },
        desired: null,
        fetching: false,
        saving: false,
        applying: false,
        refreshingSubscription: false,
        timer: null,
        error: '',
        resultMessage: '',
        lastUpdated: '',
        disposed: false
      };
    },
    computed: {
      dashboardUrl: function () {
        var hostname = window.location.hostname;
        if (hostname.indexOf(':') >= 0 && hostname.charAt(0) !== '[') hostname = '[' + hostname + ']';
        var port = this.status && Number(this.status.dashboard_port) || 9090;
        if (port < 1 || port > 65535 || Math.floor(port) !== port) port = 9090;
        var path = this.status && this.status.dashboard_path === '/ui/metacubexd/' ? '/ui/metacubexd/' : '/ui/';
        return 'http://' + hostname + ':' + port + path;
      },
      busy: function () {
        return this.saving || this.applying || !!(this.status && this.status.busy);
      },
      dirty: function () {
        return !!this.status && !same(this.draft, settings(this.status));
      },
      disabled: function () {
        return !this.status || !this.status.installed || this.busy;
      }
    },
    created: function () {
      this.fetchStatus(true);
    },
    beforeDestroy: function () {
      this.disposed = true;
      clearTimeout(this.timer);
      this.timer = null;
    },
    methods: {
      schedulePoll: function (delay) {
        var self = this;
        clearTimeout(this.timer);
        if (this.disposed) return;
        this.timer = setTimeout(function () {
          self.timer = null;
          self.fetchStatus(false);
        }, delay || 3000);
      },
      fetchStatus: function (syncDraft) {
        var self = this;
        if (this.fetching || this.disposed) return;
        this.fetching = true;
        rpc('get_status', {}).then(function (value) {
          if (self.disposed) return;
          var status = normalize(value);
          var firstLoad = !self.status;
          self.status = status;
          self.error = '';
          self.lastUpdated = new Date().toLocaleTimeString('zh-CN', { hour12: false });
          if (status.busy) {
            if (firstLoad) self.draft = settings(status);
            self.schedulePoll();
            return;
          }
          clearTimeout(self.timer);
          self.timer = null;
          if (self.applying) {
            self.applying = false;
            self.draft = settings(status);
            if (status.last_error) {
              self.error = message(status.last_error);
            } else if (!same(self.desired, settings(status))) {
              self.error = '操作已结束，但当前配置与保存内容不一致，请检查高级配置或重新应用。';
            } else if (self.desired.enabled && !status.running) {
              self.error = '配置已保存，但 OpenClash 未成功启动，请查看高级配置中的日志。';
            } else if (!self.desired.enabled && status.running) {
              self.error = 'OpenClash 仍在运行，请检查高级配置中的日志。';
            } else {
              self.resultMessage = status.last_message || '设置已生效。';
            }
            self.desired = null;
          } else if (firstLoad || syncDraft) {
            self.draft = settings(status);
            self.resultMessage = '';
          }
          self.schedulePoll(status.subscription.refreshing ? 3000 : 30000);
        }).catch(function (error) {
          if (self.disposed) return;
          self.error = message(error);
          self.schedulePoll(self.applying || (self.status && self.status.busy) ? 3000 : 30000);
        }).then(function () {
          self.fetching = false;
        });
      },
      setValue: function (key, value) {
        if (this.disabled) return;
        this.draft[key] = value;
        this.error = '';
        this.resultMessage = '';
      },
      apply: function () {
        var self = this;
        if (this.disabled || this.fetching || !this.dirty) return;
        this.error = '';
        this.resultMessage = '';
        this.saving = true;
        this.desired = settings(this.draft);
        rpc('set_config', this.desired).then(function () {
          if (self.disposed) return;
          self.saving = false;
          self.applying = true;
          self.schedulePoll();
        }).catch(function (error) {
          if (self.disposed) return;
          self.saving = false;
          self.applying = false;
          self.desired = null;
          self.error = message(error);
        });
      },
      refresh: function () {
        if (!this.busy && !this.fetching) this.fetchStatus(false);
      },
      refreshSubscription: function () {
        var self = this;
        if (this.refreshingSubscription || (this.status && this.status.subscription.refreshing)) return;
        this.refreshingSubscription = true;
        rpc('refresh_subscription', {}).then(function () {
          self.fetchStatus(false);
          self.schedulePoll();
        }).catch(function (error) { self.error = message(error); }).then(function () { self.refreshingSubscription = false; });
      },
      discard: function () {
        if (this.status && !this.busy) { this.draft = settings(this.status); this.error = ''; this.resultMessage = ''; }
      }
    },
    render: function (h) {
      var self = this;
      var status = this.status;
      var disabled = this.disabled;

      function button(label, action, inactive, primary) {
        return h('button', {
          attrs: { type: 'button', disabled: inactive },
          style: merge(style.button, merge(primary ? style.primary : {}, inactive ? { opacity: '.5', cursor: 'not-allowed' } : {})),
          on: { click: action }
        }, label);
      }

      function choices(key, items, ariaLabel) {
        return h('div', { style: style.choices, attrs: { role: 'group', 'aria-label': ariaLabel } }, items.map(function (item) {
          var selected = self.draft[key] === item[0];
          return h('button', {
            key: item[0],
            attrs: { type: 'button', disabled: disabled, 'aria-pressed': selected ? 'true' : 'false' },
            style: merge(style.choice, merge(selected ? { color: 'var(--gl-color-primary, var(--primary-color, #368ad9))', borderColor: 'var(--gl-color-primary, var(--primary-color, #368ad9))', background: 'rgba(54,138,217,.08)' } : {}, disabled ? { opacity: '.5', cursor: 'not-allowed' } : {})),
            on: { click: function () { self.setValue(key, item[0]); } }
          }, item[1]);
        }));
      }

      function toggle(key, name) {
        return h('label', { style: { display: 'inline-flex', alignItems: 'center', gap: '9px', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? '.55' : '1', padding: '6px 0' } }, [
          h('input', {
            attrs: { type: 'checkbox', disabled: disabled, role: 'switch', 'aria-label': name, 'aria-checked': self.draft[key] ? 'true' : 'false' },
            domProps: { checked: self.draft[key] },
            style: { width: '18px', height: '18px', margin: '0', accentColor: 'var(--gl-color-primary, var(--primary-color, #368ad9))', cursor: 'inherit' },
            on: { change: function (event) { self.setValue(key, event.target.checked); } }
          }),
          h('span', self.draft[key] ? '开启' : '关闭')
        ]);
      }

      function row(name, hint, control, last) {
        return h('div', { style: merge(style.row, last ? { borderBottom: '0' } : {}) }, [
          h('div', { style: style.label }, [h('div', { style: style.name }, name), h('div', { style: style.hint }, hint)]),
          control
        ]);
      }

      var stateText = this.busy ? '正在应用设置…' : !status ? this.error ? '状态读取失败' : '读取状态中…' : !status.installed ? '未安装' : status.running ? '运行中' : '已停止';
      var stateColor = this.busy || !status ? '#bd8f35' : status.running ? '#46a66a' : 'currentColor';
      var error = this.error || (status && status.last_error ? message(status.last_error) : '');
      var dnsChain = status && status.dns_chain;
      var subscription = status && status.subscription || {};
      var available = subscription.available && typeof subscription.total === 'number' && typeof subscription.upload === 'number' && typeof subscription.download === 'number';
      var used = available ? subscription.upload + subscription.download : 0;
      var remaining = available ? Math.max(0, subscription.total - used) : 0;
      var percent = available && subscription.total > 0 ? Math.min(100, 100 * used / subscription.total) : 0;
      var subscriptionBusy = this.refreshingSubscription || subscription.refreshing;
      var expired = subscription.expire > 0 && subscription.expire * 1000 <= Date.now();
      function metric(label, value, emphasis) {
        return h('div', { style: { flex: '1 1 165px', padding: '14px 16px', background: 'rgba(54,138,217,.055)', borderRadius: '10px', minWidth: '0' } }, [
          h('div', { style: style.hint }, label),
          h('div', { style: { marginTop: '6px', fontSize: emphasis ? '24px' : '18px', fontWeight: '600', color: emphasis ? 'var(--gl-color-primary, var(--primary-color, #368ad9))' : 'inherit', overflowWrap: 'anywhere' } }, value)
        ]);
      }
      if (Array.isArray(dnsChain)) dnsChain = dnsChain.join(' → ');
      if (dnsChain && typeof dnsChain === 'object') dnsChain = JSON.stringify(dnsChain);

      return h('main', { class: 'openclash-view', style: style.page }, [
        h('section', { style: style.card, attrs: { 'aria-label': 'OpenClash 状态' } }, [
          h('div', { style: style.header }, [
            h('h1', { style: style.title }, 'OpenClash'),
            h('div', { style: style.status, attrs: { role: 'status', 'aria-live': 'polite' } }, [
              h('span', { style: { width: '8px', height: '8px', flex: '0 0 8px', borderRadius: '50%', background: stateColor, opacity: status && !status.running && !self.busy ? '.5' : '1' }, attrs: { 'aria-hidden': 'true' } }),
              h('span', stateText)
            ])
          ]),
          status ? h('div', { style: style.meta }, [
            h('div', '核心版本：' + (status.core_version || '暂无')),
            h('div', '当前配置：' + (status.config_name || '未选择')),
            h('div', '开机启动：' + (status.boot_enabled ? '已启用' : '未启用'))
          ]) : null
        ]),
        h('section', { style: style.card, attrs: { 'aria-label': '订阅额度与到期时间' } }, [
          h('div', { style: style.header }, [
            h('h2', { style: merge(style.name, { margin: '0', fontSize: '17px' }) }, '订阅用量'),
            button(subscriptionBusy ? '查询中…' : '刷新订阅信息', this.refreshSubscription, !status || subscriptionBusy, false)
          ]),
          h('div', { style: merge(style.choices, { marginTop: '16px', gap: '12px' }) }, [
            metric('剩余流量', available ? subscription.total > 0 ? bytes(remaining) : '未设置额度上限' : '—', true),
            metric('已用 / 总额度', available ? bytes(used) + ' / ' + (subscription.total > 0 ? bytes(subscription.total) : '未设置') : '—', false),
            metric(expired ? '到期时间 · 已到期' : '到期时间', subscription.expire === 0 ? '未设置到期时间' : date(subscription.expire), false)
          ]),
          available && subscription.total > 0 ? h('div', { style: { height: '8px', marginTop: '18px', background: 'rgba(128,128,128,.15)', borderRadius: '8px', overflow: 'hidden' }, attrs: { role: 'progressbar', 'aria-label': '订阅额度已用比例', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': Math.round(percent) } }, [
            h('div', { style: { width: percent + '%', height: '100%', background: percent >= 90 ? '#d18d34' : '#368ad9', borderRadius: '8px' } })
          ]) : null,
          h('div', { style: style.hint, attrs: { role: 'status', 'aria-live': 'polite' } }, available ? (subscription.total > 0 ? '已用 ' + percent.toFixed(1) + '%' : '累计用量 ' + bytes(used)) + ' · 服务商数据更新于 ' + date(subscription.updated_at) + (subscription.stale ? '（旧数据）' : '') : subscriptionBusy ? '正在向订阅服务查询额度，请稍候…' : '订阅信息暂不可用'),
          subscription.error ? h('div', { style: merge(style.hint, { color: '#d18d34' }) }, subscription.error + (available ? '，以上为上次成功取得的数据。' : '。')) : null,
          h('div', { style: style.hint }, '额度由订阅服务商返回，单位 GiB；页面打开时每 15 分钟自动检查。刷新信息不会下载或切换配置。')
        ]),
        h('section', { style: style.card, attrs: { 'aria-label': 'OpenClash 设置', 'aria-busy': this.busy ? 'true' : 'false' } }, [
          status && !status.installed ? h('div', { style: style.notice }, '尚未安装 OpenClash，请先安装后刷新。') : null,
          row('OpenClash', '保存后启动或停止代理服务，并同步开机启动设置。', toggle('enabled', 'OpenClash 开关')),
          row('策略模式', '规则：按规则分流；全局：全部走代理；直连：全部直接连接。', choices('mode', [['rule', '规则'], ['global', '全局'], ['direct', '直连']], '策略模式')),
          row('DNS 模式', 'Fake-IP 使用虚拟地址映射；Redir-Host 返回真实解析地址。切换后会重新加载服务。', choices('operation_mode', [['fake-ip', 'Fake-IP'], ['redir-host', 'Redir-Host']], 'DNS 模式')),
          row('IPv6 代理', 'IPv6 流量遵循当前策略模式；规则模式下按同一套规则分流。开启时同时启用 IPv6 DNS 解析。', toggle('ipv6_enabled', 'IPv6 代理开关'), true),
          this.busy ? h('div', { style: style.notice, attrs: { role: 'status', 'aria-live': 'polite' } }, '后台正在应用设置，每 3 秒读取一次实际状态，请稍候。') : null,
          error ? h('div', { style: merge(style.notice, { borderColor: 'rgba(207,72,72,.55)', color: '#d45b5b' }), attrs: { role: 'alert' } }, error) : null,
          this.resultMessage && !this.busy && !error ? h('div', { style: merge(style.notice, { borderColor: 'rgba(70,166,106,.4)' }), attrs: { role: 'status', 'aria-live': 'polite' } }, this.resultMessage) : null,
          h('div', { style: style.controls }, [
            button(this.busy ? '应用中…' : '保存并应用', this.apply, disabled || this.fetching || !this.dirty, true),
            button(this.fetching ? '刷新中…' : '刷新', this.refresh, this.busy || this.fetching, false),
            this.dirty ? button('撤销修改', this.discard, this.busy, false) : null,
            h('span', { style: { fontSize: '13px', opacity: '.65' } }, this.dirty && !this.busy ? '有未保存的更改' : this.lastUpdated ? '状态更新于 ' + this.lastUpdated : '')
          ])
        ]),
        h('section', { style: style.card, attrs: { 'aria-label': 'DNS 与高级配置' } }, [
          h('div', { style: style.name }, 'DNS 与高级配置'),
          dnsChain ? h('div', { style: merge(style.hint, { overflowWrap: 'anywhere' }) }, 'DNS 链路：' + dnsChain) : null,
          status ? h('div', { style: style.hint }, 'IPv6 DNS 解析：' + (status.ipv6_dns ? '已开启' : '已关闭')) : null,
          h('div', { style: style.hint }, '个人直连规则请在 OpenClash 自定义规则中配置；仅规则模式生效。'),
          h('div', { style: style.hint }, '控制面板可切换节点、查看连接与规则；如提示认证，请使用高级配置中的控制器密钥。'),
          h('div', { style: merge(style.controls, { marginTop: '12px' }) }, [
            h('a', {
              style: merge(style.button, merge(style.primary, { textDecoration: 'none', display: 'inline-flex', alignItems: 'center', opacity: status && status.running ? '1' : '.5', cursor: status && status.running ? 'pointer' : 'not-allowed' })),
              attrs: { href: status && status.running ? this.dashboardUrl : undefined, target: '_blank', rel: 'noopener noreferrer', 'aria-disabled': status && status.running ? 'false' : 'true', title: status && status.running ? '在新标签页打开 Clash 控制面板' : '请先开启 OpenClash 并等待核心运行' }
            }, 'Clash 控制面板 ↗'),
            h('a', { style: style.link, attrs: { href: 'http://' + (window.location.hostname.indexOf(':') >= 0 && window.location.hostname.charAt(0) !== '[' ? '[' + window.location.hostname + ']' : window.location.hostname) + ':8080/cgi-bin/luci/admin/services/openclash', target: '_blank', rel: 'noopener noreferrer' } }, 'OpenClash 高级配置 ↗'),
            h('a', { style: style.link, attrs: { href: '/#/adguardhome' } }, 'AdGuard Home 管理')
          ])
        ])
      ]);
    }
  };
})();
