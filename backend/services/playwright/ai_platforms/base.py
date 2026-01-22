# -*- coding: utf-8 -*-
"""
AI平台检测器基类
用这个抽象基类定义检测器的统一接口！
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from playwright.async_api import Page, BrowserContext
from loguru import logger
import asyncio


class AIPlatformChecker(ABC):
    """
    AI平台检测器基类

    注意：所有AI平台检测器都要继承这个类！
    """

    def __init__(self, platform_id: str, config: Dict[str, Any]):
        """
        初始化检测器

        Args:
            platform_id: 平台ID
            config: 平台配置
        """
        self.platform_id = platform_id
        self.config = config
        self.name = config.get("name", platform_id)
        self.url = config.get("url", "")
        self.color = config.get("color", "#333333")

    @abstractmethod
    async def check(
        self,
        page: Page,
        question: str,
        keyword: str,
        company: str
    ) -> Dict[str, Any]:
        """
        检测AI平台收录情况

        Args:
            page: Playwright Page对象
            question: 检测使用的问题
            keyword: 目标关键词
            company: 公司名称

        Returns:
            检测结果：
            {
                "success": bool,
                "answer": str,
                "keyword_found": bool,
                "company_found": bool,
                "error_msg": str
            }
        """
        pass

    async def navigate_to_page(self, page: Page) -> bool:
        """
        导航到AI平台页面

        Returns:
            是否成功导航
        """
        try:
            await page.goto(self.url, wait_until="networkidle", timeout=30000)
            logger.info(f"导航到AI平台: {self.name}")
            await asyncio.sleep(2)  # 等待页面完全加载
            return True
        except Exception as e:
            logger.error(f"导航失败: {self.name}, {e}")
            return False

    async def wait_for_selector(
        self,
        page: Page,
        selector: str,
        timeout: int = 15000
    ) -> bool:
        """
        等待选择器出现

        注意：AI平台加载慢，需要耐心等待！
        """
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            logger.warning(f"等待选择器超时: {selector}")
            return False

    async def wait_for_answer_generation(
        self,
        page: Page,
        initial_content: str,
        selector: str = "body",
        timeout: int = 30000
    ) -> bool:
        """
        智能等待AI回答生成完成

        Args:
            page: Playwright Page对象
            initial_content: 初始页面内容
            selector: 要监控的选择器
            timeout: 最大等待时间（毫秒）

        Returns:
            是否成功检测到回答生成完成
        """
        start_time = asyncio.get_event_loop().time()
        content_changed = False
        
        while asyncio.get_event_loop().time() - start_time < timeout / 1000:
            current_content = await page.inner_text(selector)
            
            # 检测内容是否发生变化
            if current_content != initial_content:
                content_changed = True
                # 等待一段时间看是否稳定
                await asyncio.sleep(3)
                # 再次检查内容是否稳定
                final_content = await page.inner_text(selector)
                if final_content == current_content:
                    return True
            
            await asyncio.sleep(1)
        
        return content_changed

    def check_keywords_in_text(
        self,
        text: str,
        keyword: str,
        company: str
    ) -> Dict[str, bool]:
        """
        检查文本中是否包含关键词和公司名

        Args:
            text: 待检测文本
            keyword: 目标关键词
            company: 公司名称

        Returns:
            {keyword_found: bool, company_found: bool}
        """
        # 清理文本，移除多余空格和特殊字符
        import re
        cleaned_text = re.sub(r'[^\w\s\u4e00-\u9fa5]', ' ', text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        text_lower = cleaned_text.lower()
        keyword_lower = keyword.lower()
        company_lower = company.lower()
        
        # 1. 精确匹配检查
        keyword_exact = keyword_lower in text_lower
        company_exact = company_lower in text_lower
        
        # 2. 部分匹配检查（处理公司名可能的变体）
        company_parts = [part.strip() for part in company_lower.split() if part.strip()]
        company_partial = False
        
        if len(company_parts) > 1:
            # 检查公司名的主要部分是否存在
            main_parts = company_parts[:2]  # 取前两个词作为主要部分
            company_partial = all(part in text_lower for part in main_parts)
        
        # 3. 关键词上下文检查（确保关键词不是在无关的上下文中）
        keyword_context_found = False
        if keyword_lower in text_lower:
            # 查找关键词前后的上下文
            keyword_index = text_lower.index(keyword_lower)
            # 取关键词前后各50个字符的上下文
            start = max(0, keyword_index - 50)
            end = min(len(text_lower), keyword_index + len(keyword_lower) + 50)
            context = text_lower[start:end]
            
            # 检查上下文是否包含相关词汇（简单示例，可根据需求扩展）
            relevant_terms = ["什么是", "推荐", "介绍", "哪家", "公司", "品牌", "选择", "对比"]
            keyword_context_found = any(term in context for term in relevant_terms)
        
        # 4. 综合判断
        keyword_found = keyword_exact and keyword_context_found
        company_found = company_exact or company_partial
        
        # 5. 处理特殊情况：如果文本非常短，放宽条件
        if len(cleaned_text) < 100:
            keyword_found = keyword_exact
            company_found = company_exact
        
        return {
            "keyword_found": keyword_found,
            "company_found": company_found
        }

    async def clear_chat_history(self, page: Page) -> bool:
        """
        清理聊天历史记录（如果支持）
        
        Returns:
            是否成功清理
        """
        try:
            # 尝试查找清除按钮
            clear_buttons = [
                "button[title*='清除']",
                "button[title*='清空']",
                "button[aria-label*='清除']",
                "button[aria-label*='清空']",
                "[class*='clear'] button",
                "[class*='reset'] button"
            ]
            
            for selector in clear_buttons:
                elements = await page.query_selector_all(selector)
                if elements:
                    for element in elements:
                        try:
                            await element.click(timeout=5000)
                            await asyncio.sleep(1)
                            return True
                        except Exception:
                            continue
            
            logger.info(f"{self.name} 未找到清除历史按钮，跳过清理")
            return True
        except Exception as e:
            logger.error(f"清理聊天历史失败: {self.name}, {e}")
            return False
