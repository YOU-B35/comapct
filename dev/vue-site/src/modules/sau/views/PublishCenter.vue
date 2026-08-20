<template>
  <div class="publish-center">
    <PageHeader
      title="发布中心"
      eyebrow="自媒体"
      description="多平台内容发布与批量任务"
    />

    <!-- Tab管理区域 -->
    <PageSection title="发布任务">
    <div class="tab-management">
      <div class="tab-header">
        <div class="tab-list">
          <div 
            v-for="tab in tabs" 
            :key="tab.name"
            :class="['tab-item', { active: activeTab === tab.name }]"
            @click="activeTab = tab.name"
          >
            <span>{{ tab.label }}</span>
            <el-icon 
              v-if="tabs.length > 1"
              class="close-icon" 
              @click.stop="removeTab(tab.name)"
            >
              <Close />
            </el-icon>
          </div>
        </div>
        <div class="tab-actions">
          <el-button 
            type="primary" 
            size="small" 
            @click="addTab"
            class="add-tab-btn"
          >
            <el-icon><Plus /></el-icon>
            添加Tab
          </el-button>
          <el-button 
            type="success" 
            size="small" 
            @click="batchPublish"
            :loading="batchPublishing"
            class="batch-publish-btn"
          >
            批量发布
          </el-button>
        </div>
      </div>
    </div>
    </PageSection>

    <!-- 内容区域 -->
    <div class="publish-content">
      <div class="tab-content-wrapper">
        <div 
          v-for="tab in tabs" 
          :key="tab.name"
          v-show="activeTab === tab.name"
          class="tab-content"
        >
          <!-- 发布状态提示 -->
          <div v-if="tab.publishStatus" class="publish-status">
            <el-alert
              :title="tab.publishStatus.message"
              :type="tab.publishStatus.type"
              :closable="false"
              show-icon
            />
          </div>

          <!-- 视频上传区域 -->
          <div class="upload-section">
            <h3>视频</h3>
            <div class="upload-options">
              <el-button type="primary" @click="showUploadOptions(tab)" class="upload-btn">
                <el-icon><Upload /></el-icon>
                上传素材
              </el-button>
            </div>
            
            <!-- 已上传文件列表 -->
            <div v-if="tab.fileList.length > 0" class="uploaded-files">
              <h4>已上传文件：</h4>
              <div class="file-list">
                <div v-for="(file, index) in tab.fileList" :key="index" class="file-item">
                  <el-link :href="file.url" target="_blank" type="primary">{{ file.name }}</el-link>
                  <span class="file-size">{{ (file.size / 1024 / 1024).toFixed(2) }}MB</span>
                  <el-button type="danger" size="small" @click="removeFile(tab, index)">删除</el-button>
                </div>
              </div>
            </div>
          </div>

          <!-- 上传选项弹窗 -->
          <el-dialog
            v-model="uploadOptionsVisible"
            title="选择上传方式"
            width="400px"
            class="upload-options-dialog"
          >
            <div class="upload-options-content">
              <el-button type="primary" @click="selectLocalUpload" class="option-btn">
                <el-icon><Upload /></el-icon>
                本地上传
              </el-button>
              <el-button type="success" @click="selectMaterialLibrary" class="option-btn">
                <el-icon><Folder /></el-icon>
                素材库
              </el-button>
            </div>
          </el-dialog>

          <!-- 本地上传弹窗 -->
          <el-dialog
            v-model="localUploadVisible"
            title="本地上传"
            width="600px"
            class="local-upload-dialog"
          >
            <el-upload
              class="video-upload"
              drag
              :auto-upload="true"
              :action="`${apiBaseUrl}/upload`"
              :on-success="(response, file) => handleUploadSuccess(response, file, currentUploadTab)"
              :on-error="handleUploadError"
              :before-upload="beforeLocalUpload"
              multiple
              accept="video/*,image/*,.mp4,.avi,.mov,.wmv,.flv,.mkv,.jpg,.jpeg,.png,.gif,.bmp,.webp"
              :headers="authHeaders"
            >
              <el-icon class="el-icon--upload"><Upload /></el-icon>
              <div class="el-upload__text">
                将视频或图片拖到此处，或<em>点击上传</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  支持视频（MP4/AVI 等）与图片（JPG/PNG 等），可上传多个文件；单文件建议不超过 2GB
                </div>
              </template>
            </el-upload>
          </el-dialog>

          <!-- 批量发布进度对话框 -->
          <el-dialog
            v-model="batchPublishDialogVisible"
            title="批量发布进度"
            width="500px"
            :close-on-click-modal="false"
            :close-on-press-escape="false"
            :show-close="false"
          >
            <div class="publish-progress">
              <el-progress 
                :percentage="publishProgress"
                :status="publishProgress === 100 ? 'success' : ''"
              />
              <div v-if="currentPublishingTab" class="current-publishing">
                正在发布：{{ currentPublishingTab.label }}
              </div>
              
              <!-- 发布结果列表 -->
              <div class="publish-results" v-if="publishResults.length > 0">
                <div 
                  v-for="(result, index) in publishResults" 
                  :key="index"
                  :class="['result-item', result.status]"
                >
                  <el-icon v-if="result.status === 'success'"><Check /></el-icon>
                  <el-icon v-else-if="result.status === 'error'"><Close /></el-icon>
                  <el-icon v-else><InfoFilled /></el-icon>
                  <span class="label">{{ result.label }}</span>
                  <span class="message">{{ result.message }}</span>
                </div>
              </div>
            </div>
            
            <template #footer>
              <div class="dialog-footer">
                <el-button 
                  @click="cancelBatchPublish" 
                  :disabled="publishProgress === 100"
                >
                  取消发布
                </el-button>
                <el-button 
                  type="primary" 
                  @click="batchPublishDialogVisible = false"
                  v-if="publishProgress === 100"
                >
                  关闭
                </el-button>
              </div>
            </template>
          </el-dialog>

          <!-- 素材库选择弹窗 -->
          <el-dialog
            v-model="materialLibraryVisible"
            title="选择素材"
            width="800px"
            class="material-library-dialog"
          >
            <div class="material-library-content">
              <el-checkbox-group v-model="selectedMaterials">
                <div class="material-list">
                  <div
                    v-for="material in materials"
                    :key="material.id"
                    class="material-item"
                  >
                    <el-checkbox :label="material.id" class="material-checkbox">
                      <div class="material-info">
                        <div class="material-name">{{ material.filename }}</div>
                        <div class="material-details">
                          <span class="file-size">{{ material.filesize }}MB</span>
                          <span class="upload-time">{{ material.upload_time }}</span>
                        </div>
                      </div>
                    </el-checkbox>
                  </div>
                </div>
              </el-checkbox-group>
            </div>
            <template #footer>
              <div class="dialog-footer">
                <el-button @click="materialLibraryVisible = false">取消</el-button>
                <el-button type="primary" @click="confirmMaterialSelection">确定</el-button>
              </div>
            </template>
          </el-dialog>

          <!-- 平台选择（可多选；账号按已选平台分组） -->
          <div class="platform-section">
            <h3>平台（可多选）</h3>
            <el-checkbox-group
              v-model="tab.selectedPlatforms"
              class="platform-radios"
              @change="handlePlatformChange(tab)"
            >
              <el-checkbox
                v-for="platform in platforms"
                :key="platform.key"
                :label="platform.key"
                class="platform-radio"
              >
                {{ platform.name }}
              </el-checkbox>
            </el-checkbox-group>
          </div>

          <!-- 账号选择 -->
          <div class="account-section">
            <h3>账号</h3>
            <div class="account-display">
              <div class="selected-accounts">
                <el-tag
                  v-for="(account, index) in tab.selectedAccounts"
                  :key="index"
                  closable
                  @close="removeAccount(tab, index)"
                  class="account-tag"
                >
                  {{ getAccountDisplayName(account) }}
                </el-tag>
              </div>
              <el-button 
                type="primary" 
                plain 
                @click="openAccountDialog(tab)"
                class="select-account-btn"
              >
                选择账号
              </el-button>
            </div>
            <p v-if="!tab.selectedPlatforms?.length" class="account-hint">请先选择发布平台</p>
          </div>

          <!-- 账号选择弹窗 -->
          <el-dialog
            v-model="accountDialogVisible"
            title="选择账号"
            width="600px"
            class="account-dialog"
          >
            <div class="account-dialog-content">
              <el-empty
                v-if="!currentTab?.selectedPlatforms?.length"
                description="请先在发布页选择平台"
              />
              <el-empty
                v-else-if="availableAccounts.length === 0"
                description="所选平台下暂无可用账号，请先在账号管理绑定"
              />
              <el-checkbox-group v-else v-model="tempSelectedAccounts">
                <div
                  v-for="group in availableAccountGroups"
                  :key="group.platform"
                  class="account-group"
                >
                  <div class="account-group-title">{{ group.platform }}</div>
                  <div class="account-list">
                    <el-checkbox
                      v-for="account in group.accounts"
                      :key="account.id"
                      :label="account.id"
                      class="account-item"
                    >
                      <div class="account-info">
                        <span class="account-name">{{ account.name }}</span>
                        <el-tag size="small" type="info">{{ account.platform }}</el-tag>
                      </div>
                    </el-checkbox>
                  </div>
                </div>
              </el-checkbox-group>
            </div>

            <template #footer>
              <div class="dialog-footer">
                <el-button @click="accountDialogVisible = false">取消</el-button>
                <el-button type="primary" @click="confirmAccountSelection">确定</el-button>
              </div>
            </template>
          </el-dialog>

          <!-- 原创声明 -->
          <div class="original-section">
            <el-checkbox
              v-model="tab.isOriginal"
              label="声明原创"
              class="original-checkbox"
            />
          </div>

          <!-- 草稿选项 (仅在视频号可见) -->
          <div v-if="tab.selectedPlatforms?.includes(2)" class="draft-section">
            <el-checkbox
              v-model="tab.isDraft"
              label="视频号仅保存草稿(用手机发布)"
              class="draft-checkbox"
            />
          </div>

          <!-- 标签 (仅在抖音可见) -->
          <div v-if="tab.selectedPlatforms?.includes(3)" class="product-section">
            <h3>商品链接</h3>
            <el-input
              v-model="tab.productTitle"
              type="text"
              :rows="1"
              placeholder="请输入商品名称"
              maxlength="200"
              class="product-name-input"
            />
            <el-input
              v-model="tab.productLink"
              type="text"
              :rows="1"
              placeholder="请输入商品链接"
              maxlength="200"
              class="product-link-input"
            />
          </div>

          <!-- 标题输入 -->
          <div class="title-section">
            <h3>标题</h3>
            <el-input
              v-model="tab.title"
              type="textarea"
              :rows="3"
              placeholder="请输入标题"
              maxlength="100"
              show-word-limit
              class="title-input"
            />
          </div>

          <!-- 话题输入 -->
          <div class="topic-section">
            <h3>话题</h3>
            <div class="topic-display">
              <div class="selected-topics">
                <el-tag
                  v-for="(topic, index) in tab.selectedTopics"
                  :key="index"
                  closable
                  @close="removeTopic(tab, index)"
                  class="topic-tag"
                >
                  #{{ topic }}
                </el-tag>
              </div>
              <el-button 
                type="primary" 
                plain 
                @click="openTopicDialog(tab)"
                class="select-topic-btn"
              >
                添加话题
              </el-button>
            </div>
          </div>

          <!-- 添加话题弹窗 -->
          <el-dialog
            v-model="topicDialogVisible"
            title="添加话题"
            width="600px"
            class="topic-dialog"
          >
            <div class="topic-dialog-content">
              <!-- 自定义话题输入 -->
              <div class="custom-topic-input">
                <el-input
                  v-model="customTopic"
                  placeholder="输入自定义话题"
                  class="custom-input"
                >
                  <template #prepend>#</template>
                </el-input>
                <el-button type="primary" @click="addCustomTopic">添加</el-button>
              </div>

              <!-- 推荐话题 -->
              <div class="recommended-topics">
                <h4>推荐话题</h4>
                <div class="topic-grid">
                  <el-button
                    v-for="topic in recommendedTopics"
                    :key="topic"
                    :type="currentTab?.selectedTopics?.includes(topic) ? 'primary' : 'default'"
                    @click="toggleRecommendedTopic(topic)"
                    class="topic-btn"
                  >
                    {{ topic }}
                  </el-button>
                </div>
              </div>
            </div>

            <template #footer>
              <div class="dialog-footer">
                <el-button @click="topicDialogVisible = false">取消</el-button>
                <el-button type="primary" @click="confirmTopicSelection">确定</el-button>
              </div>
            </template>
          </el-dialog>

          <div v-if="tab.selectedPlatforms?.includes(5)" class="tiktok-hint-section">
            <el-alert
              type="warning"
              :closable="false"
              show-icon
              title="TikTok 须本机助手立即发布"
              description="第一期仅支持立即发布（标题+标签+视频）。助手离线时不会服务器静默回退。多号建议一号一粘性/静态住宅或移动代理。"
            />
          </div>

          <!-- 定时发布（TikTok P1 仅立即发布） -->
          <div v-if="!tab.selectedPlatforms?.includes(5) || tab.selectedPlatforms?.length > 1" class="schedule-section">
            <h3>定时发布</h3>
            <div class="schedule-controls">
              <el-switch
                v-model="tab.scheduleEnabled"
                active-text="定时发布"
                inactive-text="立即发布"
              />
              <div v-if="tab.scheduleEnabled" class="schedule-settings">
                <div class="schedule-item">
                  <span class="label">每天发布视频数：</span>
                  <el-select v-model="tab.videosPerDay" placeholder="选择发布数量">
                    <el-option
                      v-for="num in 55"
                      :key="num"
                      :label="num"
                      :value="num"
                    />
                  </el-select>
                </div>
                <div class="schedule-item">
                  <span class="label">每天发布时间：</span>
                  <el-time-select
                    v-for="(time, index) in tab.dailyTimes"
                    :key="index"
                    v-model="tab.dailyTimes[index]"
                    start="00:00"
                    step="00:30"
                    end="23:30"
                    placeholder="选择时间"
                  />
                  <el-button
                    v-if="tab.dailyTimes.length < tab.videosPerDay"
                    type="primary"
                    size="small"
                    @click="tab.dailyTimes.push('10:00')"
                  >
                    添加时间
                  </el-button>
                </div>
                <div class="schedule-item">
                  <span class="label">开始天数：</span>
                  <el-select v-model="tab.startDays" placeholder="选择开始天数">
                    <el-option :label="'明天'" :value="0" />
                    <el-option :label="'后天'" :value="1" />
                  </el-select>
                </div>
              </div>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="action-buttons">
            <el-button size="small" @click="cancelPublish(tab)">取消</el-button>
            <el-button
              size="small"
              type="primary"
              @click="confirmPublish(tab)"
              :loading="tab.publishing || false"
            >
              {{ tab.publishing ? '发布中...' : '发布' }}
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onActivated } from 'vue'
import { Upload, Plus, Close, Folder } from '@element-plus/icons-vue'
import { ElMessage, ElNotification } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '@/components/common/PageHeader.vue'
import PageSection from '@/components/common/PageSection.vue'
import { useAccountStore } from '@sau/stores/account'
import { useAppStore } from '@sau/stores/app'
import { materialApi } from '@sau/api/material'
import { accountApi } from '@sau/api/account'
import { API_BASE_URL } from '@sau/utils/apiBase'
import { http } from '@sau/utils/request'

