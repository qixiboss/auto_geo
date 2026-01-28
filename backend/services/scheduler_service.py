# -*- coding: utf-8 -*-
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

try:
    from pytz import timezone
except ImportError:
    timezone = None

from backend.services.geo_article_service import GeoArticleService
from backend.database.models import ScheduledTask, GeoArticle, Project, Keyword


class SchedulerService:
    def __init__(self):
        tz = timezone('Asia/Shanghai') if timezone else None
        self.scheduler = AsyncIOScheduler(timezone=tz)
        self.db_factory = None

        # 🌟 任务映射：将数据库里的 task_key 映射到具体的函数
        self.task_registry = {
            "publish_task": self.check_and_publish_scheduled_articles,
            "monitor_task": self.auto_check_indexing_job
        }

    def set_db_factory(self, db_factory):
        self.db_factory = db_factory

    def init_default_tasks(self):
        """初始化默认任务到数据库 (如果表为空)"""
        if not self.db_factory: return
        db = self.db_factory()
        try:
            # 检查是否已有任务
            if db.query(ScheduledTask).count() == 0:
                defaults = [
                    ScheduledTask(
                        name="文章自动发布与重试",
                        task_key="publish_task",
                        cron_expression="*/1 * * * *",  # 每分钟
                        description="扫描待发布文章，执行发布及失败重试",
                        is_active=True
                    ),
                    ScheduledTask(
                        name="全网收录监测",
                        task_key="monitor_task",
                        cron_expression="*/5 * * * *",  # 每5分钟
                        description="检查已发布文章是否被AI搜索引擎收录",
                        is_active=True
                    )
                ]
                db.add_all(defaults)
                db.commit()
                logger.info("✅ 初始化默认定时任务配置完成")
        except Exception as e:
            logger.error(f"初始化任务失败: {e}")
        finally:
            db.close()

    def load_jobs_from_db(self):
        """从数据库加载并注册所有任务"""
        if not self.db_factory: return
        db = self.db_factory()
        try:
            tasks = db.query(ScheduledTask).all()
            for task in tasks:
                self._schedule_job(task)
        finally:
            db.close()

    def _schedule_job(self, task: ScheduledTask):
        """内部方法：根据配置注册/更新单个 Job"""
        func = self.task_registry.get(task.task_key)
        if not func:
            logger.warning(f"⚠️ 未找到任务处理函数: {task.task_key}")
            return

        # 先移除旧任务（如果存在）
        if self.scheduler.get_job(task.task_key):
            self.scheduler.remove_job(task.task_key)

        # 如果启用，则添加新任务
        if task.is_active:
            try:
                self.scheduler.add_job(
                    func,
                    CronTrigger.from_crontab(task.cron_expression),
                    id=task.task_key,
                    replace_existing=True
                )
                logger.info(f"📅 任务已装载: {task.name} -> {task.cron_expression}")
            except Exception as e:
                logger.error(f"❌ Cron表达式错误 [{task.name}]: {e}")

    def start(self):
        """启动引擎"""
        if not self.scheduler.running:
            self.init_default_tasks()  # 确保数据库有数据
            self.load_jobs_from_db()  # 加载任务
            self.scheduler.start()
            logger.info("🚀 [Scheduler] 动态调度引擎已启动")

    def reload_task(self, task_id: int):
        """对外接口：当用户修改配置后，重新加载该任务"""
        if not self.db_factory: return
        db = self.db_factory()
        try:
            task = db.query(ScheduledTask).get(task_id)
            if task:
                self._schedule_job(task)
                return True
        finally:
            db.close()
        return False

    # ================= 具体的业务逻辑函数 (保持不变) =================

    async def check_and_publish_scheduled_articles(self):
        """发布逻辑"""
        if not self.db_factory: return
        db = self.db_factory()
        try:
            now = datetime.now()
            pending = db.query(GeoArticle).filter(
                ((GeoArticle.publish_status == "scheduled") |
                 ((GeoArticle.publish_status == "failed") & (GeoArticle.retry_count < 3))),
                GeoArticle.publish_time <= now
            ).all()
            if pending:
                logger.info(f"🔍 [发布扫描] 发现 {len(pending)} 篇待处理")
                service = GeoArticleService(db)
                for article in pending:
                    await service.execute_publish(article.id)
        except Exception as e:
            logger.error(f"发布任务异常: {e}")
        finally:
            db.close()

    async def auto_check_indexing_job(self):
        """监测逻辑"""
        if not self.db_factory: return
        db = self.db_factory()
        try:
            pending = db.query(GeoArticle).filter(
                GeoArticle.publish_status == "published",
                GeoArticle.index_status != "indexed"
            ).all()
            if pending:
                logger.info(f"📡 [收录扫描] 发现 {len(pending)} 篇待检测")
                service = GeoArticleService(db)
                for article in pending:
                    await service.check_article_index(article.id)
        except Exception as e:
            logger.error(f"监测任务异常: {e}")
        finally:
            db.close()


_instance = SchedulerService()


def get_scheduler_service(): return _instance