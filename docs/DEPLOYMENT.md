# 部署对应与恢复边界

这是已有开发设备实现的**源码对应表**，不是承诺跨设备的一键安装流程。当前用户反馈还有多个故障；先读 README 的实验状态、依赖和已知限制。不要为了复现仓库而重装已经工作的路由器。

## 部署前

- 记录固件版本、当前中继/网口/DNS、防火墙和服务状态，确保有独立的 Wi-Fi/SSH 通道。
- 对下表准备修改的**具体文件**做 root-only 备份。配置备份可能含私人密码/订阅，绝不上传本仓库。
- 保存原 `/etc/rc.d/` 中相关启用链接的状态，以便回退启动设置。
- 下载和安装 OpenClash/核心、AGH 需使用各自官方渠道；本仓库未提供它们的下载器或完整配置。
- 本地私密凭据用环境变量或 SSH stdin 输入。不要在 README、shell history 或命令参数中写真实密码。

## 原厂网页和后台文件

| 仓库文件 | 设备位置 | 作用/注意事项 |
| --- | --- | --- |
| `gl-sdk4-ui-openclash.common.js` | `/www/views/gl-sdk4-ui-openclash.common.js` | 原厂 OpenClash 页面扩展 |
| `openclash-menu.json` | `/usr/share/oui/menu.d/openclash.json` | 应用菜单注册 |
| `openclash-rpc.lua` | `/usr/lib/oui-httpd/rpc/openclash` | OUI root 会话控制与状态 |
| `subscription.lua` | `/etc/mudi7-management/subscription.lua` | 订阅 metadata 缓存/查询 |
| `mudi7-subscription-info.lua` | `/usr/libexec/mudi7-subscription-info.lua` | 命令入口 |
| `mudi7-openclash.sh` | `/usr/libexec/mudi7-openclash` | 固定配置应用、等待和回退 |
| `mudi7-core-global.lua` | `/usr/libexec/mudi7-core-global.lua` | 核心全局策略应用 |
| `mudi7-core-apply.lua` | `/usr/libexec/mudi7-core-apply.lua` | 运行中核心配置应用 |
| `mudi7-dns-sync.sh` | `/usr/libexec/mudi7-dns-sync` | DNS 协同 shell 入口 |
| `mudi7-dns-sync.lua` | `/usr/libexec/mudi7-dns-sync.lua` | dnsmasq/AGH/核心与防火墙协同 |
| `mudi7-proxy.init` | `/etc/init.d/mudi7-proxy` | procd DNS 协同服务 |
| `openclash-dns-overwrite.rb` | `/etc/mudi7-management/openclash-dns-overwrite.rb` | 核心配置生成时调整 DNS |
| `openclash_custom_overwrite.sh` | 合并到 `/etc/openclash/custom/openclash_custom_overwrite.sh` | 仅调用上面的 Ruby 钩子；不可覆盖用户现有钩子 |
| `openclash_custom_firewall_rules.sh` | 合并到 `/etc/openclash/custom/openclash_custom_firewall_rules.sh` | DNS 排除/本机 ULA；发布版不含某台设备的前缀 |
| `mudi7-adguard-start.sh` | `/usr/libexec/mudi7-adguard-start` | AGH 启动协同；原厂 init 需按当前固件检查接入 |
| `adg.conf` | 合并到 `/etc/nginx/gl-conf.d/adg.conf` | 两个固定统计接口与通用控制 API 分开认证 |
| `mudi7-adguard-stats.lua` | `/usr/libexec/mudi7-adguard-stats.lua` | 原厂 Admin-Token 检查，注入本机后台授权 |
| `mudi7-adguard-top-five.lua` | `/usr/libexec/mudi7-adguard-top-five.lua` | 本机固定 API 查询/前五裁剪 |
| `adguard-rankings.lua` | `/etc/mudi7-management/adguard-rankings.lua` | 前五数据裁剪，保留原排序与其他字段 |

OpenClash/AGH 自身的 init、配置、原厂 AGH 菜单、核心、NGINX/OUI 框架均不随仓库打包，**仅按表复制文件不足以完整复现集成**。执行文件通常设为 755；RPC/库/view/menu 为 644；含凭据配置设为 600。每步先语法验证，再重载服务，检查日志和实际状态。

### 账户和个人规则辅助

`adguard-account.py` 使用 `ADGUARD_TASK_USERNAME` / `ADGUARD_TASK_PASSWORD`，生成用户 bcrypt 哈希及随机后台账户，通过 stdin 给 Ruby 配置辅助。默认用户名只是示例 `admin`，没有默认密码。此操作会改变 AGH 原配置/原厂 `--glinet` 认证行为；**应停止服务、备份相关文件并检查当前固件后再使用，不是独立的一键命令**。后台账户已存在时拒绝覆盖，不能反复执行。

