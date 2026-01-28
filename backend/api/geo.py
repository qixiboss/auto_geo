# -*- coding: utf-8 -*-
from typing import List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database import get_db, SessionLocal
from backend.services.geo_article_service import GeoArticleService
from backend.database.models import GeoArticle, Project
from backend.schemas import ApiResponse
from loguru import logger

router = APIRouter(prefix="/api/geo", tags=["GEO文章"])


# ==================== 请求/响应模型 ====================

class GenerateArticleRequest(BaseModel):
    keyword_id: int
    company_name: str
    platform: str = "zhihu"
    publish_time: Optional[datetime] = None


class ArticleResponse(BaseModel):
    """
    🌟 核心模型：补齐所有字段，解决序列化报错
    """
    id: int
    keyword_id: int
    title: Optional[str] = None
    content: Optional[str] = None

    # 状态
    quality_status: Optional[str] = "pending"
    publish_status: Optional[str] = "draft"
    index_status: Optional[str] = "uncheck"  # 🌟 新增：收录状态
    platform: Optional[str] = "zhihu"

    # 评分
    quality_score: Optional[int] = None
    ai_score: Optional[int] = None
    readability_score: Optional[int] = None

    # 记录与日志
    retry_count: Optional[int] = 0
    error_msg: Optional[str] = None
    publish_logs: Optional[str] = None
    index_details: Optional[str] = None

    # 时间
    publish_time: Optional[datetime] = None
    last_check_time: Optional[datetime] = None  # 🌟 新增：检测时间
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProjectResponse(BaseModel):
    id: int
    name: str
    company_name: str

    class Config:
        from_attributes = True


# ==================== 异步辅助逻辑 ====================

async def run_generate_task(keyword_id: int, company_name: str, platform: str, publish_time: Optional[datetime]):
    db = SessionLocal()
    try:
        service = GeoArticleService(db)
        await service.generate(keyword_id, company_name, platform, publish_time)
    finally:
        db.close()


# ==================== 接口实现 ====================

@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(db: Session = Depends(get_db)):
    """获取项目列表"""
    return db.query(Project).filter(Project.status == 1).all()


@router.post("/generate", response_model=ApiResponse)
async def generate_article(request: GenerateArticleRequest, background_tasks: BackgroundTasks):
    """提交生成任务"""
    background_tasks.add_task(run_generate_task, request.keyword_id, request.company_name, request.platform,
                              request.publish_time)
    return ApiResponse(success=True, message="任务已提交，后台生成并排期中...")


@router.get("/articles", response_model=List[ArticleResponse])
async def list_articles(limit: int = Query(100), db: Session = Depends(get_db)):
    """获取文章列表（按创建时间倒序）"""
    return db.query(GeoArticle).order_by(desc(GeoArticle.created_at)).limit(limit).all()


@router.post("/articles/{article_id}/check-quality", response_model=ApiResponse)
async def check_quality(article_id: int, db: Session = Depends(get_db)):
    """手动质检"""
    service = GeoArticleService(db)
    result = await service.check_quality(article_id)
    return ApiResponse(success=True, message="质检完成", data=result)


@router.post("/articles/{article_id}/check-index", response_model=ApiResponse)
async def manual_check_index(article_id: int, db: Session = Depends(get_db)):
    """
    🌟 [新增] 手动触发收录检测接口
    """
    service = GeoArticleService(db)
    result = await service.check_article_index(article_id)
    if result.get("status") == "error":
        return ApiResponse(success=False, message=result.get("message"))
    return ApiResponse(success=True, message=f"检测完成，当前状态：{result.get('index_status')}")


@router.delete("/articles/{article_id}", response_model=ApiResponse)
async def delete_article(article_id: int, db: Session = Depends(get_db)):
    """删除文章"""
    article = db.query(GeoArticle).filter(GeoArticle.id == article_id).first()
    if not article: raise HTTPException(status_code=404, detail="文章不存在")
    db.delete(article)
    db.commit()
    return ApiResponse(success=True, message="删除成功")