<template>
  <div class="articles-page">
    <!-- 选择区域 -->
    <div class="section">
      <h2 class="section-title">生成文章</h2>
      <el-form :inline="true" :model="generateForm" class="generate-form">
        <el-form-item label="选择项目">
          <el-select
            v-model="generateForm.projectId"
            placeholder="请选择项目"
            style="width: 180px"
            @change="onProjectChange"
          >
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="选择关键词">
          <el-select
            v-model="generateForm.keywordId"
            placeholder="请选择关键词"
            style="width: 180px"
            :disabled="!generateForm.projectId"
          >
            <el-option
              v-for="keyword in keywords"
              :key="keyword.id"
              :label="keyword.keyword"
              :value="keyword.id"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="发布平台">
          <el-select v-model="generateForm.platform" style="width: 120px">
            <el-option label="知乎" value="zhihu" />
            <el-option label="百家号" value="baijiahao" />
            <el-option label="搜狐号" value="sohu" />
            <el-option label="头条号" value="toutiao" />
          </el-select>
        </el-form-item>

        <el-form-item label="定时发布">
          <el-date-picker
            v-model="generateForm.publishTime"
            type="datetime"
            placeholder="立即发布 (留空)"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 200px"
            clearable
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :loading="generating"
            :disabled="!generateForm.keywordId"
            @click="generateArticle"
          >
            <el-icon><MagicStick /></el-icon>
            生成文章
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 文章列表 -->
    <div class="section">
      <div class="section-header">
        <h2 class="section-title">文章列表</h2>
        <el-button @click="loadArticles">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>

      <el-table
        v-loading="articlesLoading"
        :data="articles"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="title" label="标题" min-width="180">
          <template #default="{ row }">
            {{ row.title || '（内容生成中...）' }}
          </template>
        </el-table-column>
        <el-table-column prop="platform" label="平台" width="90">
          <template #default="{ row }">
            <el-tag size="small">{{ getPlatformName(row.platform) }}</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="发布状态" width="100">
          <template #default="{ row }">
            <el-tooltip 
              :content="row.publish_time ? '计划发布: ' + formatDate(row.publish_time) : '无计划时间'" 
              placement="top"
              :disabled="!row.publish_time"
            >
              <el-tag :type="getPublishStatusType(row.publish_status)">
                {{ getPublishStatusText(row.publish_status) }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>

        <el-table-column label="质检状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getQualityStatusType(row.quality_status)" size="small">
              {{ getQualityStatusText(row.quality_status) }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 🌟 新增列：收录状态 -->
        <el-table-column label="收录状态" width="100">
          <template #default="{ row }">
            <el-tooltip 
              :content="row.last_check_time ? '最后检测: ' + formatDate(row.last_check_time) : '尚未检测'" 
              placement="top"
            >
              <el-tag :type="getIndexStatusType(row.index_status)" size="small" effect="dark">
                {{ getIndexStatusText(row.index_status) }}
              </el-tag>
            </el-tooltip>
          </template>
        </el-table-column>

        <el-table-column label="评分" width="70">
          <template #default="{ row }">
            <span v-if="row.quality_score" :class="getScoreClass(row.quality_score)">
              {{ row.quality_score }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">
            <span class="text-muted">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="previewArticle(row)">预览</el-button>
            <el-button
              type="success"
              size="small"
              link
              :loading="checkingQuality === row.id"
              :disabled="row.quality_status === 'passed' || row.publish_status === 'generating'"
              @click="checkQuality(row)"
            >质检</el-button>

            <!-- 🌟 新增操作：检测收录按钮 -->
            <el-button
              type="warning"
              size="small"
              link
              :loading="checkingIndex === row.id"
              :disabled="row.publish_status !== 'published'"
              @click="checkIndex(row)"
            >检测</el-button>

            <el-button type="info" size="small" link @click="editArticle(row)">编辑</el-button>
            <el-button type="danger" size="small" link @click="deleteArticle(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 文章预览对话框 -->
    <el-dialog 
      v-model="showPreviewDialog" 
      :title="currentArticle?.title || '预览'" 
      width="900px"
      top="5vh"
      destroy-on-close
    >
      <div v-if="currentArticle" class="article-preview-scroll">
        <div 
          class="markdown-body" 
          v-html="renderMarkdown(currentArticle.content)"
        ></div>
      </div>
      <template #footer>
        <el-button @click="showPreviewDialog = false">关闭预览</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, Refresh } from '@element-plus/icons-vue'
import { geoKeywordApi, geoArticleApi } from '@/services/api'
import MarkdownIt from 'markdown-it'

// ==================== 初始化 Markdown 解析器 ====================
const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
})

const renderMarkdown = (content: string) => {
  if (!content) return ''
  return md.render(content)
}

// ==================== 状态定义 ====================
const projects = ref<any[]>([])
const keywords = ref<any[]>([])
const articles = ref<any[]>([])
const articlesLoading = ref(false)
const generating = ref(false)
const checkingQuality = ref<number | null>(null)
const checkingIndex = ref<number | null>(null) // 🌟 新增状态
const showPreviewDialog = ref(false)
const currentArticle = ref<any>(null)

const generateForm = ref({
  projectId: null as number | null,
  keywordId: null as number | null,
  platform: 'zhihu',
  publishTime: '' 
})

// ==================== 核心数据加载逻辑 ====================

