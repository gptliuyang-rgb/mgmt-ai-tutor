# Arxiv Daily Digest (ainewspaper)

一个免费的 Arxiv AI 论文日报站点：

- 模块 1：具身智能（VLA / 世界模型 / 机器人）
- 模块 2：大语言模型、AI Agent、算法相关

## 已实现功能

- 每日自动抓取 Arxiv 分类：`cs.AI`、`cs.LG`、`cs.RO`、`cs.HC`
- 生成字段：标题、作者、作者单位（优先 Arxiv 元数据，缺失时尝试 Semantic Scholar）、摘要、发布时间、PDF 链接、主要图片（含 fallback）
- 自动摘要：方法总结 + 结论总结（默认轻量规则；可选 `HF_API_TOKEN` 调 HuggingFace 免费推理）
- 静态站点：
  - 首页按日期浏览
  - 两个模块分栏展示
  - 论文详情页（原始摘要 + AI 摘要 + 图片 + PDF）
- 交互：
  - 点赞（本地存储）
  - 收藏（本地存储）
  - 评论系统：Utterances（GitHub 登录）
- 自动化：
  - `daily-digest.yml`：每天 UTC 00:00 更新数据
  - `deploy-pages.yml`：推送到 `main` 自动部署 GitHub Pages

## 本地运行

```bash
python scripts/build_digest.py --max-results 36
python -m http.server 8000
```

打开 <http://localhost:8000>。

如果你希望用 Node 启动静态服务（与 Render Docker 部署一致）：

```bash
node server.js
```

默认监听 `3000`，也可以通过 `PORT` 环境变量覆盖。

## GitHub Pages 发布流程（仓库名：`ainewspaper`）

1. 在 GitHub 创建公开仓库 `ainewspaper`。
2. 推送本项目代码到该仓库的 `main` 分支。
3. 在仓库 `Settings -> Pages` 中确认 Source 为 **GitHub Actions**。
4. 在 `Actions` 页面运行 `Build Arxiv Daily Digest`（生产数据）和 `Deploy static site to GitHub Pages`（发布页面）。
5. 发布后访问：
   - 项目站点：`https://<你的用户名>.github.io/ainewspaper/`
   - 若仓库名是 `<你的用户名>.github.io`，则域名是：`https://<你的用户名>.github.io/`

## 评论系统启用（Utterances）

1. 打开 <https://github.com/apps/utterances> 并安装到你的仓库（例如 `gptliuyang-rgb/mgmt-ai-tutor`）。
2. 等待 1~2 分钟后刷新论文详情页。
3. 首次评论会自动创建对应 issue 线程。
