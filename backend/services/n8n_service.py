"""
n8n 服务封装
把所有 AI 调用都通过 n8n webhook 转发，解耦 AI 逻辑
作者: 老王
创建时间: 2025-01-22
"""

import httpx
from typing import Any, Literal
from loguru import logger
from pydantic import BaseModel, Field


# ==================== 配置 ====================

class N8nConfig:
    # 🌟 改回正式地址，不带 -test
    WEBHOOK_BASE = "http://localhost:5678/webhook"

    # 超时配置
    TIMEOUT_SHORT = 30.0   # 简单任务超时
    TIMEOUT_LONG = 120.0   # 文章生成超时

    # 重试配置
    MAX_RETRIES = 2
    RETRY_DELAY = 1.0


# ==================== 请求模型 ====================

class KeywordDistillRequest(BaseModel):
    """关键词蒸馏请求"""
    keywords: list[str] = Field(..., description="待蒸馏的关键词列表")
    project_id: int | None = Field(None, description="项目ID")


class GenerateQuestionsRequest(BaseModel):
    """生成问题变体请求"""
    question: str = Field(..., description="原始问题")
    count: int = Field(10, ge=1, le=50, description="生成数量")


class GeoArticleRequest(BaseModel):
    """GEO文章生成请求"""
    keyword: str = Field(..., description="目标关键词")
    platform: Literal["zhihu", "baijiahao", "sohu", "toutiao"] = Field(
        "zhihu", description="目标平台"
    )
    requirements: str = Field("", description="补充要求")
    word_count: int = Field(1200, ge=500, le=3000, description="字数要求")


class IndexCheckAnalysisRequest(BaseModel):
    """收录分析请求"""
    keyword: str = Field(..., description="关键词")
    doubao_indexed: bool = Field(..., description="豆包是否收录")
    qianwen_indexed: bool = Field(..., description="千问是否收录")
    deepseek_indexed: bool = Field(..., description="DeepSeek是否收录")
    history: list[dict] = Field(default_factory=list, description="历史数据")


# ==================== 响应模型 ====================

class N8nResponse(BaseModel):
    """n8n 统一响应格式"""
    status: Literal["success", "error", "processing"]
    data: dict[str, Any] | None = None
    error: str | None = None
    timestamp: str | None = None


# ==================== 服务类 ====================

