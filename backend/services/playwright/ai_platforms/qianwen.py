# -*- coding: utf-8 -*-
"""
通义千问检测器
用这个来检测通义千问的收录情况！
"""

from typing import Dict, Any
from playwright.async_api import Page
from loguru import logger
import asyncio

from .base import AIPlatformChecker


class QianwenChecker(AIPlatformChecker):
    """
    通义千问检测器

    URL: https://tongyi.aliyun.com
    """

    # 通义千问的选择器
    SELECTORS = {
        "input_box": "textarea[placeholder*='输入']",
        "submit_button": "button[type='submit']",
        "answer_area": "[class*='answer']",
        "chat_message": "[class*='message']",
    }

    async def check(
        self,
        page: Page,
        question: str,
        keyword: str,
        company: str
    ) -> Dict[str, Any]:
        """
        检测通义千问收录情况
        """
        try:
            # 1. 导航到通义千问
            if not await self.navigate_to_page(page):
                return {
                    "success": False,
                    "answer": None,
                    "keyword_found": False,
                    "company_found": False,
                    "error_msg": "导航失败"
                }

            # 2. 清理聊天历史
            await self.clear_chat_history(page)

            # 3. 等待输入框加载
            input_selector = self.SELECTORS["input_box"]
            if not await self.wait_for_selector(page, input_selector, 15000):
                input_selector = "textarea"
                if not await self.wait_for_selector(page, input_selector, 10000):
                    return {
                        "success": False,
                        "answer": None,
                        "keyword_found": False,
                        "company_found": False,
                        "error_msg": "输入框未找到"
                    }

            # 4. 输入问题
            await page.fill(input_selector, question)
            await asyncio.sleep(0.5)
            logger.info(f"通义千问已输入问题: {question[:30]}...")

            # 5. 记录当前页面状态，用于智能等待
            initial_content = await page.inner_text("body")

            # 6. 提交（按Enter键）
            await page.keyboard.press("Enter")
            logger.info("通义千问已提交问题")

            # 7. 智能等待回答生成完成
            await self.wait_for_answer_generation(page, initial_content, timeout=40000)

            # 8. 获取回答内容
            answer_selectors = [
                self.SELECTORS["answer_area"],
                self.SELECTORS["chat_message"],
                "[class*='content']",
                "[class*='bubble']",
                ".markdown-body",
                ".answer-content",
                ".chat-content"
            ]

            answer_text = ""
            for selector in answer_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        answer_text = await elements[-1].inner_text()
                        if answer_text.strip():
                            break
                except Exception as e:
                    logger.debug(f"选择器 {selector} 获取失败: {e}")
                    continue

            if not answer_text:
                answer_text = await page.inner_text("body")

            # 9. 检测关键词和公司名
            check_result = self.check_keywords_in_text(answer_text, keyword, company)

            logger.info(f"通义千问检测完成: 关键词={check_result['keyword_found']}, 公司={check_result['company_found']}")

            return {
                "success": True,
                "answer": answer_text[:1000],
                "keyword_found": check_result["keyword_found"],
                "company_found": check_result["company_found"],
                "error_msg": None
            }

        except Exception as e:
            logger.error(f"通义千问检测失败: {e}")
            return {
                "success": False,
                "answer": None,
                "keyword_found": False,
                "company_found": False,
                "error_msg": str(e)
            }
