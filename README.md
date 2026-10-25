# WSB Utilities 静态网站

本仓库提供产品介绍、隐私政策与服务条款三个静态 HTML 页面，无构建步骤或应用后端。

- `index.html`：介绍与导航。
- `privacy.html`：隐私政策。
- `terms.html`：服务条款。
- `CNAME`：自定义域名 `app.wsb511.abrdns.com`。

## 本地检查

在仓库根目录运行：

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

用本机 HTTP 请求检查 `/index.html`、`/privacy.html`、`/terms.html` 返回 200，并核对导航、页面正文和语言。当前云环境已验证这三个页面可以本地读取；这不证明线上 Pages、DNS 或 HTTPS 配置生效。

## 修改与发布

通过分支和 PR 修改页面，隐私与条款变化须按真实产品行为核实。本仓库不是五个 Apps Script Agent 之一，没有它们的审查/部署脚本。仓库内未见 Pages 发布工作流；线上发布来源与域名绑定需在 GitHub Pages 设置确认，不推测已经自动发布。仓库不保存用户数据或服务凭据。
