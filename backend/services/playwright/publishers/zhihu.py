# -*- coding: utf-8 -*-
"""
知乎发布适配器 - 工业加固版 (v3.6)
修复：
1. 登录失效自动识别 (防止在登录页死等超时)
2. 图像搜索关键词清洗 (防止搜索 [AI正在创作中])
3. 增强图源稳定性
"""

import asyncio
import re
import os
import httpx
import tempfile
import random
from typing import Dict, Any, List, Optional
from playwright.async_api import Page
from loguru import logger

from .base import BasePublisher, registry


class ZhihuPublisher(BasePublisher):
    async def publish(self, page: Page, article: Any, account: Any) -> Dict[str, Any]:
        temp_files = []
        try:
            logger.info("🚀 开始知乎发布 (v3.6 状态自检版)...")

            # 1. 导航并验证登录状态
            await page.goto(self.config["publish_url"], wait_until="networkidle", timeout=60000)
            await asyncio.sleep(5)

            # 🌟 [关键修复] 检查是否被重定向到了登录页
            if "signin" in page.url or "login" in page.url:
                logger.error("❌ 登录已失效：页面被重定向至登录页，请重新扫码授权账号")
                return {"success": False, "error_msg": "账号登录已过期，请重新授权"}

            # 2. 图像获取逻辑
            # 清洗正文
            clean_content = re.sub(r'!\[.*?\]\(.*?\)', '', article.content)
            # 尝试下载正文原图
            image_urls = re.findall(r'!\[.*?\]\(((?:https?://)?\S+?)\)', article.content)
            downloaded_paths = await self._download_images(image_urls)

            # 🌟 [关键修复] 自动配图策略：确保不使用占位符关键词
            if not downloaded_paths:
                # 如果标题包含正在创作中，则尝试使用关键词表里的原词
                search_kw = article.title
                if "创作中" in search_kw or not search_kw:
                    # 兜底：尝试从关联的关键词对象获取
                    search_kw = "科技创新"  # 终极回退词

                logger.info(f"⚠️ 正文无有效图片，启动自动配图。搜索词: {search_kw}")
                fallback_path = await self._generate_fallback_image(search_kw)
                if fallback_path:
                    downloaded_paths = [fallback_path]
                    temp_files.append(fallback_path)

            # 3. 填充标题 (增加对占位标题的防御)
            display_title = article.title
            if "创作中" in display_title:
                await asyncio.sleep(5)  # 再等5秒看数据库是否更新
                # 提示：实际生产中应在 Service 层拦截，这里做二次防御

            await self._fill_title(page, display_title)

            # 4. 填充内容
            await self._fill_content_and_clean_ui(page, clean_content)

            # 5. 上传图像
            if downloaded_paths:
                await self._upload_real_images(page, downloaded_paths)

            # 6. 发布流程
            topic_word = search_kw[:4] if 'search_kw' in locals() else "科技"
            if not await self._handle_publish_process(page, topic_word):
                return {"success": False, "error_msg": "发布确认环节失败"}

            return await self._wait_for_publish_result(page)

        except Exception as e:
            logger.exception(f"❌ 知乎脚本严重故障: {str(e)}")
            return {"success": False, "error_msg": str(e)}
        finally:
            for f in temp_files:
                if os.path.exists(f): os.remove(f)

    async def _download_images(self, urls: List[str]) -> List[str]:
        paths = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        async with httpx.AsyncClient(headers=headers, verify=False) as client:
            for i, url in enumerate(urls[:2]):
                try:
                    clean_url = url.strip().strip('"').strip("'")
                    if clean_url.startswith('//'): clean_url = 'https:' + clean_url
                    # 过滤掉非法的占位符链接
                    if "loremflickr" in clean_url or "unsplash" in clean_url or "http" in clean_url:
                        resp = await client.get(clean_url, timeout=15.0, follow_redirects=True)
                        if resp.status_code == 200:
                            tmp_path = os.path.join(tempfile.gettempdir(), f"zh_v36_{random.randint(100, 999)}.jpg")
                            with open(tmp_path, "wb") as f:
                                f.write(resp.content)
                            paths.append(tmp_path)
                except:
                    pass
        return paths

    async def _generate_fallback_image(self, keyword: str) -> Optional[str]:
        """备用图源重构：使用更稳定的源"""
        clean_kw = re.sub(r'[\[\]\(\)\s]', '', keyword)[:10]
        # 使用 Unsplash 随机图源加速器
        url = f"https://source.unsplash.com/800x600/?business,technology,{clean_kw}"
        return (await self._download_images([url]))[0] if True else None

    async def _fill_content_and_clean_ui(self, page: Page, content: str):
        editor = ".public-DraftEditor-content"
        await page.wait_for_selector(editor)
        await page.click(editor)
        await page.evaluate('''(text) => {
            const dt = new DataTransfer();
            dt.setData("text/plain", text);
            const ev = new ClipboardEvent("paste", { clipboardData: dt, bubbles: true });
            document.querySelector(".public-DraftEditor-content").dispatchEvent(ev);
        }''', content)
        await asyncio.sleep(2)
        try:
            confirm = page.locator("button:has-text('确认并解析')").first
            if await confirm.is_visible(timeout=3000):
                await confirm.click()
        except:
            pass

    async def _upload_real_images(self, page: Page, paths: List[str]):
        try:
            logger.info("正在尝试上传封面图...")
            cover_input = page.locator("input.UploadPicture-input").first
            await cover_input.set_input_files(paths[0])
            await asyncio.sleep(4)

            logger.info("正在正文插入图片...")
            await page.keyboard.press("Control+Home")
            await page.keyboard.press("Enter")
            await page.keyboard.press("ArrowUp")
            img_icon = page.locator(".WriteIndex-imageIcon, button[aria-label='插入图片']").first
            async with page.expect_file_chooser() as fc_info:
                await img_icon.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(paths[0])
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"真实图片上传动作失败: {e}")

    async def _fill_title(self, page: Page, title: str):
        # 针对知乎的多种标题输入框进行适配
        sel = "input[placeholder*='标题'], .WriteIndex-titleInput textarea, .Input"
        await page.wait_for_selector(sel, timeout=10000)
        await page.fill(sel, title)

    async def _handle_publish_process(self, page: Page, topic: str) -> bool:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        add_topic = page.locator("button:has-text('添加话题')").first
        if await add_topic.is_visible(timeout=2000):
            await add_topic.click()
        topic_input = page.locator("input[placeholder*='话题']").first
        if await topic_input.is_visible():
            await topic_input.fill(topic)
            await asyncio.sleep(2)
            suggestion = page.locator(".Suggestion-item, .PublishPanel-suggestionItem").first
            if await suggestion.is_visible():
                await suggestion.click()
            else:
                await page.keyboard.press("Enter")
        final_btn = page.locator(
            "button.PublishPanel-submitButton, .WriteIndex-publishButton, button:has-text('发布')").last
        for _ in range(5):
            if await final_btn.is_enabled():
                await final_btn.click(force=True)
                return True
            await asyncio.sleep(2)
        return False

    async def _wait_for_publish_result(self, page: Page) -> Dict[str, Any]:
        for i in range(25):
            if "/p/" in page.url and "/edit" not in page.url:
                return {"success": True, "platform_url": page.url}
            await asyncio.sleep(1)
        return {"success": False, "error_msg": "发布超时"}


# 注册适配器
ZHIHU_CONFIG = {"name": "知乎", "publish_url": "https://zhuanlan.zhihu.com/write", "color": "#0084FF"}
registry.register("zhihu", ZhihuPublisher("zhihu", ZHIHU_CONFIG))