const loadProjects = async () => {
  try {
    const result: any = await geoKeywordApi.getProjects()
    projects.value = result.data || result || []
  } catch (error) {
    ElMessage.error('无法获取项目列表')
  }
}

const onProjectChange = async () => {
  generateForm.value.keywordId = null
  keywords.value = []
  if (generateForm.value.projectId) {
    try {
      const result: any = await geoKeywordApi.getProjectKeywords(generateForm.value.projectId)
      keywords.value = result.data || result || []
    } catch (error) {
      console.error('加载关键词失败:', error)
    }
  }
}

const loadArticles = async () => {
  articlesLoading.value = true
  try {
    const result: any = await geoArticleApi.getList({ limit: 100 })
    articles.value = result.data || result || []
  } catch (error) {
    console.error('加载文章失败:', error)
  } finally {
    articlesLoading.value = false
  }
}

// ==================== 文章操作 ====================

const generateArticle = async () => {
  if (!generateForm.value.keywordId) return
  const project = projects.value.find(p => p.id === generateForm.value.projectId)
  const companyName = project?.company_name || '默认公司'

  generating.value = true
  try {
    const payload = {
      keyword_id: generateForm.value.keywordId,
      company_name: companyName,
      platform: generateForm.value.platform,
      publish_time: generateForm.value.publishTime || null 
    }
    const result = await geoArticleApi.generate(payload)
    if (result.success) {
      ElMessage.success('任务已提交')
      generateForm.value.publishTime = ''
      await loadArticles()
    }
  } finally {
    generating.value = false
  }
}

const checkQuality = async (article: any) => {
  checkingQuality.value = article.id
  try {
    const result = await geoArticleApi.checkQuality(article.id)
    if (result.success) {
      ElMessage.success('质检完成')
      await loadArticles()
    }
  } finally {
    checkingQuality.value = null
  }
}

// 🌟 新增：手动检测收录逻辑
const checkIndex = async (article: any) => {
  checkingIndex.value = article.id
  try {
    const result = await geoArticleApi.checkIndex(article.id)
    if (result.success) {
      ElMessage.success(result.message)
      await loadArticles()
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    ElMessage.error('收录检测异常')
  } finally {
    checkingIndex.value = null
  }
}

const previewArticle = (article: any) => {
  currentArticle.value = article
  showPreviewDialog.value = true
}

const editArticle = (article: any) => {
  // 编辑逻辑可以后续根据需求补全对话框
  ElMessage.info('编辑功能开发中...')
}

const deleteArticle = async (article: any) => {
  try {
    await geoArticleApi.delete(article.id)
    ElMessage.success('已删除')
    await loadArticles()
  } catch (error) {
    ElMessage.error('删除失败')
  }
}

// ==================== 工具渲染函数 ====================

const getPublishStatusType = (status: string) => {
  const types: any = { draft: 'info', scheduled: 'warning', publishing: 'primary', published: 'success', failed: 'danger' }
  return types[status] || 'info'
}

const getPublishStatusText = (status: string) => {
  const texts: any = { draft: '草稿', scheduled: '待发布', publishing: '发布中', published: '已发布', failed: '失败' }
  return texts[status] || status
}

// 🌟 新增：收录状态渲染逻辑
const getIndexStatusType = (status: string) => {
  const types: any = { uncheck: 'info', indexed: 'success', not_indexed: 'danger' }
  return types[status] || 'info'
}

const getIndexStatusText = (status: string) => {
  const texts: any = { uncheck: '未检测', indexed: '已收录', not_indexed: '未收录' }
  return texts[status] || '未检测'
}

const getPlatformName = (p: string) => {
  const names: any = { zhihu: '知乎', baijiahao: '百家号', sohu: '搜狐', toutiao: '头条' }
  return names[p] || p
}

const getQualityStatusType = (s: string) => s === 'passed' ? 'success' : (s === 'failed' ? 'danger' : 'warning')
const getQualityStatusText = (s: string) => s === 'passed' ? '通过' : (s === 'failed' ? '未过' : '待检')

const getScoreClass = (s: number) => s >= 80 ? 'text-success' : (s >= 60 ? 'text-warning' : 'text-danger')

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN', { hour12: false })
}

onMounted(() => {
  loadProjects()
  loadArticles()
})
</script>

<style scoped lang="scss">
.articles-page { padding: 20px; }
.section { background: #1e1e1e; border-radius: 12px; padding: 24px; margin-bottom: 24px; border: 1px solid rgba(255,255,255,0.05); }
.section-title { color: #fff; margin-bottom: 20px; font-size: 18px; font-weight: 600; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.generate-form { display: flex; align-items: center; gap: 12px; }
.text-muted { color: #888; font-size: 13px; }
.text-success { color: #67c23a; }
.text-warning { color: #e6a23c; }
.text-danger { color: #f56c6c; }

.article-preview-scroll {
  max-height: 70vh;
  overflow-y: auto;
  padding: 0 20px;
}

/* Markdown 样式 */
.markdown-body {
  color: #d1d5db;
  line-height: 1.8;
  font-size: 16px;

  :deep(img) {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 24px auto;
    border-radius: 12px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  :deep(h1), :deep(h2), :deep(h3) {
    color: #ffffff;
    margin: 32px 0 16px 0;
    font-weight: 600;
  }

  :deep(h2) {
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  :deep(p) {
    margin-bottom: 18px;
    letter-spacing: 0.3px;
  }
}

.article-preview-scroll::-webkit-scrollbar { width: 6px; }
.article-preview-scroll::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 10px; }
</style>