// API base URL
const apiBaseUrl = API_BASE_URL

// Authorization headers
const authHeaders = computed(() => ({
  'Authorization': `Bearer ${localStorage.getItem('sau_token') || ''}`
}))

// 当前激活的tab
const activeTab = ref('tab1')

// tab计数器
let tabCounter = 1

// 获取应用状态管理
const appStore = useAppStore()

// 上传相关状态
const uploadOptionsVisible = ref(false)
const localUploadVisible = ref(false)
const materialLibraryVisible = ref(false)
const currentUploadTab = ref(null)
const selectedMaterials = ref([])
const materials = computed(() => appStore.materials)

// 批量发布相关状态
const batchPublishing = ref(false)
const batchPublishMessage = ref('')
const batchPublishType = ref('info')

// 平台列表 - 对应后端type字段
const platforms = [
  { key: 3, name: '抖音' },
  { key: 4, name: '快手' },
  { key: 2, name: '视频号' },
  { key: 1, name: '小红书' },
  { key: 5, name: 'TikTok' }
]

const defaultTabInit = {
  name: 'tab1',
  label: '发布1',
  fileList: [], // 后端返回的文件名列表
  displayFileList: [], // 用于显示的文件列表
  selectedAccounts: [], // 选中的账号ID列表
  selectedPlatforms: [], // 选中的平台（多选）
  title: '',
  productLink: '', // 商品链接
  productTitle: '', // 商品名称
  selectedTopics: [], // 话题列表（不带#号）
  scheduleEnabled: false, // 定时发布开关
  videosPerDay: 1, // 每天发布视频数量
  dailyTimes: ['10:00'], // 每天发布时间点列表
  startDays: 0, // 从今天开始计算的发布天数，0表示明天，1表示后天
  publishStatus: null, // 发布状态，包含message和type
  publishing: false, // 发布状态，用于控制按钮loading效果
  isDraft: false, // 是否保存为草稿，仅视频号平台可见
  isOriginal: false // 是否标记为原创
}

