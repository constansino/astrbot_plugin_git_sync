import base64
import json
import os
import asyncio
import aiohttp
import re
from astrbot.api.star import Context, Star, register
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api import logger, AstrBotConfig

@register("astrbot_plugin_git_sync", "Gemini", "Sync local files to GitHub", "1.3.0")
class GitSyncPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._task = None
        
        # Check for auto-sync on startup
        if self._get_config("enable_auto_sync", False):
            self._task = asyncio.create_task(self._auto_sync_loop())
            logger.info("Git Sync: Auto-sync enabled.")

        # Check for manual triggers from settings
        if self._get_config("trigger_upload", False):
            asyncio.create_task(self._perform_upload(is_auto=True))
        if self._get_config("trigger_download", False):
            asyncio.create_task(self._perform_download(is_auto=True))

    def _get_config(self, key, default=None):
        return self.config.get(key, default)

    async def terminate(self):
        """Cleanup on plugin unload"""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Git Sync: Plugin terminated.")

    def _sanitize_repo(self, repo: str) -> str:
        if not repo: return ""
        repo = re.sub(r'^https?://(www\.)?github\.com/', '', repo)
        repo = re.sub(r'\.git$', '', repo)
        return repo.strip().strip('/')

    def _filter_paths(self, sync_paths: list, keyword: str) -> list:
        """Filter paths based on keyword"""
        if not keyword or keyword.lower() == "all":
            return sync_paths
        
        filtered = [p for p in sync_paths if keyword.lower() in p.lower()]
        return filtered

    async def _auto_sync_loop(self):
        logger.info("Git Sync: Auto-sync loop started.")
        while True:
            try:
                interval = int(self._get_config("sync_interval", 60))
                if interval <= 0: interval = 60
                
                await asyncio.sleep(interval * 60)
                await self._perform_upload(is_auto=True)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Git Sync: Auto-sync error: {e}")
                await asyncio.sleep(60)

    async def _perform_upload(self, event: AstrMessageEvent = None, keyword: str = None, is_auto=False):
        token = self._get_config("github_token")
        repo = self._sanitize_repo(self._get_config("github_repo"))
        sync_paths = self._get_config("sync_paths", [])

        if isinstance(sync_paths, str): sync_paths = [sync_paths]

        if not token or not repo:
            msg = "配置错误: 缺少 GitHub Token 或 仓库信息"
            if event: yield event.plain_result(msg)
            else: logger.error(f"Git Sync: {msg}")
            return

        # Filter paths
        target_paths = self._filter_paths(sync_paths, keyword)
        if not target_paths:
            msg = f"没有匹配到包含 '{keyword}' 的文件路径" if keyword else "没有配置同步路径"
            if event: yield event.plain_result(msg)
            return

        results = []
        if event: yield event.plain_result(f"开始上传 {len(target_paths)} 个文件...")

        async with aiohttp.ClientSession() as session:
            for local_path in target_paths:
                local_path = local_path.strip()
                if not local_path: continue
                
                remote_path = local_path.lstrip('/').replace('\\', '/')
                
                if not os.path.exists(local_path):
                    msg = f"❌ (跳过) 本地不存在: {local_path}"
                    results.append(msg)
                    continue

                try:
                    with open(local_path, "rb") as f:
                        content = f.read()
                    content_b64 = base64.b64encode(content).decode("utf-8")

                    headers = {
                        "Authorization": f"token {token}",
                        "Accept": "application/vnd.github.v3+json"
                    }
                    url = f"https://api.github.com/repos/{repo}/contents/{remote_path}"

                    # Get SHA
                    sha = None
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            sha = data.get("sha")
                        elif resp.status == 401:
                            msg = f"❌ Token 无效"
                            results.append(msg)
                            break
                    
                    # Upload
                    payload = {
                        "message": f"Update {remote_path} via AstrBot",
                        "content": content_b64
                    }
                    if sha: payload["sha"] = sha
                    
                    async with session.put(url, headers=headers, json=payload) as resp:
                        if resp.status in [200, 201]:
                            msg = f"✅ 上传成功: {remote_path}"
                            results.append(msg)
                            if is_auto: logger.info(f"Git Sync: {msg}")
                        else:
                            text = await resp.text()
                            msg = f"❌ 上传失败 {remote_path}: {resp.status}"
                            results.append(msg)
                            if is_auto: logger.error(f"Git Sync: {msg} - {text}")

                except Exception as e:
                    msg = f"❌ 异常 {remote_path}: {e}"
                    results.append(msg)
                    if is_auto: logger.error(f"Git Sync: {msg}")

        if event:
            yield event.plain_result("\n".join(results))

    async def _perform_download(self, event: AstrMessageEvent = None, keyword: str = None, is_auto=False):
        token = self._get_config("github_token")
        repo = self._sanitize_repo(self._get_config("github_repo"))
        sync_paths = self._get_config("sync_paths", [])
        
        if isinstance(sync_paths, str): sync_paths = [sync_paths]

        if not token or not repo:
            if event: yield event.plain_result("配置错误: 缺少 Token 或 仓库信息")
            return

        target_paths = self._filter_paths(sync_paths, keyword)
        if not target_paths:
            if event: yield event.plain_result("没有匹配的文件路径")
            return

        results = []
        need_restart = False
        
        if event: yield event.plain_result(f"开始下载 {len(target_paths)} 个文件...")

        async with aiohttp.ClientSession() as session:
            for local_path in target_paths:
                local_path = local_path.strip()
                if not local_path: continue
                
                remote_path = local_path.lstrip('/').replace('\\', '/')
                url = f"https://api.github.com/repos/{repo}/contents/{remote_path}"
                headers = {
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json"
                }

                try:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            content_b64 = data.get("content", "").replace("\n", "")
                            
                            try:
                                content = base64.b64decode(content_b64)
                                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                                with open(local_path, "wb") as f:
                                    f.write(content)
                                msg = f"✅ 下载成功: {local_path}"
                                results.append(msg)
                                
                                # Check if core config
                                if "cmd_config.json" in local_path:
                                    need_restart = True
                                    
                            except Exception as e:
                                msg = f"❌ 写入失败 {local_path}: {e}"
                                results.append(msg)
                        else:
                            msg = f"❌ 下载失败 {remote_path}: {resp.status}"
                            results.append(msg)
                except Exception as e:
                     msg = f"❌ 异常 {remote_path}: {e}"
                     results.append(msg)

        final_msg = "\n".join(results)
        if need_restart:
            final_msg += "\n\n⚠️ 检测到核心配置文件已更新，请重启 AstrBot 容器以生效。"
            
        if event:
            yield event.plain_result(final_msg)

    @filter.command("git_upload")
    async def upload_file(self, event: AstrMessageEvent, keyword: str = ""):
        '''手动上传。用法: /git_upload [关键词] (不填则上传所有)'''
        async for result in self._perform_upload(event=event, keyword=keyword):
            yield result

    @filter.command("git_download")
    async def download_file(self, event: AstrMessageEvent, keyword: str = ""):
        '''手动下载。用法: /git_download [关键词] (不填则下载所有)'''
        async for result in self._perform_download(event=event, keyword=keyword):
            yield result
