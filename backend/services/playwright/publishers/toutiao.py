# -*- coding: utf-8 -*-
"""
今日头条 (头条号) 发布适配器 - v4.0 强力交互版
修复：
1. 解决标题填充超时：使用物理坐标点击 + 极限字数剪裁 (20字)
2. 侧边栏深度清理：确保“创作助手”不干扰输入
3. 增强发布按钮判定：适配“预览并发布”红色按钮
"""

import asyncio
import os
import re
import httpx
import tempfile
import random
from typing import Dict, Any, List, Optional
from playwright.async_api import Page
from loguru import logger
from .base import BasePublisher, registry


class ToutiaoPublisher(BasePublisher):
    async def publish(self, page: Page, article: Any, account: Any) -> Dict[str, Any]:
        temp_files = []
        try:
            logger.info("🚀 开始今日头条发布流程 (v4.0 强力交互版)...")

            # 1. 导航与充分等待
            await page.goto(self.config["publish_url"], wait_until="networkidle", timeout=60000)
            await asyncio.sleep(10)  # 增加到 10s 确保 Heavy Editor 加载完毕

            # 2. UI 强力清理
            await self._clean_toutiao_ui_v4(page)

            # 3. 标题极限剪裁 (今日头条 20 字以内最容易通过校验)
            raw_title = article.title.replace("#", "").strip()
            safe_title = raw_title[:20]
            logger.info(f"📝 极限剪裁标题: {safe_title}")

            # 4. 图片准备 (必须有封面)
            image_urls = re.findall(r'!\[.*?\]\(((?:https?://)?\S+?)\)', article.content)
            clean_content = re.sub(r'!\[.*?\]\(.*?\)', '', article.content)

            # 备用图源
            fallback_urls = [f"https://source.unsplash.com/800x600/?tech,drone,{random.randint(1, 50)}"]
            downloaded_paths = await self._download_images(image_urls + fallback_urls)
            temp_files.extend(downloaded_paths)

            # 5. 强力填充标题
            if not await self._fill_title_v4(page, safe_title):
                return {"success": False, "error_msg": "标题填充失败 (物理坐标激活无效)"}

            # 6. 填充正文
            if not await self._fill_content_v4(page, clean_content):
                return {"success": False, "error_msg": "正文填充失败"}

            # 7. 封面上传 (头条号命门)
            if downloaded_paths:
                await self._upload_mandatory_cover_v4(page, downloaded_paths[0])
            else:
                logger.warning("未获得有效封面，发布按钮可能无法激活")

            # 8. 发布确认
            if not await self._handle_final_publish_v4(page):
                return {"success": False, "error_msg": "发布按钮点击无效 (可能字数或封面不达标)"}

            return await self._wait_for_publish_result(page)

        except Exception as e:
            logger.exception(f"❌ 今日头条发布异常: {str(e)}")
            return {"success": False, "error_msg": str(e)}
        finally:
            for f in temp_files:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass

    async def _clean_toutiao_ui_v4(self, page: Page):
        """深度清理干扰"""
        try:
            # 关闭侧边栏“头条创作助手”
            close_selectors = [".byte-icon--close", ".creation-helper-close", "[class*='close']", ".add-desktop-close"]
            for sel in close_selectors:
                elements = page.locator(sel)
                count = await elements.count()
                for i in range(count):
                    if await elements.nth(i).is_visible():
                        await elements.nth(i).click()

            # 点击页面中心一下，消除可能的透明蒙层
            await page.mouse.click(640, 400)
            logger.info("✅ UI 干扰初步清理完成")
        except:
            pass

    async def _fill_title_v4(self, page: Page, title: str) -> bool:
        """物理坐标激活 + 模拟打字"""
        try:
            # 1. 尝试使用多种选择器定位
            sel = "textarea[placeholder*='标题'], .title-input textarea, .byte-input__inner"
            title_el = page.locator(sel).first

            # 2. 物理坐标激活 (核心：直接点标题大约所在的位置)
            await page.mouse.click(400, 220)
            await asyncio.sleep(1)

            if await title_el.is_visible(timeout=5000):
                await title_el.click(force=True)
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                await page.keyboard.type(title, delay=100)
                logger.info("✅ 标题填充成功")
                return True
            return False
        except:
            return False

    async def _fill_content_v4(self, page: Page, content: str) -> bool:
        """正文填充"""
        try:
            editor = page.locator(".ProseMirror").first
            await editor.click(force=True)
            await page.evaluate('''(args) => {
                const el = document.querySelector(args.sel);
                el.innerHTML = ''; 
                const dt = new DataTransfer();
                dt.setData("text/plain", args.text);
                const ev = new ClipboardEvent("paste", { clipboardData: dt, bubbles: true });
                el.dispatchEvent(ev);
            }''', {"sel": ".ProseMirror", "text": content})
            await page.keyboard.press("Enter")
            return True
        except:
            return False

    async def _upload_mandatory_cover_v4(self, page: Page, path: str):
        """强制封面"""
        try:
            await page.locator("text=单图").first.click()
            await asyncio.sleep(1)
            file_input = page.locator("input[type='file']").first
            await file_input.set_input_files(path)
            await asyncio.sleep(5)
            logger.info("✅ 封面上传指令发送完毕")
        except:
            pass

    async def _handle_final_publish_v4(self, page: Page) -> bool:
        """点击发布"""
        try:
            # 定位那个红色的“预览并发布”按钮
            btn = page.locator("button:has-text('预览并发布'), button:has-text('发布')").last
            await btn.scroll_into_view_if_needed()

            # 轮询 10 次直到按钮可用
            for _ in range(10):
                if await btn.is_enabled():
                    await btn.click(force=True)
                    logger.success("✅ 已触发发布按钮点击")

                    # 检查是否有二次弹窗
                    await asyncio.sleep(2)
                    confirm = page.locator(".byte-modal__footer button:has-text('确认'), button:has-text('发布')").first
                    if await confirm.is_visible(timeout=3000):
                        await confirm.click()
                    return True

                await asyncio.sleep(2)
                # 如果按钮还是灰的，尝试点一下标题激活
                await page.mouse.click(400, 220)
            return False
        except:
            return False

    async def _download_images(self, urls: List[str]) -> List[str]:
        paths = []
        async with httpx.AsyncClient(verify=False) as client:
            for url in urls:
                try:
                    resp = await client.get(url, timeout=10.0)
                    if resp.status_code == 200:
                        tmp = os.path.join(tempfile.gettempdir(), f"tt_v4_{random.randint(100, 999)}.jpg")
                        with open(tmp, "wb") as f:
                            f.write(resp.content)
                        paths.append(tmp)
                        if len(paths) >= 1: break
                except:
                    continue
        return paths

    async def _wait_for_publish_result(self, page: Page) -> Dict[str, Any]:
        for i in range(25):
            if "content_manage" in page.url or "profile" in page.url:
                return {"success": True, "platform_url": page.url}
            await asyncio.sleep(1)
        return {"success": False, "error_msg": "发布超时，可能存在标题违规或封面未选中"}


# 注册
registry.register("toutiao", ToutiaoPublisher("toutiao", {
    "name": "今日头条",
    "publish_url": "https://mp.toutiao.com/profile_v4/graphic/publish",
    "color": "#F85959"
}))