class N8nService:
    """
    n8n 服务类
    老王我封装了一层，以后调用 AI 就不用管底层是啥了
    """

    def __init__(self, config: N8nConfig | None = None):
        self.config = config or N8nConfig()
        self.client = httpx.AsyncClient(timeout=self.config.TIMEOUT_SHORT)

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    async def _call_webhook(
        self,
        webhook_path: str,
        payload: dict[str, Any],
        timeout: float | None = None
    ) -> N8nResponse:
        """
        调用 n8n webhook 的通用方法

        Args:
            webhook_path: webhook 路径
            payload: 请求载荷
            timeout: 超时时间

        Returns:
            N8nResponse: 统一响应格式
        """
        url = f"{self.config.WEBHOOK_BASE}{webhook_path}"
        timeout = timeout or self.config.TIMEOUT_SHORT

        for attempt in range(self.config.MAX_RETRIES + 1):
            try:
                logger.info(f"[n8n] 调用 webhook: {webhook_path}, 尝试 {attempt + 1}")
                response = await self.client.post(url, json=payload, timeout=timeout)
                response.raise_for_status()

                data = response.json()
                return N8nResponse(**data)

            except httpx.TimeoutException:
                logger.warning(f"[n8n] 超时: {webhook_path}")
                if attempt == self.config.MAX_RETRIES:
                    return N8nResponse(
                        status="error",
                        error=f"请求超时 ({timeout}s)",
                        data=None
                    )

            except httpx.HTTPStatusError as e:
                logger.error(f"[n8n] HTTP错误: {e.response.status_code}")
                return N8nResponse(
                    status="error",
                    error=f"HTTP {e.response.status_code}",
                    data=None
                )

            except Exception as e:
                logger.error(f"[n8n] 异常: {e}")
                if attempt == self.config.MAX_RETRIES:
                    return N8nResponse(
                        status="error",
                        error=str(e),
                        data=None
                    )

    async def distill_keywords(
        self,
        keywords: list[str],
        project_id: int | None = None
    ) -> N8nResponse:
        """
        关键词蒸馏
        把一堆破词儿提炼成有价值的 SEO 关键词

        Args:
            keywords: 原始关键词列表
            project_id: 项目ID

        Returns:
            包含核心词、长尾词的响应
        """
        request = KeywordDistillRequest(keywords=keywords, project_id=project_id)
        return await self._call_webhook(
            "/keyword-distill",
            request.model_dump(),
            timeout=self.config.TIMEOUT_SHORT
        )

    async def generate_questions(
        self,
        question: str,
        count: int = 10
    ) -> N8nResponse:
        """
        生成问题变体
        一个问题变出N种问法，覆盖更多搜索意图

        Args:
            question: 原始问题
            count: 生成数量

        Returns:
            包含问题变体列表的响应
        """
        request = GenerateQuestionsRequest(question=question, count=count)
        return await self._call_webhook(
            "/generate-questions",
            request.model_dump(),
            timeout=self.config.TIMEOUT_SHORT
        )

    async def generate_geo_article(
        self,
        keyword: str,
        platform: str = "zhihu",
        requirements: str = "",
        word_count: int = 1200
    ) -> N8nResponse:
        """
        生成 GEO 优化文章
        用 AI 写文章，SEO 优化到位

        Args:
            keyword: 目标关键词
            platform: 发布平台
            requirements: 额外要求
            word_count: 字数要求

        Returns:
            包含标题、内容、SEO评分的响应
        """
        request = GeoArticleRequest(
            keyword=keyword,
            platform=platform,
            requirements=requirements,
            word_count=word_count
        )
        return await self._call_webhook(
            "/geo-article-generate",
            request.model_dump(),
            timeout=self.config.TIMEOUT_LONG
        )

    async def analyze_index_check(
        self,
        keyword: str,
        doubao_indexed: bool,
        qianwen_indexed: bool,
        deepseek_indexed: bool,
        history: list[dict] | None = None
    ) -> N8nResponse:
        """
        分析收录检测结果
        AI 分析收录情况，给出优化建议

        Args:
            keyword: 关键词
            doubao_indexed: 豆包收录状态
            qianwen_indexed: 千问收录状态
            deepseek_indexed: DeepSeek收录状态
            history: 历史数据

        Returns:
            包含分析和预警的响应
        """
        request = IndexCheckAnalysisRequest(
            keyword=keyword,
            doubao_indexed=doubao_indexed,
            qianwen_indexed=qianwen_indexed,
            deepseek_indexed=deepseek_indexed,
            history=history or []
        )
        return await self._call_webhook(
            "/index-check-analysis",
            request.model_dump(),
            timeout=self.config.TIMEOUT_SHORT
        )


# ==================== 单例实例 ====================

_n8n_service: N8nService | None = None


async def get_n8n_service() -> N8nService:
    """获取 n8n 服务单例"""
    global _n8n_service
    if _n8n_service is None:
        _n8n_service = N8nService()
    return _n8n_service


# ==================== 测试代码 ====================

async def main():
    """测试 n8n 服务是否连通"""
    service = await get_n8n_service()

    # 测试关键词蒸馏
    result = await service.distill_keywords(
        keywords=["Python教程", "怎么学Python", "Python入门"]
    )

    if result.status == "success":
        logger.info(f"✅ 关键词蒸馏成功: {result.data}")
    else:
        logger.error(f"❌ 关键词蒸馏失败: {result.error}")

    await service.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