// helper to create a fresh deep-copied tab from defaultTabInit
const makeNewTab = () => {
  // prefer structuredClone when available (newer browsers/node), fallback to JSON
  try {
    return typeof structuredClone === 'function' ? structuredClone(defaultTabInit) : JSON.parse(JSON.stringify(defaultTabInit))
  } catch (e) {
    return JSON.parse(JSON.stringify(defaultTabInit))
  }
}

// tab页数据 - 默认只有一个tab (use deep copy to avoid shared refs)
const tabs = reactive([
  makeNewTab()
])

// 账号相关状态
const accountDialogVisible = ref(false)
const tempSelectedAccounts = ref([])
const currentTab = ref(null)

// 获取账号状态管理
const accountStore = useAccountStore()

// 根据选择的平台获取可用账号列表
const platformMap = {
  3: '抖音',
  2: '视频号',
  1: '小红书',
  4: '快手',
  5: 'TikTok'
}

const getPlatformName = (platformKey) => platformMap[platformKey] || '未知'

const availableAccounts = computed(() => {
  const keys = currentTab.value?.selectedPlatforms || []
  if (!keys.length) return []
  const names = new Set(keys.map(k => platformMap[k]).filter(Boolean))
  return accountStore.accounts.filter(
    acc => names.has(acc.platform) && acc.status !== '异常'
  )
})

