# Arxiv Daily Digest

一个免费的 Arxiv AI 论文日报站点：

- 模块 1：具身智能（VLA / 世界模型 / 机器人）
- 模块 2：大语言模型、AI Agent、算法相关

## 已实现功能

- 每日自动抓取 Arxiv 分类：`cs.AI`、`cs.LG`、`cs.RO`、`cs.HC`
- 生成字段：标题、作者、摘要、发布时间、PDF 链接、主要图片（含 fallback）
- 自动摘要：方法总结 + 结论总结（优先 `t5-small`，失败时自动降级到轻量规则摘要）
- 静态站点：
  - 首页按日期浏览
  - 两个模块分栏展示
  - 论文详情页（原始摘要 + AI 摘要 + 图片 + PDF）
- 交互：
  - 点赞（本地存储）
  - 收藏（本地存储）
  - 评论系统：Giscus（GitHub 登录）
- 自动化：GitHub Actions 每天 UTC 00:00 运行并提交新数据

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/build_digest.py --max-results 20
python -m http.server 8000
```

打开 <http://localhost:8000>。

## GitHub Pages 部署

1. 推送仓库到 GitHub。
2. 在仓库 `Settings -> Pages`，选择 `Deploy from branch`，分支选择 `main`（或当前分支）根目录。
3. 确保 Actions 工作流正常运行（首次可手动触发 `workflow_dispatch`）。

## 配置 Giscus

在 `app.js` 中替换下列占位符：

- `<YOUR_GITHUB_NAME>/<YOUR_REPO>`
- `<YOUR_REPO_ID>`
- `<YOUR_CATEGORY_ID>`

这些值可在 <https://giscus.app/zh-CN> 生成。
