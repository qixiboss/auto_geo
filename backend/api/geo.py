# -*- coding: utf-8 -*-
"""
GEO文章API
写的GEO文章API，包含生成和质检！
"""

from typing import List, Optional
from datetime import datetime  # <--- 确保导入
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.geo_article_service import GeoArticleService
from backend.database.models import GeoArticle
from backend.schemas import ApiResponse
from loguru import logger

router = APIRouter(prefix="/api/geo", tags=["GEO文章"])


# ==================== 请求/响应模型 ====================

class GenerateArticleRequest(BaseModel):
    """生成文章请求"""
    keyword_id: int
    company_name: str
    platform: str = "zhihu"

    # 👇 关键新增：接收前端的时间参数
    publish_time: Optional[datetime] = None


class ArticleResponse(BaseModel):
    """文章响应 (Pydantic模型)"""
    id: int
    keyword_id: int
    title: Optional[str] = None
    content: Optional[str] = None

    quality_score: Optional[int] = None
    ai_score: Optional[int] = None
    readability_score: Optional[int] = None

    quality_status: Optional[str] = "pending"
    platform: Optional[str] = "zhihu"
    publish_status: Optional[str] = "draft"

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # 新增字段的响应
    publish_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class QualityCheckResponse(BaseModel):
    """质检响应"""
    article_id: int
    quality_score: Optional[int]
    ai_score: Optional[int]
    readability_score: Optional[int]
    quality_status: str


# ==================== 文章生成API ====================

@router.post("/generate", response_model=ApiResponse)
async def generate_article(
        request: GenerateArticleRequest,
        db: Session = Depends(get_db)
):
    """
    生成文章 (支持定时发布)

    调用n8n工作流基于关键词生成SEO优化文章。
    注意：这是AI驱动的核心功能！
    """
    service = GeoArticleService(db)
    result = await service.generate(
        keyword_id=request.keyword_id,
        company_name=request.company_name,
        platform=request.platform,
        # 👇 关键新增：把时间传给 Service 层
        publish_time=request.publish_time
    )

    if result.get("status") == "error":
        return ApiResponse(success=False, message=result.get("message", "生成失败"))

    return ApiResponse(
        success=True,
        message="文章生成成功",
        data={
            "article_id": result.get("article_id"),
            "title": result.get("title")
        }
    )


@router.post("/articles/{article_id}/check-quality", response_model=ApiResponse)
async def check_quality(
        article_id: int,
        db: Session = Depends(get_db)
):
    """
    质检文章
    """
    service = GeoArticleService(db)
    result = await service.check_quality(article_id)

    if result.get("status") == "error":
        return ApiResponse(success=False, message=result.get("message", "质检失败"))

    return ApiResponse(
        success=True,
        message="质检完成",
        data=result
    )


# ==================== 文章查询/管理 API ====================

@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, db: Session = Depends(get_db)):
    """
    获取文章详情
    """
    service = GeoArticleService(db)
    article = service.get_article(article_id)

    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    return article


@router.get("/keywords/{keyword_id}/articles", response_model=List[ArticleResponse])
async def get_keyword_articles(keyword_id: int, db: Session = Depends(get_db)):
    """
    获取关键词的所有文章
    """
    service = GeoArticleService(db)
    articles = service.get_keyword_articles(keyword_id)
    return articles


@router.put("/articles/{article_id}", response_model=ArticleResponse)
async def update_article(
        article_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """
    更新文章
    """
    service = GeoArticleService(db)
    article = service.update_article(article_id, title, content)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    article.quality_status = "pending"
    db.commit()
    db.refresh(article)

    return article


@router.delete("/articles/{article_id}", response_model=ApiResponse)
async def delete_article(article_id: int, db: Session = Depends(get_db)):
    """
    删除文章
    """
    article = db.query(GeoArticle).filter(GeoArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    db.delete(article)
    db.commit()

    logger.info(f"文章已删除: {article_id}")
    return ApiResponse(success=True, message="文章已删除")


@router.get("/articles", response_model=List[ArticleResponse])
async def list_articles(
        keyword_id: Optional[int] = Query(None, description="筛选关键词ID"),
        quality_status: Optional[str] = Query(None, description="质检状态筛选"),
        limit: int = Query(50, ge=1, le=100),
        db: Session = Depends(get_db)
):
    """
    获取文章列表 (支持筛选)
    """
    query = db.query(GeoArticle)

    if keyword_id:
        query = query.filter(GeoArticle.keyword_id == keyword_id)
    if quality_status:
        query = query.filter(GeoArticle.quality_status == quality_status)

    articles = query.order_by(GeoArticle.created_at.desc()).limit(limit).all()
    return articles