const availableAccountGroups = computed(() => {
  const groups = []
  const keys = currentTab.value?.selectedPlatforms || []
  for (const key of keys) {
    const name = platformMap[key]
    if (!name) continue
    const accounts = accountStore.accounts.filter(
      acc => acc.platform === name && acc.status !== '异常'
    )
    if (accounts.length) {
      groups.push({ platform: name, accounts })
    }
  }
  return groups
})

// 进入发布中心时加载账号列表（不依赖是否访问过账号管理页）
const fetchPublishAccounts = async () => {
  try {
    const res = await accountApi.getAccounts()
    if (res.code === 200 && res.data) {
      accountStore.setAccounts(res.data)
    }
  } catch (error) {
    console.error('获取账号列表失败:', error)
  }
}

onMounted(() => {
  if (accountStore.accounts.length > 0) return
  fetchPublishAccounts()
})

onActivated(() => {
  if (accountStore.accounts.length === 0) {
    fetchPublishAccounts()
  }
})

// 话题相关状态
const topicDialogVisible = ref(false)
const customTopic = ref('')

// 推荐话题列表
const recommendedTopics = [
  '游戏', '电影', '音乐', '美食', '旅行', '文化',
  '科技', '生活', '娱乐', '体育', '教育', '艺术',
  '健康', '时尚', '美妆', '摄影', '宠物', '汽车'
]

// 添加新tab
const addTab = () => {
  tabCounter++
  const newTab = makeNewTab()
  newTab.name = `tab${tabCounter}`
  newTab.label = `发布${tabCounter}`
  tabs.push(newTab)
  activeTab.value = newTab.name
}

// 删除tab
const removeTab = (tabName) => {
  const index = tabs.findIndex(tab => tab.name === tabName)
  if (index > -1) {
    tabs.splice(index, 1)
    // 如果删除的是当前激活的tab，切换到第一个tab
    if (activeTab.value === tabName && tabs.length > 0) {
      activeTab.value = tabs[0].name
    }
  }
}

// 从上传/素材库返回值中提取 videoFile 下的文件名
const extractVideoFilename = (value) => {
  if (!value) return ''
  if (typeof value === 'object') {
    return extractVideoFilename(value.filepath || value.path || value.filename || '')
  }
  return String(value).split(/[/\\]/).pop()
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

/** 轮询 GET /publish/jobs/:id，直到 success/failed 或超时 */
const pollPublishJob = async (jobId, timeoutMs = 180000) => {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      const res = await http.get(`/publish/jobs/${jobId}`)
      const job = res?.data
      if (job && (job.status === 'success' || job.status === 'failed')) {
        return job
      }
    } catch (err) {
      console.warn('poll publish job failed', jobId, err)
    }
    await sleep(2500)
  }
  return { status: 'failed', error: '发布超时，请稍后在平台后台确认是否已发出' }
}

const COOKIE_INVALID_RE = /cookie|已失效|失效|请先完成.*登录|重新登录|重新扫码/i
const isCookieInvalidError = (error) => {
  if (!error) return false
  return COOKIE_INVALID_RE.test(String(error))
}

const route = useRoute()
const router = useRouter()
const sauAccountsPath = computed(() => {
  const root = route.path.startsWith('/boss/sau') ? '/boss/sau' : '/employee/sau'
  return `${root}/accounts`
})

/** 账号登录失效时弹出醒目提示，引导去账号管理补充登录 */
const notifyCookieInvalid = (names) => {
  const label = names && names.length ? names.join('、') : '所选平台账号'
  ElNotification({
    title: '账号登录已失效',
    message: `${label} 的登录状态已失效，本次发布未成功。请前往「账号管理」重新扫码登录后再发布。`,
    type: 'warning',
    duration: 0,
    onClick: () => router.push(sauAccountsPath.value),
  })
}

// 处理文件上传成功
const handleUploadSuccess = (response, file, tab) => {
  if (response.code === 200) {
    const filePath = extractVideoFilename(response.data)
    if (!filePath) {
      ElMessage.error('上传成功但未获取到文件名，请重试')
      return
    }
    const filename = filePath
    
    // 保存文件信息到fileList，包含文件路径和其他信息
    const fileInfo = {
      name: file.name,
      url: materialApi.getMaterialPreviewUrl(filename), // 使用getMaterialPreviewUrl生成预览URL
      path: filePath,
      size: file.size,
      type: file.type
    }
    
    // 添加到文件列表
    tab.fileList.push(fileInfo)
    
    // 更新显示列表
    tab.displayFileList = [...tab.fileList.map(item => ({
      name: item.name,
      url: item.url
    }))]
    
    ElMessage.success('文件上传成功')
  } else {
    ElMessage.error(response.msg || '上传失败')
  }
}

