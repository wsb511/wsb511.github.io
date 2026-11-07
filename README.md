# WSB Utilities 静态网站

GitHub Pages 静态站点，自定义域名见 `CNAME`（`app.wsb511.abrdns.com`）。没有构建步骤，也没有自建后端。站点包含三部分：

## 1. 产品说明与合规页面

- `index.html`：WSB Utilities 介绍与导航。
- `privacy.html`：隐私政策。
- `terms.html`：服务条款。

修改隐私政策和服务条款前，要先确认产品的真实行为。

## 2. 中文新闻标题 RSS（`rss/`）

- 四个订阅源：`cnbc.xml`、`barrons.xml`、`electrek.xml`、`eletricvehicles.xml`。只包含中文标题和原文链接。订阅入口页是 `rss/index.html`。
- 采集和翻译由外部 Apps Script 服务完成。**日常自动更新**由外部发布程序直接提交到 `main`，提交信息为 “Refresh Chinese RSS snapshots directly”。
- `.github/workflows/rss.yml` 是旧的备用工作流，**只能手动触发**。它先跑 `rss/test_sync.py`，再用 `rss/sync.py` 拉取快照并校验来源域名、标题、GUID 和时间戳。校验失败就保留旧快照，不会用错误页覆盖订阅源。
- 订阅地址有两种：Pages 地址和 `raw.githubusercontent.com` 直链。Feedly 用直链。FT 自制订阅源已在 PR #8 中移除。

## 3. 记忆库导入页（`memory/`）

- `memory/index.html`：在浏览器本地解析 Claude / ChatGPT 官方导出包，登录后写入本人的 Supabase 记忆库。用户消息存全文，AI 回答只存前 500 字。重复导入不会产生重复记录。
- `memory/convert.js`：导出包解析逻辑，不发任何网络请求。
- 页面里只有 Supabase 的公开（publishable）密钥。访问权限由登录身份控制，只有记忆库主人的邮箱能导入。仓库不保存私密凭据，也不保存用户数据。

## 本地检查

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

确认 `/`、`/privacy.html`、`/terms.html`、`/rss/`、`/memory/` 都返回 200。RSS 发布程序的测试：

```sh
python3 -m unittest discover -s rss -p 'test_sync.py'
```

本地检查通过，不代表线上的 Pages、DNS 和 HTTPS 已经生效。

## 工作收尾与同步

完成一段可保存的工作后，默认提交并推送到工作分支。不要因为等审计或合并，就把改动长期留在聊天工作区。没做完的工作也可以作为 WIP 提交保存到分支上。只提交本次任务的文件，不混入用户的其他修改。凭据和业务数据不提交。

只要有可审查的改动，就创建或更新 PR（没做完时用草稿 PR）。合并和上线由审计和 CI 把关。每次交付都要说清楚：分支是否已推送、PR 链接、CI 和审查状态、是否已合并或上线，以及还有哪些文件没推送、原因是什么。推送失败时要报告具体卡在哪里，不能把本地保存当成已同步。
