# -*- coding: utf-8 -*-
import asyncio
import random
from typing import Any, Dict, Optional, List
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database.models import GeoArticle, Keyword
from backend.services.n8n_service import get_n8n_service


class GeoArticleService:
    def __init__(self, db: Session):
        self.db = db

    async def generate(self, keyword_id: int, company_name: str, platform: str = "zhihu",
                       publish_time: Optional[datetime] = None) -> Dict[str, Any]:
        """后台异步生成文章逻辑"""
        article = GeoArticle(
            keyword_id=keyword_id,
            title="[AI正在创作中]...",
            content="正在努力写作，请稍后刷新列表...",
            platform=platform,
            publish_status="generating",
            publish_time=publish_time
        )
        self.db.add(article)
        self.db.commit()
        self.db.refresh(article)

        try:
            kw_obj = self.db.query(Keyword).filter(Keyword.id == keyword_id).first()
            kw_text = kw_obj.keyword if kw_obj else "未知关键词"

            n8n = await get_n8n_service()
            n8n_res = await n8n.generate_geo_article(
                keyword=kw_text,
                platform=platform,
                requirements=f"围绕【{company_name}】编写，风格专业商务。",
                word_count=1000
            )

            if n8n_res.status == "success":
                ai_data = n8n_res.data or {}
                article.title = ai_data.get("title", f"关于{kw_text}的解析")
                article.content = ai_data.get("content", "内容生成失败")
                # 逻辑：有排期时间则为 scheduled，否则为 draft
                article.publish_status = "scheduled" if publish_time else "draft"
            else:
                article.publish_status = "failed"
                article.error_msg = n8n_res.error

            self.db.commit()
            logger.info(f"✅ 文章 {article.id} 生成完毕，状态: {article.publish_status}")
            return {"status": "success", "article_id": article.id}
        except Exception as e:
            logger.error(f"❌ 后台生成异常: {str(e)}")
            article.publish_status = "failed"
            article.error_msg = str(e)
            self.db.commit()
            return {"status": "error", "message": str(e)}

    async def execute_publish(self, article_id: int) -> bool:
        """执行发布动作 (由调度器定时触发)"""
        article = self.db.query(GeoArticle).filter(GeoArticle.id == article_id).first()
        if not article:
            return False

        # 频率控制：模拟真人操作，随机延迟 5-15 秒
        wait_time = random.randint(5, 15)
        logger.info(f"⏳ [频率控制] 文章 {article.id} 将在 {wait_time} 秒后发布...")
        await asyncio.sleep(wait_time)

        try:
            article.publish_status = "publishing"
            article.publish_logs = f"[{datetime.now()}] 开始推送至平台...\n"
            self.db.commit()

            logger.info(f"🚀 正在发布: {article.title}")
            await asyncio.sleep(2)  # 模拟推送请求

            article.publish_status = "published"
            article.publish_logs += f"[{datetime.now()}] ✅ 发布成功\n"
            self.db.commit()
            return True
        except Exception as e:
            article.retry_count += 1
            article.publish_status = "failed"
            article.error_msg = str(e)
            article.publish_logs += f"[{datetime.now()}] ❌ 发布失败: {str(e)}\n"
            self.db.commit()
            return False

    async def check_article_index(self, article_id: int) -> Dict[str, Any]:
        """
        🌟 [新增] 收录监测逻辑
        模拟调用 n8n 检查文章是否被 AI 搜索引擎收录
        """
        article = self.db.query(GeoArticle).filter(GeoArticle.id == article_id).first()
        if not article or article.publish_status != "published":
            return {"status": "error", "message": "文章未发布，无法检测"}

        logger.info(f"🔍 [监测] 正在检查文章收录情况: {article.title[:15]}...")

        try:
            # 这里原本应该调用 n8n 的 index-check 工作流
            await asyncio.sleep(3)  # 模拟 AI 搜索耗时

            # 模拟收录结果：如果是“写字楼”相关，设定收录概率高一些
            is_indexed = random.random() > 0.4

            article.index_status = "indexed" if is_indexed else "not_indexed"
            article.last_check_time = datetime.now()
            article.index_details = "DeepSeek, 豆包 已引用" if is_indexed else "全网 AI 暂未收录"

            self.db.commit()
            logger.success(f"📡 文章 {article.id} 监测完成: {article.index_status}")
            return {"status": "success", "index_status": article.index_status}
        except Exception as e:
            logger.error(f"❌ 收录监测异常: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def check_quality(self, article_id: int) -> Dict[str, Any]:
        """质检逻辑 (Mock)"""
        try:
            article = self.db.query(GeoArticle).filter(GeoArticle.id == article_id).first()
            if not article: return {"status": "error", "message": "未找到文章"}

            await asyncio.sleep(0.5)
            article.quality_score = random.randint(85, 96)
            article.readability_score = random.randint(80, 95)
            article.ai_score = random.randint(5, 25)
            article.quality_status = "passed"
            self.db.commit()

            return {
                "article_id": article.id,
                "quality_score": article.quality_score,
                "quality_status": article.quality_status
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_article(self, article_id: int) -> Optional[GeoArticle]:
        return self.db.query(GeoArticle).filter(GeoArticle.id == article_id).first()

    def update_article(self, article_id: int, title: str, content: str) -> Optional[GeoArticle]:
        article = self.get_article(article_id)
        if article:
            article.title = title
            article.content = content
            self.db.commit()
        return article