// 处理文件上传失败
const beforeLocalUpload = (file) => {
  const maxBytes = 2 * 1024 * 1024 * 1024
  if (file.size > maxBytes) {
    ElMessage.error(`「${file.name}」超过 2GB 上限，请压缩后再上传`)
    return false
  }
  return true
}

const handleUploadError = (error) => {
  const status = error?.status || error?.response?.status
  const msg =
    (typeof error?.message === 'string' && /413|too large|Entity Too Large/i.test(error.message)
      ? '文件过大，超过服务器上传上限，请压缩后再试'
      : null) ||
    (status === 413
      ? '文件过大，超过服务器上传上限，请压缩后再试'
      : '文件上传失败，请检查网络或文件大小后重试')
  ElMessage.error(msg)
}

// 删除已上传文件
const removeFile = (tab, index) => {
  // 从文件列表中删除
  tab.fileList.splice(index, 1)
  
  // 更新显示列表
  tab.displayFileList = [...tab.fileList.map(item => ({
    name: item.name,
    url: item.url
  }))]
  
  ElMessage.success('文件删除成功')
}

// 话题相关方法
// 打开添加话题弹窗
const openTopicDialog = (tab) => {
  currentTab.value = tab
  topicDialogVisible.value = true
}

// 添加自定义话题
const addCustomTopic = () => {
  if (!customTopic.value.trim()) {
    ElMessage.warning('请输入话题内容')
    return
  }
  if (currentTab.value && !currentTab.value.selectedTopics.includes(customTopic.value.trim())) {
    currentTab.value.selectedTopics.push(customTopic.value.trim())
    customTopic.value = ''
    ElMessage.success('话题添加成功')
  } else {
    ElMessage.warning('话题已存在')
  }
}

// 切换推荐话题
const toggleRecommendedTopic = (topic) => {
  if (!currentTab.value) return
  
  const index = currentTab.value.selectedTopics.indexOf(topic)
  if (index > -1) {
    currentTab.value.selectedTopics.splice(index, 1)
  } else {
    currentTab.value.selectedTopics.push(topic)
  }
}

// 删除话题
const removeTopic = (tab, index) => {
  tab.selectedTopics.splice(index, 1)
}

// 确认添加话题
const confirmTopicSelection = () => {
  topicDialogVisible.value = false
  customTopic.value = ''
  currentTab.value = null
  ElMessage.success('添加话题完成')
}

// 账号选择相关方法
const handlePlatformChange = (tab) => {
  // 去掉已不在所选平台下的账号
  const names = new Set((tab.selectedPlatforms || []).map(k => platformMap[k]).filter(Boolean))
  tab.selectedAccounts = (tab.selectedAccounts || []).filter(id => {
    const acc = accountStore.accounts.find(a => a.id === id)
    return acc && names.has(acc.platform)
  })
  if ((tab.selectedPlatforms || []).includes(5)) {
    tab.isDraft = false
  }
  if ((tab.selectedPlatforms || []).length === 1 && tab.selectedPlatforms[0] === 5) {
    tab.scheduleEnabled = false
  }
}

// 打开账号选择弹窗
const openAccountDialog = (tab) => {
  if (!tab.selectedPlatforms?.length) {
    ElMessage.warning('请先选择发布平台')
    return
  }
  currentTab.value = tab
  tempSelectedAccounts.value = [...tab.selectedAccounts]
  accountDialogVisible.value = true
}

// 确认账号选择
const confirmAccountSelection = () => {
  if (currentTab.value) {
    currentTab.value.selectedAccounts = [...tempSelectedAccounts.value]
  }
  accountDialogVisible.value = false
  currentTab.value = null
  ElMessage.success('账号选择完成')
}

// 删除选中的账号
const removeAccount = (tab, index) => {
  tab.selectedAccounts.splice(index, 1)
}

// 获取账号显示名称
const getAccountDisplayName = (accountId) => {
  const account = accountStore.accounts.find(acc => acc.id === accountId)
  if (!account) return accountId
  return `${account.name}（${account.platform}）`
}

// 取消发布
const cancelPublish = (tab) => {
  ElMessage.info('已取消发布')
}

const fetchLocalAgentHealth = async () => {
  const empty = { running: false, agent_id: '', hostname: '' }
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 1200)
  try {
    const res = await fetch('http://127.0.0.1:19876/health', {
      signal: ctrl.signal,
      cache: 'no-store',
      mode: 'cors',
    })
    clearTimeout(timer)
    if (!res.ok) return empty
    const data = await res.json().catch(() => ({}))
    return {
      running: true,
      agent_id: String(data?.agent_id || '').trim(),
      hostname: String(data?.hostname || '').trim(),
    }
  } catch {
    clearTimeout(timer)
    return empty
  }
}