Ruby 辅助文件应在设备上位于 `/tmp/mudi7-adguard-account.rb`（源 `adguard-account.rb`），授权保存为 `/etc/mudi7-management/adguard-api.authorization`，权限 600。如回退，账户配置、原厂 init 参数、NGINX 认证桥和后台授权需成套处理，不能只还原一个文件。

`adguard-configure.rb` 是当时的配置调整辅助，包含外部 DNS 示例。它不是通用推荐配置，不能在已有整合上盲目运行。启用代理时应由协同服务保持 AGH 上游为核心。

`personal-rules.rb` 安全合并一条 DOMAIN-SUFFIX / DIRECT，发布版使用 `example.com`。先修改为自己的域名并运行对应测试，再合并既有自定义规则；不替换订阅。规则模式生效，全局模式不保证该域名直连。

## 两类扫描

| 仓库文件 | 设备位置 |
| --- | --- |
| `radio-parse.lua` / `radio-scan.lua` | `/etc/mudi7-management/` 下同名 |
| `radio-scan-rpc.lua` | `/usr/lib/oui-httpd/rpc/radio-scan` |
| `mudi7-wifi-scan.lua` / `mudi7-cellular-scan.lua` | `/usr/libexec/` 下同名 |
| `radio-scan-menu.json` | `/usr/share/oui/menu.d/radio-scan.json` |
| `gl-sdk4-ui-radio-scan.common.js` | `/www/views/gl-sdk4-ui-radio-scan.common.js` |

已有基础集成时可用 `python deploy-radio.py` 上传这些文件。完成后原厂应用菜单显示“无线信号扫描”。设备 CLI：

```sh
lua /usr/libexec/mudi7-wifi-scan.lua status
lua /usr/libexec/mudi7-wifi-scan.lua scan
lua /usr/libexec/mudi7-cellular-scan.lua status
lua /usr/libexec/mudi7-cellular-scan.lua scan
```

`scan` 启动异步任务并立即返回。两类扫描全局互斥，完成后最短冷却 20 秒，无自动扫描历史。结果存 RAM，重启清空。

蜂窝通过现有 modem.CPU.AT 守护进程，只查询 QENG serving/neighbour 与 COPS?；不能将屏幕显示的 SIM 槽位直接作为 AT 的 sub_id。当前实现 sub_id=0 的语义基于开发设备，不承诺其他模组相同。

## 屏幕

安装助手把 `screen-custom` 的运行文件和 `screen-upstream` 的驱动/监听复制到 `/root/dashboard/`，权限受限；`citydash`、`homebutton` 放到 `/etc/init.d/`。

| 文件 | 用途 |
| --- | --- |
| `main.py` | 正确入口，调用自定义 UI |
| `mudi_ui.py` | 画面、触摸分发、页面、锁屏和确认 |
| `backend.py` | 固定本机 API、PIN/账户读取、节点/网口/中继操作 |
| `repeater-connect.lua` | stdin 传入连接参数，UBUS 固定桥接 |
| `run.sh` | 退出重启与三次崩溃回退 |
| `toggle.sh` | 启停与原厂切换，读取实际 procd 状态 |
| `prepare-live.py` | PIN 检查和背光值保存 |
| `dashboard.py` | 未拆分上游底层依赖，不是本套件入口 |
| `button_watch.py` / `screen_sleep.sh` | 电源键监听和背光控制 |

`verify-device.py` 会断言现有 PIN、代理、AGH、中继和策略组可用；若当前场景不符合这些前提则安装验证失败，不是允许绕过的理由。它还生成**真实数据**预览到 `/tmp/mudi7-screen-render/`，只能私下查看，不能公开上传。

## 检查与回退

基础只读检查可分别执行 `nginx -t`、Lua `loadfile`、Python `py_compile`、`toggle.sh status`、现有 OpenClash/AGH 状态以及真实网络/DNS 请求。完整网络修改请在实体设备逐项测试并记录，不能用离线图片代替。

只恢复屏幕：`/root/dashboard/toggle.sh off`。停止电源键切换可停止/禁用 homebutton；先确认原厂屏幕已启动。

要移除扩展时，按表逐个恢复备份/删除确知新增文件和保留项，再检查/重载有关服务。**不要**直接恢复整个 `/etc` 或递归删除大目录。保留后续用户改动。

固件升级前切回原厂并备份。`sysupgrade.paths` 只是追加的源码保留项，不含用户的 AGH/订阅/UCI 配置；应自行确认这些配置的官方保留机制。保留了源码也不代表新固件的内部接口仍兼容。
