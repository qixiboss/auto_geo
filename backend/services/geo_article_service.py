# -*- coding: utf-8 -*-
import asyncio
import random
from typing import Any, Dict, Optional, List
from datetime import datetime  # <--- 🌟 关键新增：导入 datetime
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database.models import GeoArticle, Keyword
from backend.services.n8n_service import get_n8n_service


class GeoArticleService:
    def __init__(self, db: Session):
        self.db = db

    async def generate(
        self,
        keyword_id: int,
        company_name: str,
        platform: str = "zhihu",
        publish_time: Optional[datetime] = None  # <--- 🌟 关键新增：接收时间参数
    ) -> Dict[str, Any]:
        """
        生成文章 (正式版：调用 n8n，支持定时发布)
        """
        # 1. 获取关键词
        keyword_obj = self.db.query(Keyword).filter(Keyword.id == keyword_id).first()
        if not keyword_obj:
            return {"status": "error", "message": "关键词不存在"}

        logger.info(f"🚀 [正式调用] 准备发送请求到 n8n: {keyword_obj.keyword}")

        try:
            # 2. 获取 n8n 服务单例
            n8n = await get_n8n_service()

            # 3. 调用 n8n 生成文章
            n8n_res = await n8n.generate_geo_article(
                keyword=keyword_obj.keyword,
                platform=platform,
                requirements=f"请围绕【{company_name}】编写，要求SEO友好。",
                word_count=1000
            )

            # 4. 检查结果
            if n8n_res.status != "success":
                return {"status": "error", "message": n8n_res.error or "n8n 返回异常"}

            # 5. 提取 AI 生成的内容
            ai_data = n8n_res.data or {}
            title = ai_data.get("title", f"关于{keyword_obj.keyword}的解析")
            content = ai_data.get("content", "内容生成失败")

            # 6. 保存到数据库
            article = GeoArticle(
                keyword_id=keyword_id,
                title=title,
                content=content,
                platform=platform,
                quality_status="pending",
                publish_time=publish_time  # <--- 🌟 关键新增：将时间存入数据库
            )
            self.db.add(article)
            self.db.commit()
            self.db.refresh(article)

            logger.info(f"✅ AI 文章生成并入库成功: ID={article.id}")
            return {
                "status": "success",
                "article_id": article.id,
                "title": title
            }

        except Exception as e:
            logger.error(f"❌ 调用 n8n 链路崩溃: {str(e)}")
            return {"status": "error", "message": str(e)}

    # ==============================================================
    # 👇 其他方法保持不变
    # ==============================================================

    def get_article(self, article_id: int) -> Optional[GeoArticle]:
        """
        根据ID获取文章详情
        """
        return self.db.query(GeoArticle).filter(GeoArticle.id == article_id).first()

    def get_keyword_articles(self, keyword_id: int) -> List[GeoArticle]:
        """

        获取某个关键词下的所有文章
        """
        return self.db.query(GeoArticle).filter(
            GeoArticle.keyword_id == keyword_id
        ).order_by(desc(GeoArticle.created_at)).all()

    def update_article(
            self,
            article_id: int,
            title: Optional[str] = None,
            content: Optional[str] = None
    ) -> Optional[GeoArticle]:
        """
        手动更新文章内容
        """
        article = self.get_article(article_id)
        if not article:
            return None

        if title is not None:
            article.title = title
        if content is not None:
            article.content = content

        self.db.commit()
        self.db.refresh(article)
        return article

    async def check_quality(self, article_id: int) -> Dict[str, Any]:
        """
        文章质检 (目前暂时保持 Mock 逻辑)
        """
        article = self.get_article(article_id)
        if not article:
            return {"status": "error", "message": "文章不存在"}

        logger.info(f"🔍 [Mock] 开始质检文章: {article_id}")

        await asyncio.sleep(1)

        score = random.randint(80, 98)
        article.quality_score = score
        article.readability_score = random.randint(80, 95)
        article.ai_score = random.randint(10, 30)
        article.quality_status = "passed" if score >= 60 else "failed"

        self.db.commit()

        return {
            "status": "success",
            "quality_score": article.quality_score,
            "quality_status": article.quality_status
        }