// 确认发布（支持多平台一键）
const confirmPublish = async (tab) => {
  if (tab.publishing) {
    throw new Error('正在发布中，请稍候...')
  }

  tab.publishing = true

  if (tab.fileList.length === 0) {
    ElMessage.error('请先上传素材文件')
    tab.publishing = false
    throw new Error('请先上传素材文件')
  }
  if (!tab.title.trim()) {
    ElMessage.error('请输入标题')
    tab.publishing = false
    throw new Error('请输入标题')
  }
  const platforms = [...(tab.selectedPlatforms || [])]
  if (!platforms.length) {
    ElMessage.error('请选择发布平台')
    tab.publishing = false
    throw new Error('请选择发布平台')
  }
  if (tab.selectedAccounts.length === 0) {
    ElMessage.error('请选择发布账号')
    tab.publishing = false
    throw new Error('请选择发布账号')
  }

  // 每个平台至少 1 个账号
  for (const type of platforms) {
    const pname = platformMap[type]
    const has = tab.selectedAccounts.some(id => {
      const acc = accountStore.accounts.find(a => a.id === id)
      return acc && acc.platform === pname
    })
    if (!has) {
      ElMessage.error(`平台「${pname}」尚未选择账号`)
      tab.publishing = false
      throw new Error(`平台「${pname}」尚未选择账号`)
    }
  }

  const includesTikTok = platforms.includes(5)
  let localAgentId = ''
  if (includesTikTok) {
    const local = await fetchLocalAgentHealth()
    if (!local.running || !local.agent_id) {
      ElMessage.error('发布 TikTok 前请先启动并连接本机助手')
      tab.publishing = false
      throw new Error('本机助手未就绪')
    }
    localAgentId = local.agent_id
    const noProxy = tab.selectedAccounts.some(accountId => {
      const account = accountStore.accounts.find(acc => acc.id === accountId)
      return account && account.platform === 'TikTok' && !account.proxyUrl
    })
    if (noProxy) {
      ElMessage.warning('所选 TikTok 账号未配置代理（直连可用；多号矩阵建议一号一粘性代理）')
    }
  }

  const fileList = tab.fileList.map(file => extractVideoFilename(file.path)).filter(Boolean)
  const batch = platforms.map(type => {
    const pname = platformMap[type]
    const isTikTok = type === 5
    const accountList = tab.selectedAccounts
      .map(accountId => accountStore.accounts.find(acc => acc.id === accountId))
      .filter(acc => acc && acc.platform === pname)
      .map(acc => acc.filePath)
    return {
      type,
      title: tab.title,
      tags: tab.selectedTopics,
      fileList,
      accountList,
      enableTimer: isTikTok ? 0 : (tab.scheduleEnabled ? 1 : 0),
      videosPerDay: isTikTok ? 1 : (tab.scheduleEnabled ? tab.videosPerDay || 1 : 1),
      dailyTimes: isTikTok ? ['10:00'] : (tab.scheduleEnabled ? tab.dailyTimes || ['10:00'] : ['10:00']),
      startDays: isTikTok ? 0 : (tab.scheduleEnabled ? tab.startDays || 0 : 0),
      category: tab.isOriginal ? 1 : 0,
      productLink: type === 3 ? (tab.productLink.trim() || '') : '',
      productTitle: type === 3 ? (tab.productTitle.trim() || '') : '',
      isDraft: type === 2 ? tab.isDraft : false,
      agentId: isTikTok ? localAgentId : undefined,
    }
  })

  // 发布前先校验所选账号 cookie，失效账号及时提示，避免提交后才发现
  const invalidAccounts = []
  await Promise.all(
    (tab.selectedAccounts || []).map(async (accountId) => {
      const acc = accountStore.accounts.find((a) => a.id === accountId)
      if (!acc) return
      try {
        const res = await http.post('/checkAccount', { id: accountId })
        if (res?.data?.valid === false) invalidAccounts.push(`${acc.name}（${acc.platform}）`)
      } catch (e) {
        // 校验接口异常不阻塞发布
      }
    })
  )
  if (invalidAccounts.length) {
    const names = [...new Set(invalidAccounts)]
    notifyCookieInvalid(names)
    tab.publishStatus = { message: `以下账号登录已失效，请先重新扫码登录：${names.join('、')}`, type: 'error' }
    tab.publishing = false
    throw new Error(`以下账号登录已失效，请先重新扫码登录：${names.join('、')}`)
  }

  try {
    const data = await http.post('/postVideoBatch', batch)
    let results = data?.data?.results || []

    // 轮询后台任务，拿到最终成功/失败（助手或服务器 Playwright）
    const pending = results.filter((r) => r.job_id && Number(r.code) === 200)
    if (pending.length) {
      tab.publishStatus = {
        message: '任务已提交，正在发布中…',
        type: 'info',
      }
      const polled = await Promise.all(
        pending.map(async (item) => {
          const finalJob = await pollPublishJob(item.job_id, 600000)
          if (!finalJob) return item
          const ok = finalJob.status === 'success'
          const cookieInvalid = !ok && (
            isCookieInvalidError(finalJob.error) ||
            !!(finalJob.detail && finalJob.detail.cookie_invalid_accounts && finalJob.detail.cookie_invalid_accounts.length)
          )
          return {
            ...item,
            code: ok ? 200 : 500,
            msg: ok
              ? (item.msg || '发布完成')
              : (cookieInvalid
                  ? `「${getPlatformName(item.type)}」账号登录状态已失效，请前往账号管理重新扫码登录后再发布`
                  : (finalJob.error || '发布失败')),
            runtime: finalJob.runtime || item.runtime,
            cookieInvalid,
          }
        })
      )
      const byJob = Object.fromEntries(polled.map((r) => [r.job_id, r]))
      results = results.map((r) => (r.job_id && byJob[r.job_id] ? byJob[r.job_id] : r))
    }

    const cookieInvalidResults = results.filter((r) => r.cookieInvalid)
    if (cookieInvalidResults.length) {
      notifyCookieInvalid(cookieInvalidResults.map((r) => getPlatformName(r.type)))
    }

    const lines = results.map((r) => {
      const name = getPlatformName(r.type)
      return `${name}: ${Number(r.code) === 200 ? '✓' : '✗'} ${r.msg || ''}`
    })
    const allOk = results.length > 0 && results.every((r) => Number(r.code) === 200)
    if (allOk) {
      ElMessage.success('全部平台发布成功')
      tab.publishStatus = { message: lines.join('；') || '发布成功', type: 'success' }
      tab.fileList = []
      tab.displayFileList = []
      tab.title = ''
      tab.selectedTopics = []
      tab.selectedAccounts = []
      tab.scheduleEnabled = false
    } else {
      ElMessage.warning('部分平台失败')
      tab.publishStatus = { message: lines.join('；') || '部分失败', type: 'error' }
    }
  } catch (error) {
    console.error('发布错误:', error)
    tab.publishStatus = {
      message: `发布失败：${error.message || '请检查网络连接'}`,
      type: 'error'
    }
    throw error
  } finally {
    tab.publishing = false
  }
}

