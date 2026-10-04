# 来源、许可证与未打包依赖

## 屏幕上游

- 仓库：https://github.com/robavionix/gl-e5800-dashboard
- 固定提交：`e01ee320eb42db46b75468fc854a21a740bac75e`
- 许可证：MIT，保留 `Copyright (c) 2026 robavionix`，原文位于根目录及 `screen-upstream/LICENSE`。
- 保留文件：`dashboard.py`、`button_watch.py`、`screen_sleep.sh`、`homebutton`。
- 重用范围：framebuffer、触摸、电池、背光/电源监听；主程序入口为 `screen-custom/main.py`，不是上游整套 UI 入口。

上游 `dashboard.py` 保留为未拆分依赖，文件中还有未启用的上游功能；不要直接运行它来替代本项目入口。

## 外部依赖

OpenClash、Mihomo、AdGuard Home、NumPy、Pillow、Paramiko、bcrypt、Lupa、Playwright、OpenWrt 和 GL.iNet 固件均保持各自的许可证。本仓库不分发代理核心、节点配置、AGH 二进制或原厂系统。

OpenClash 自定义覆盖文件仅保存本项目自己的调用钩子，没有复制其完整示例模板。安装时与既有用户钩子合并。

## 原厂资源

原厂字体、壁纸、闭源 gl_screen 及 OUI 框架不包含在源码包中。运行时从用户自己安装的固件读取；文档截图仅展示该界面的表现，相关品牌和素材权利仍属于原权利人。不能把本项目的 MIT 文件视为分发厂商素材的授权。
