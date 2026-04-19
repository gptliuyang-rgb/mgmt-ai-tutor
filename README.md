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

## GitHub Pages 发布流程（仓库名：`ainewspaper`）

1. 在 GitHub 创建公开仓库 `ainewspaper`。
2. 推送本项目代码到该仓库的 `main` 分支。
3. 在仓库 `Settings -> Pages` 中确认 Source 为 **GitHub Actions**。
4. 在 `Actions` 页面运行 `Build Arxiv Daily Digest`（生产数据）和 `Deploy static site to GitHub Pages`（发布页面）。
5. 发布后访问：
   - 项目站点：`https://<你的用户名>.github.io/ainewspaper/`
   - 若仓库名是 `<你的用户名>.github.io`，则域名是：`https://<你的用户名>.github.io/`


## 每天自动更新（一步一步配置）

如果你遇到“网站不自动更新”，按下面顺序操作：

1. **确认默认分支是 `main`**
   - GitHub 仓库 -> `Settings` -> `General` -> `Default branch`。
2. **开启 Actions 权限**
   - `Settings` -> `Actions` -> `General`：
   - 勾选 `Allow all actions and reusable workflows`；
   - 在 `Workflow permissions` 里勾选 **Read and write permissions**；
   - 勾选 `Allow GitHub Actions to create and approve pull requests`（建议开启）。
3. **确认定时任务工作流已在默认分支**
   - 文件路径：`.github/workflows/daily-digest.yml`；
   - 该工作流已配置 UTC `00:00` + `00:30` 两次触发（第二次是兜底重试）。
4. **手动跑一次，验证链路**
   - 仓库 -> `Actions` -> `Build Arxiv Daily Digest` -> `Run workflow`；
   - 确认日志里出现 `Build digest`、`Commit data update` 并成功 `git push`。
5. **确认部署工作流会被触发**
   - 数据提交到 `main` 后，`Deploy static site to GitHub Pages` 会自动运行；
   - 若未触发，手动点一次 `Run workflow`。
6. **验证线上更新时间**
   - 打开 `https://<你的用户名>.github.io/<仓库名>/data/latest.json`；
   - 检查 `generated_at` 是否是当天 UTC 时间。
7. **如果仍失败，先看最常见两类报错**
   - `Permission denied to github-actions[bot]`：通常是第 2 步没开写权限。
   - `Updates were rejected`：通常是分支保护阻止直接 push。需要在 `Branch protection rules` 允许 Actions 推送，或者改成 PR 模式。

## 评论系统启用（Utterances）

1. 打开 <https://github.com/apps/utterances> 并安装到你的仓库（例如 `gptliuyang-rgb/mgmt-ai-tutor`）。
2. 等待 1~2 分钟后刷新论文详情页。
3. 首次评论会自动创建对应 issue 线程。


## 图片加载修复说明

- 现在构建脚本会优先抓取论文 `fig.1`（来自 `https://arxiv.org/html/<paper_id>` 的 Figure 1），并保存到 `data/images/`，前端直接使用仓库内静态文件链接，避免外链图片失效。
- 若抓不到原图，会自动生成本地 SVG 占位图，保证页面每个论文都有可显示图片。

## 常见问题：更新分支提示“不支持二进制文件”

这个报错通常出现在 **GitHub 网页端冲突编辑器**：它不能在线合并 `png/jpg` 这类二进制文件。

推荐做法（命令行，最稳）：

```bash
# 1) 拉取最新
git fetch origin

# 2) 切到你的分支
git checkout <your-branch>

# 3) 合并 main（遇到二进制冲突时保留当前分支或 main 的版本）
git merge origin/main

# 若冲突在 data/images/*.png 或 *.jpg，二选一：
# 保留当前分支版本：
git checkout --ours data/images/*
# 或保留 main 版本：
git checkout --theirs data/images/*

# 4) 标记已解决并提交
git add -A
git commit -m "Resolve binary image conflicts"
```

本仓库已添加 `.gitattributes` 将 `data/images/*.png`、`data/images/*.jpg` 标记为二进制文件，避免 Git 把它们当文本补丁处理。

### 根因与彻底修复（本仓库已执行）

- 根因不是 GitHub Pages 本身，而是**PR 分支里包含了大量自动生成的 `png/jpg` 文件**；当你在网页上点 `Update branch`，GitHub 的网页冲突编辑器无法处理这类二进制冲突。
- 解决策略：**不再把生成的二进制图片提交进仓库**。现在脚本会优先写入远程图片 URL，失败时只生成本地 `svg` 占位图（纯文本），避免再次出现该类冲突。

如果你的旧分支已经卡住，按下面步骤一次性清理：

```bash
git checkout <your-branch>
git fetch origin
git merge origin/main

# 删除历史遗留的二进制图（仅需一次）
git rm --cached data/images/*.png data/images/*.jpg 2>/dev/null || true

# 拉最新数据（会生成 remote URL + svg，不再产出 png/jpg）
python3 scripts/build_digest.py --max-results 36

git add -A
git commit -m "chore: remove generated binary images"
git push origin <your-branch>
```