// 显示上传选项
const showUploadOptions = (tab) => {
  currentUploadTab.value = tab
  uploadOptionsVisible.value = true
}

// 选择本地上传
const selectLocalUpload = () => {
  uploadOptionsVisible.value = false
  localUploadVisible.value = true
}

// 选择素材库
const selectMaterialLibrary = async () => {
  uploadOptionsVisible.value = false
  
  // 如果素材库为空，先获取素材数据
  if (materials.value.length === 0) {
    try {
      const response = await materialApi.getAllMaterials()
      if (response.code === 200) {
        appStore.setMaterials(response.data)
      } else {
        ElMessage.error('获取素材列表失败')
        return
      }
    } catch (error) {
      console.error('获取素材列表出错:', error)
      ElMessage.error('获取素材列表失败')
      return
    }
  }
  
  selectedMaterials.value = []
  materialLibraryVisible.value = true
}

// 确认素材选择
const confirmMaterialSelection = () => {
  if (selectedMaterials.value.length === 0) {
    ElMessage.warning('请选择至少一个素材')
    return
  }
  
  if (currentUploadTab.value) {
    // 将选中的素材添加到当前tab的文件列表
    selectedMaterials.value.forEach(materialId => {
      const material = materials.value.find(m => m.id === materialId)
      if (material) {
        const fileInfo = {
          name: material.filename,
          url: materialApi.getMaterialPreviewUrl(material.file_path.split('/').pop()),
          path: extractVideoFilename(material.file_path),
          size: material.filesize * 1024 * 1024, // 转换为字节
          type: 'video/mp4'
        }
        
        // 检查是否已存在相同文件
        const exists = currentUploadTab.value.fileList.some(file => file.path === fileInfo.path)
        if (!exists) {
          currentUploadTab.value.fileList.push(fileInfo)
        }
      }
    })
    
    // 更新显示列表
    currentUploadTab.value.displayFileList = [...currentUploadTab.value.fileList.map(item => ({
      name: item.name,
      url: item.url
    }))]
  }
  
  const addedCount = selectedMaterials.value.length
  materialLibraryVisible.value = false
  selectedMaterials.value = []
  currentUploadTab.value = null
  ElMessage.success(`已添加 ${addedCount} 个素材`)
}

// 批量发布对话框状态
const batchPublishDialogVisible = ref(false)
const currentPublishingTab = ref(null)
const publishProgress = ref(0)
const publishResults = ref([])
const isCancelled = ref(false)

// 取消批量发布
const cancelBatchPublish = () => {
  isCancelled.value = true
  ElMessage.info('正在取消发布...')
}

// 批量发布方法
const batchPublish = async () => {
  if (batchPublishing.value) return
  
  batchPublishing.value = true
  currentPublishingTab.value = null
  publishProgress.value = 0
  publishResults.value = []
  isCancelled.value = false
  batchPublishDialogVisible.value = true
  
  try {
    for (let i = 0; i < tabs.length; i++) {
      if (isCancelled.value) {
        publishResults.value.push({
          label: tabs[i].label,
          status: 'cancelled',
          message: '已取消'
        })
        continue
      }

      const tab = tabs[i]
      currentPublishingTab.value = tab
      publishProgress.value = Math.floor((i / tabs.length) * 100)
      
      try {
        await confirmPublish(tab)
        publishResults.value.push({
          label: tab.label,
          status: 'success',
          message: '发布成功'
        })
      } catch (error) {
        publishResults.value.push({
          label: tab.label,
          status: 'error',
          message: error.message
        })
        // 不立即返回，继续显示发布结果
      }
    }
    
    publishProgress.value = 100
    
    // 统计发布结果
    const successCount = publishResults.value.filter(r => r.status === 'success').length
    const failCount = publishResults.value.filter(r => r.status === 'error').length
    const cancelCount = publishResults.value.filter(r => r.status === 'cancelled').length
    
    if (isCancelled.value) {
      ElMessage.warning(`发布已取消：${successCount}个成功，${failCount}个失败，${cancelCount}个未执行`)
    } else if (failCount > 0) {
      ElMessage.error(`发布完成：${successCount}个成功，${failCount}个失败`)
    } else {
      ElMessage.success('所有Tab发布成功')
      setTimeout(() => {
        batchPublishDialogVisible.value = false
      }, 1000)
    }
    
  } catch (error) {
    console.error('批量发布出错:', error)
    ElMessage.error('批量发布出错，请重试')
  } finally {
    batchPublishing.value = false
    isCancelled.value = false
  }
}
</script>

<style lang="scss" scoped>
@use '@sau/styles/variables.scss' as *;

