# AstrBot Plugin Git Sync

一个用于 [AstrBot](https://github.com/Soulter/AstrBot) 的插件，支持将本地文件（如配置文件、数据文件）同步到 GitHub 仓库，支持上传、下载及自动定时备份。

## ✨ 功能特性

*   **多文件同步**：支持配置多个本地文件路径进行同步。
*   **双向同步**：
    *   **上传 (Upload)**：将本地文件备份到 GitHub 仓库。
    *   **下载 (Download)**：从 GitHub 仓库拉取文件覆盖本地。
*   **自动备份**：支持设置定时任务，自动将本地文件上传到 GitHub。
*   **选择性操作**：指令支持关键词过滤，可只同步特定文件。
*   **零配置路径**：远程仓库路径自动映射（例如 `/AstrBot/data/config.json` -> `repo/AstrBot/data/config.json`）。

## 📦 安装

1.  将本项目克隆或下载到 AstrBot 的插件目录 `data/plugins/astrbot_plugin_git_sync`。
2.  重启 AstrBot。

## ⚙️ 配置

在 AstrBot 管理面板的插件配置中填写以下信息：

| 配置项 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `github_token` | GitHub Personal Access Token (需要 `repo` 权限) | (必填) |
| `github_repo` | 目标仓库地址 (格式: `用户名/仓库名`) | (必填) |
| `sync_paths` | 需要同步的本地文件绝对路径列表 | `["/AstrBot/data/cmd_config.json"]` |
| `enable_auto_sync` | 是否开启自动定时上传 | `false` |
| `sync_interval` | 自动同步间隔 (分钟) | `60` |

### 🚀 快速触发 (仅在配置面板有效)

*   `trigger_upload`: 勾选并保存后，立即执行一次全量上传。
*   `trigger_download`: 勾选并保存后，立即执行一次全量下载。

## 💻 指令使用

### 1. 上传文件 (Backup)

```bash
/git_upload             # 上传所有配置的文件
/git_upload config      # 只上传路径中包含 "config" 的文件
```

### 2. 下载文件 (Restore)

```bash
/git_download           # 下载所有配置的文件
/git_download cmd       # 只下载路径中包含 "cmd" 的文件
```

**注意**：如果是恢复核心配置文件（如 `cmd_config.json`），下载完成后需要**重启 AstrBot 容器**才能生效。

## 📝 License

MIT