.publish-center {
  display: flex;
  flex-direction: column;
  height: 100%;
  
  // Tab管理区域
  .tab-management {
    padding: 0;

    .tab-header {
      display: flex;
      align-items: flex-start;
      gap: 15px;
      
      .tab-list {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        flex: 1;
        min-width: 0;
        
        .tab-item {
           display: flex;
           align-items: center;
           gap: 6px;
           padding: 6px 12px;
           background-color: #f5f7fa;
           border: 1px solid #dcdfe6;
           border-radius: 4px;
           cursor: pointer;
           transition: all 0.3s;
           font-size: 14px;
           height: 32px;
           
           &:hover {
             background-color: #ecf5ff;
             border-color: #b3d8ff;
           }
           
           &.active {
             background-color: #409eff;
             border-color: #409eff;
             color: #fff;
             
             .close-icon {
               color: #fff;
               
               &:hover {
                 background-color: rgba(255, 255, 255, 0.2);
               }
             }
           }
           
           .close-icon {
             padding: 2px;
             border-radius: 2px;
             cursor: pointer;
             transition: background-color 0.3s;
             font-size: 12px;
             
             &:hover {
               background-color: rgba(0, 0, 0, 0.1);
             }
           }
         }
       }
       
      .tab-actions {
        display: flex;
        gap: 10px;
        flex-shrink: 0;
        
        .add-tab-btn,
        .batch-publish-btn {
          display: flex;
          align-items: center;
          gap: 4px;
          height: 32px;
          padding: 6px 12px;
          font-size: 14px;
          white-space: nowrap;
        }
      }
    }
  }
  
  // 批量发布进度对话框样式
  .publish-progress {
    padding: 20px;
    
    .current-publishing {
      margin: 15px 0;
      text-align: center;
      color: #606266;
    }

    .publish-results {
      margin-top: 20px;
      border-top: 1px solid #EBEEF5;
      padding-top: 15px;
      max-height: 300px;
      overflow-y: auto;

      .result-item {
        display: flex;
        align-items: center;
        padding: 8px 0;
        color: #606266;

        .el-icon {
          margin-right: 8px;
        }

        .label {
          margin-right: 10px;
          font-weight: 500;
        }

        .message {
          color: #909399;
        }

        &.success {
          color: #67C23A;
        }

        &.error {
          color: #F56C6C;
        }

        &.cancelled {
          color: #909399;
        }
      }
    }
  }

  .dialog-footer {
    text-align: right;
  }
  
  // 内容区域
  .publish-content {
    flex: 1;
    background-color: #fff;
    border-radius: 4px;
    box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
    padding: 20px;
    
    .tab-content-wrapper {
      display: flex;
      justify-content: center;
      
      .tab-content {
        width: 100%;
        max-width: 800px;
        
        h3 {
          font-size: 16px;
          font-weight: 500;
          color: $text-primary;
          margin: 0 0 10px 0;
        }
        
        .upload-section,
        .account-section,
        .platform-section,
        .title-section,
        .product-section,
        .topic-section,
        .schedule-section {
          margin-bottom: 30px;
        }

        .product-section {
          .product-name-input,
          .product-link-input {
            margin-bottom: 5px;
          }
        }
        
        .video-upload {
          width: 100%;
          
          :deep(.el-upload-dragger) {
            width: 100%;
            height: 180px;
          }
        }
        
        .account-input {
          max-width: 400px;
        }

        .account-hint {
          margin: 8px 0 0;
          font-size: 13px;
          color: $text-secondary;
        }
        
        .platform-buttons {
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
          
          .platform-btn {
            min-width: 80px;
          }
        }
        
        .title-input {
          max-width: 600px;
        }
        
        .topic-display {
          display: flex;
          flex-direction: column;
          gap: 12px;
          
          .selected-topics {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            min-height: 32px;
            
            .topic-tag {
              font-size: 14px;
            }
          }
          
          .select-topic-btn {
            align-self: flex-start;
          }
        }
        
        .schedule-controls {
          display: flex;
          flex-direction: column;
          gap: 15px;

          .schedule-settings {
            margin-top: 15px;
            padding: 15px;
            background-color: #f5f7fa;
            border-radius: 4px;

            .schedule-item {
              display: flex;
              align-items: center;
              margin-bottom: 15px;

              &:last-child {
                margin-bottom: 0;
              }

              .label {
                min-width: 120px;
                margin-right: 10px;
              }

              .el-time-select {
                margin-right: 10px;
              }

              .el-button {
                margin-left: 10px;
              }
            }
          }
        }
        
        .action-buttons {
          display: flex;
          justify-content: flex-end;
          gap: 10px;
          margin-top: 30px;
          padding-top: 20px;
          border-top: 1px solid #ebeef5;
        }

        .draft-section {
          margin: 20px 0;

          .draft-checkbox {
            display: block;
            margin: 10px 0;
          }
        }

        .original-section {
          margin: 10px 0 20px;

          .original-checkbox {
            display: block;
            margin: 10px 0;
          }
        }
      }
    }
  }

  // 已上传文件列表样式
  .uploaded-files {
    margin-top: 20px;
    
    h4 {
      font-size: 16px;
      font-weight: 500;
      margin-bottom: 12px;
      color: #303133;
    }
    
    .file-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
      
      .file-item {
        display: flex;
        align-items: center;
        padding: 10px 15px;
        background-color: #f5f7fa;
        border-radius: 4px;
        
        .el-link {
          margin-right: 10px;
          max-width: 300px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        
        .file-size {
          color: #909399;
          font-size: 13px;
          margin-right: auto;
        }
      }
    }
  }
  
  // 添加话题弹窗样式
  .topic-dialog {
    .topic-dialog-content {
      .custom-topic-input {
        display: flex;
        gap: 12px;
        margin-bottom: 24px;
        
        .custom-input {
          flex: 1;
        }
      }
      
      .recommended-topics {
        h4 {
          margin: 0 0 16px 0;
          font-size: 16px;
          font-weight: 500;
          color: #303133;
        }
        
        .topic-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
          gap: 12px;
          
          .topic-btn {
            height: 36px;
            font-size: 14px;
            border-radius: 6px;
            min-width: 100px;
            padding: 0 12px;
            white-space: nowrap;
            text-align: center;
            display: flex;
            align-items: center;
            justify-content: center;
            
            &.el-button--primary {
              background-color: #409eff;
              border-color: #409eff;
              color: white;
            }
          }
        }
      }
    }
    
    .dialog-footer {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
    }
  }
}
</style>
