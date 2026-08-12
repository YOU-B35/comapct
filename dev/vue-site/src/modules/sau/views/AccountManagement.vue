<template>
  <div class="account-management">
    <PageHeader
      title="账号管理"
      eyebrow="自媒体"
      description="管理各平台自媒体账号与本机助手"
    />

    <PageSection title="本机助手">
      <div class="login-agent-panel">
        <span class="agent-dot" :class="loginAgentOnline ? 'online' : 'offline'"></span>
        <div class="login-agent-panel-main">
          <div class="login-agent-panel-title">本机浏览器环境（含 TikTok）</div>
          <div class="login-agent-panel-desc">
            <template v-if="agentConnectHint">{{ agentConnectHint }}</template>
            <template v-else-if="loginAgentOnline">
              {{ currentAgentStatusText }}
            </template>
            <template v-else-if="agentInstalledHint">
              请点击右侧「连接助手」
            </template>
            <template v-else>
              首次使用：点「下载助手」保存 zip → 解压 → 双击 SETUP.bat → 再点「连接助手」。已安装也可随时「下载/更新助手」覆盖原目录。若提示版本过旧，必须更新后再连接，否则多机登录会串台。
            </template>
          </div>
          <div v-if="loginAgentAgents.length > 0" class="login-agent-picker">
            <el-select v-model="activeAgentId" size="small" style="width: 320px" placeholder="选择要使用的助手">
              <el-option
                v-for="a in loginAgentAgentsLabeled"
                :key="a.agent_id"
                :label="a.label"
                :value="a.agent_id"
              />
            </el-select>
            <el-button size="small" @click="activateAgent(activeAgentId)">设为当前助手</el-button>
          </div>
        </div>
        <div class="login-agent-panel-actions">
          <el-button
            size="small"
            :loading="agentDownloading"
            @click="downloadLoginAgent"
          >
            {{ agentInstalledHint ? '下载/更新助手' : '下载助手' }}
          </el-button>
          <el-button type="primary" size="small" :loading="agentLaunching" @click="connectLoginAgent">
            连接助手
          </el-button>
        </div>
      </div>
    </PageSection>

    <PageSection title="账号列表">
    <div class="account-tabs">
      <el-tabs v-model="activeTab" class="account-tabs-nav">
        <el-tab-pane label="全部" name="all">
          <div class="account-list-container">
            <div class="account-search">
              <el-input
                v-model="searchKeyword"
                placeholder="输入名称或账号搜索"
                prefix-icon="Search"
                clearable
                @clear="handleSearch"
                @input="handleSearch"
              />
              <div class="action-buttons">
                <el-button type="primary" @click="handleAddAccount">添加账号</el-button>
                <el-button type="info" @click="fetchAccounts" :loading="false">
                  <el-icon :class="{ 'is-loading': appStore.isAccountRefreshing }"><Refresh /></el-icon>
                  <span v-if="appStore.isAccountRefreshing">同步中</span>
                  <span v-else>同步账号</span>
                </el-button>
              </div>
            </div>
            
            <div v-if="filteredAccounts.length > 0" class="account-list">
              <el-table :data="filteredAccounts" style="width: 100%">
                <el-table-column label="头像" width="80">
                  <template #default="scope">
                    <el-avatar :src="getDefaultAvatar(scope.row.name)" :size="40" />
                  </template>
                </el-table-column>
                <el-table-column prop="name" label="名称" width="180" />
                <el-table-column prop="platform" label="平台">
                  <template #default="scope">
                    <el-tag
                      :type="getPlatformTagType(scope.row.platform)"
                      effect="plain"
                    >
                      {{ scope.row.platform }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="状态">
                  <template #default="scope">
                    <el-tag
                      :type="getStatusTagType(scope.row.status)"
                      effect="plain"
                      :class="{'clickable-status': isStatusClickable(scope.row.status)}"
                      @click="handleStatusClick(scope.row)"
                    >
                      <el-icon :class="scope.row.status === '验证中' ? 'is-loading' : ''" v-if="scope.row.status === '验证中'">
                        <Loading />
                      </el-icon>
                      {{ scope.row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作">
                  <template #default="scope">
                    <el-button size="small" @click="handleEdit(scope.row)">编辑</el-button>
                    <el-button size="small" type="primary" :icon="Download" @click="handleDownloadCookie(scope.row)">下载Cookie</el-button>
                    <el-button size="small" type="info" :icon="Upload" @click="handleUploadCookie(scope.row)">上传Cookie</el-button>
                    <el-button size="small" type="danger" @click="handleDelete(scope.row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            
            <div v-else class="empty-data">
              <el-empty description="暂无账号数据" />
            </div>
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="快手" name="kuaishou">
          <div class="account-list-container">
            <div class="account-search">
              <el-input
                v-model="searchKeyword"
                placeholder="输入名称或账号搜索"
                prefix-icon="Search"
                clearable
                @clear="handleSearch"
                @input="handleSearch"
              />
              <div class="action-buttons">
                <el-button type="primary" @click="handleAddAccount">添加账号</el-button>
                <el-button type="info" @click="fetchAccounts" :loading="false">
                  <el-icon :class="{ 'is-loading': appStore.isAccountRefreshing }"><Refresh /></el-icon>
                  <span v-if="appStore.isAccountRefreshing">同步中</span>
                  <span v-else>同步账号</span>
                </el-button>
              </div>
            </div>
            
            <div v-if="filteredKuaishouAccounts.length > 0" class="account-list">
              <el-table :data="filteredKuaishouAccounts" style="width: 100%">
                <el-table-column label="头像" width="80">
                  <template #default="scope">
                    <el-avatar :src="getDefaultAvatar(scope.row.name)" :size="40" />
                  </template>
                </el-table-column>
                <el-table-column prop="name" label="名称" width="180" />
                <el-table-column prop="platform" label="平台">
                  <template #default="scope">
                    <el-tag
                      :type="getPlatformTagType(scope.row.platform)"
                      effect="plain"
                    >
                      {{ scope.row.platform }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="状态">
                  <template #default="scope">
                    <el-tag
                      :type="getStatusTagType(scope.row.status)"
                      effect="plain"
                      :class="{'clickable-status': isStatusClickable(scope.row.status)}"
                      @click="handleStatusClick(scope.row)"
                    >
                      <el-icon :class="scope.row.status === '验证中' ? 'is-loading' : ''" v-if="scope.row.status === '验证中'">
                        <Loading />
                      </el-icon>
                      {{ scope.row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作">
                  <template #default="scope">
                    <el-button size="small" @click="handleEdit(scope.row)">编辑</el-button>
                    <el-button size="small" type="primary" :icon="Download" @click="handleDownloadCookie(scope.row)">下载Cookie</el-button>
                    <el-button size="small" type="info" :icon="Upload" @click="handleUploadCookie(scope.row)">上传Cookie</el-button>
                    <el-button size="small" type="danger" @click="handleDelete(scope.row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            
            <div v-else class="empty-data">
              <el-empty description="暂无快手账号数据" />
            </div>
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="抖音" name="douyin">
          <div class="account-list-container">
            <div class="account-search">
              <el-input
                v-model="searchKeyword"
                placeholder="输入名称或账号搜索"
                prefix-icon="Search"
                clearable
                @clear="handleSearch"
                @input="handleSearch"
              />
              <div class="action-buttons">
                <el-button type="primary" @click="handleAddAccount">添加账号</el-button>
                <el-button type="info" @click="fetchAccounts" :loading="false">
                  <el-icon :class="{ 'is-loading': appStore.isAccountRefreshing }"><Refresh /></el-icon>
                  <span v-if="appStore.isAccountRefreshing">同步中</span>
                  <span v-else>同步账号</span>
                </el-button>
              </div>
            </div>
            
            <div v-if="filteredDouyinAccounts.length > 0" class="account-list">
              <el-table :data="filteredDouyinAccounts" style="width: 100%">
                <el-table-column label="头像" width="80">
                  <template #default="scope">
                    <el-avatar :src="getDefaultAvatar(scope.row.name)" :size="40" />
                  </template>
                </el-table-column>
                <el-table-column prop="name" label="名称" width="180" />
                <el-table-column prop="platform" label="平台">
                  <template #default="scope">
                    <el-tag
                      :type="getPlatformTagType(scope.row.platform)"
                      effect="plain"
                    >
                      {{ scope.row.platform }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="状态">
                  <template #default="scope">
                    <el-tag
                      :type="getStatusTagType(scope.row.status)"
                      effect="plain"
                      :class="{'clickable-status': isStatusClickable(scope.row.status)}"
                      @click="handleStatusClick(scope.row)"
                    >
                      <el-icon :class="scope.row.status === '验证中' ? 'is-loading' : ''" v-if="scope.row.status === '验证中'">
                        <Loading />
                      </el-icon>
                      {{ scope.row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作">
                  <template #default="scope">
                    <el-button size="small" @click="handleEdit(scope.row)">编辑</el-button>
                    <el-button size="small" type="primary" :icon="Download" @click="handleDownloadCookie(scope.row)">下载Cookie</el-button>
                    <el-button size="small" type="info" :icon="Upload" @click="handleUploadCookie(scope.row)">上传Cookie</el-button>
                    <el-button size="small" type="danger" @click="handleDelete(scope.row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            
            <div v-else class="empty-data">
              <el-empty description="暂无抖音账号数据" />
            </div>
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="视频号" name="channels">
          <div class="account-list-container">
            <div class="account-search">
              <el-input
                v-model="searchKeyword"
                placeholder="输入名称或账号搜索"
                prefix-icon="Search"
                clearable
                @clear="handleSearch"
                @input="handleSearch"
              />
              <div class="action-buttons">
                <el-button type="primary" @click="handleAddAccount">添加账号</el-button>
                <el-button type="info" @click="fetchAccounts" :loading="false">
                  <el-icon :class="{ 'is-loading': appStore.isAccountRefreshing }"><Refresh /></el-icon>
                  <span v-if="appStore.isAccountRefreshing">同步中</span>
                  <span v-else>同步账号</span>
                </el-button>
              </div>
            </div>
            
            <div v-if="filteredChannelsAccounts.length > 0" class="account-list">
              <el-table :data="filteredChannelsAccounts" style="width: 100%">
                <el-table-column label="头像" width="80">
                  <template #default="scope">
                    <el-avatar :src="getDefaultAvatar(scope.row.name)" :size="40" />
                  </template>
                </el-table-column>
                <el-table-column prop="name" label="名称" width="180" />
                <el-table-column prop="platform" label="平台">
                  <template #default="scope">
                    <el-tag
                      :type="getPlatformTagType(scope.row.platform)"
                      effect="plain"
                    >
                      {{ scope.row.platform }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="状态">
                  <template #default="scope">
                    <el-tag
                      :type="getStatusTagType(scope.row.status)"
                      effect="plain"
                      :class="{'clickable-status': isStatusClickable(scope.row.status)}"
                      @click="handleStatusClick(scope.row)"
                    >
                      <el-icon :class="scope.row.status === '验证中' ? 'is-loading' : ''" v-if="scope.row.status === '验证中'">
                        <Loading />
                      </el-icon>
                      {{ scope.row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作">
                  <template #default="scope">
                    <el-button size="small" @click="handleEdit(scope.row)">编辑</el-button>
                    <el-button size="small" type="primary" :icon="Download" @click="handleDownloadCookie(scope.row)">下载Cookie</el-button>
                    <el-button size="small" type="info" :icon="Upload" @click="handleUploadCookie(scope.row)">上传Cookie</el-button>
                    <el-button size="small" type="danger" @click="handleDelete(scope.row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            
            <div v-else class="empty-data">
              <el-empty description="暂无视频号账号数据" />
            </div>
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="小红书" name="xiaohongshu">
          <div class="account-list-container">
            <div class="account-search">
              <el-input
                v-model="searchKeyword"
                placeholder="输入名称或账号搜索"
                prefix-icon="Search"
                clearable
                @clear="handleSearch"
                @input="handleSearch"
              />
              <div class="action-buttons">
                <el-button type="primary" @click="handleAddAccount">添加账号</el-button>
                <el-button type="info" @click="fetchAccounts" :loading="false">
                  <el-icon :class="{ 'is-loading': appStore.isAccountRefreshing }"><Refresh /></el-icon>
                  <span v-if="appStore.isAccountRefreshing">同步中</span>
                  <span v-else>同步账号</span>
                </el-button>
              </div>
            </div>
            
            <div v-if="filteredXiaohongshuAccounts.length > 0" class="account-list">
              <el-table :data="filteredXiaohongshuAccounts" style="width: 100%">
                <el-table-column label="头像" width="80">
                  <template #default="scope">
                    <el-avatar :src="getDefaultAvatar(scope.row.name)" :size="40" />
                  </template>
                </el-table-column>
                <el-table-column prop="name" label="名称" width="180" />
                <el-table-column prop="platform" label="平台">
                  <template #default="scope">
                    <el-tag
                      :type="getPlatformTagType(scope.row.platform)"
                      effect="plain"
                    >
                      {{ scope.row.platform }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="状态">
                  <template #default="scope">
                    <el-tag
                      :type="getStatusTagType(scope.row.status)"
                      effect="plain"
                      :class="{'clickable-status': isStatusClickable(scope.row.status)}"
                      @click="handleStatusClick(scope.row)"
                    >
                      <el-icon :class="scope.row.status === '验证中' ? 'is-loading' : ''" v-if="scope.row.status === '验证中'">
                        <Loading />
                      </el-icon>
                      {{ scope.row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作">
                  <template #default="scope">
                    <el-button size="small" @click="handleEdit(scope.row)">编辑</el-button>
                    <el-button size="small" type="primary" :icon="Download" @click="handleDownloadCookie(scope.row)">下载Cookie</el-button>
                    <el-button size="small" type="info" :icon="Upload" @click="handleUploadCookie(scope.row)">上传Cookie</el-button>
                    <el-button size="small" type="danger" @click="handleDelete(scope.row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            
            <div v-else class="empty-data">
              <el-empty description="暂无小红书账号数据" />
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="TikTok" name="tiktok">
          <div class="account-list-container">
            <div class="account-search">
              <el-input
                v-model="searchKeyword"
                placeholder="输入名称或账号搜索"
                prefix-icon="Search"
                clearable
                @clear="handleSearch"
                @input="handleSearch"
              />
              <div class="action-buttons">
                <el-button type="primary" @click="handleAddAccount">添加账号</el-button>
                <el-button type="info" @click="fetchAccounts" :loading="false">
                  <el-icon :class="{ 'is-loading': appStore.isAccountRefreshing }"><Refresh /></el-icon>
                  <span v-if="appStore.isAccountRefreshing">同步中</span>
                  <span v-else>同步账号</span>
                </el-button>
              </div>
            </div>

            <div v-if="filteredTikTokAccounts.length > 0" class="account-list">
              <el-table :data="filteredTikTokAccounts" style="width: 100%">
                <el-table-column label="头像" width="80">
                  <template #default="scope">
                    <el-avatar :src="getDefaultAvatar(scope.row.name)" :size="40" />
                  </template>
                </el-table-column>
                <el-table-column prop="name" label="名称" width="180" />
                <el-table-column prop="platform" label="平台">
                  <template #default="scope">
                    <el-tag :type="getPlatformTagType(scope.row.platform)" effect="plain">
                      {{ scope.row.platform }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="代理" min-width="140">
                  <template #default="scope">
                    <span class="proxy-cell">{{ scope.row.proxyUrl ? '已配置' : '直连' }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="状态">
                  <template #default="scope">
                    <el-tag
                      :type="getStatusTagType(scope.row.status)"
                      effect="plain"
                      :class="{'clickable-status': isStatusClickable(scope.row.status)}"
                      @click="handleStatusClick(scope.row)"
                    >
                      <el-icon :class="scope.row.status === '验证中' ? 'is-loading' : ''" v-if="scope.row.status === '验证中'">
                        <Loading />
                      </el-icon>
                      {{ scope.row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作">
                  <template #default="scope">
                    <el-button size="small" @click="handleEdit(scope.row)">编辑</el-button>
                    <el-button size="small" type="primary" :icon="Download" @click="handleDownloadCookie(scope.row)">下载Cookie</el-button>
                    <el-button size="small" type="info" :icon="Upload" @click="handleUploadCookie(scope.row)">上传Cookie</el-button>
                    <el-button size="small" type="danger" @click="handleDelete(scope.row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <div v-else class="empty-data">
              <el-empty description="暂无 TikTok 账号数据" />
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
    </PageSection>

    <!-- 添加/编辑账号对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogType === 'add' ? '添加账号' : '编辑账号'"
      width="560px"
      :close-on-click-modal="false"
      :close-on-press-escape="!sseConnecting"
      :show-close="!sseConnecting"
    >
      <el-form :model="accountForm" label-width="80px" :rules="rules" ref="accountFormRef">
        <el-form-item label="平台" prop="platform">
          <el-select 
            v-model="accountForm.platform" 
            placeholder="请选择平台" 
            style="width: 100%"
            :disabled="dialogType === 'edit' || sseConnecting"
          >
            <el-option label="快手" value="快手" />
            <el-option label="抖音" value="抖音" />
            <el-option label="视频号" value="视频号" />
            <el-option label="小红书" value="小红书" />
            <el-option label="TikTok" value="TikTok" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input 
            v-model="accountForm.name" 
            placeholder="请输入账号名称" 
            :disabled="sseConnecting"
          />
        </el-form-item>

        <template v-if="accountForm.platform === 'TikTok'">
          <el-form-item label="代理">
            <el-input
              v-model="accountForm.proxyUrl"
              placeholder="建议留空：跟随本机 Clash；高级可选填 http://user:pass@host:port"
              :disabled="sseConnecting"
            />
          </el-form-item>
          <el-alert
            type="success"
            :closable="false"
            show-icon
            class="tiktok-proxy-alert"
            title="推荐：留空代理，用本机 Clash"
            description="不填代理时，助手会自动连接本机 Clash 混合端口（常见 7897）。请保持 Clash Verge 开启且规则下能打开 TikTok，然后直接扫码。无需再配 Decodo。"
          />
          <el-alert
            v-if="accountForm.proxyUrl"
            type="warning"
            :closable="false"
            show-icon
            class="tiktok-proxy-alert"
            title="已填写账号代理"
            description="将强制走该代理而非 Clash。若出现 ERR_EMPTY_RESPONSE，请清空代理改用 Clash，或单独排查该代理能否访问 TikTok。"
          />
        </template>
        
        <!-- 添加账号：本机助手状态 -->
        <div v-if="dialogType === 'add' && accountForm.platform" class="douyin-agent-bar">
          <span class="agent-dot" :class="loginAgentOnline ? 'online' : 'offline'"></span>
          <template v-if="loginAgentOnline">
            <span>助手已连接，确认后将打开本机 Chrome 扫码</span>
          </template>
          <template v-else>
            <span>助手未连接，</span>
            <el-button type="primary" size="small" link :loading="agentLaunching" @click="connectLoginAgent">
              点此连接
            </el-button>
          </template>
        </div>

        <!-- 二维码显示区域 -->
        <div v-if="sseConnecting" class="qrcode-container">
          <el-alert
            v-if="loginHint"
            type="info"
            :closable="false"
            show-icon
            class="login-hint-alert"
            :title="loginHint"
          />
          <div v-if="loginAgentOnline && !qrCodeData && !loginStatus" class="loading-wrapper">
            <el-icon class="is-loading"><Refresh /></el-icon>
            <span>等待本机 Chrome 打开…</span>
          </div>
          <div v-else-if="qrCodeData && !loginStatus" class="qrcode-wrapper">
            <p class="qrcode-tip">{{ loginHint || '请使用对应平台APP扫描二维码登录' }}</p>
            <img :src="qrCodeData" alt="登录二维码" class="qrcode-image" />
          </div>
          <div v-else-if="!qrCodeData && !loginStatus" class="loading-wrapper">
            <el-icon class="is-loading"><Refresh /></el-icon>
            <span>请求中...</span>
          </div>
          <div v-else-if="loginStatus === '200'" class="success-wrapper">
            <el-icon><CircleCheckFilled /></el-icon>
            <span>添加成功</span>
          </div>
          <div v-else-if="loginStatus === '500'" class="error-wrapper">
            <el-icon><CircleCloseFilled /></el-icon>
            <span>{{ loginHint || '添加失败，请稍后再试' }}</span>
          </div>
        </div>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button 
            type="primary" 
            @click="submitAccountForm" 
            :loading="sseConnecting" 
            :disabled="sseConnecting"
          >
            {{ sseConnecting ? '请求中' : '确认' }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { Refresh, CircleCheckFilled, CircleCloseFilled, Download, Upload, Loading } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/common/PageHeader.vue'
import PageSection from '@/components/common/PageSection.vue'
import { accountApi } from '@sau/api/account'
import { useAccountStore } from '@sau/stores/account'
import { useAppStore } from '@sau/stores/app'
import { buildApiUrl, API_BASE_URL } from '@sau/utils/apiBase'
import { http } from '@sau/utils/request'

// 获取账号状态管理
const accountStore = useAccountStore()
// 获取应用状态管理
const appStore = useAppStore()

// 当前激活的标签页
const activeTab = ref('all')

// 搜索关键词
const searchKeyword = ref('')

// 获取账号数据（快速，不验证）——直接展示库里状态，不再整表刷成「验证中」
const fetchAccountsQuick = async () => {
  try {
    const res = await accountApi.getAccounts()
    if (res.code === 200 && res.data) {
      accountStore.setAccounts(res.data)
    }
  } catch (error) {
    console.error('快速获取账号数据失败:', error)
  }
}

// 获取账号数据（带验证，仅手动同步）
const fetchAccounts = async () => {
  if (appStore.isAccountRefreshing) return

  appStore.setAccountRefreshing(true)

  // 仅在真正发起校验时标记「验证中」
  const pending = accountStore.accounts.map((acc) => ({
    ...acc,
    status: '验证中',
  }))
  accountStore.accounts.splice(0, accountStore.accounts.length, ...pending)

  try {
    const res = await accountApi.getValidAccounts(true)
    if (res.code === 200 && res.data) {
      accountStore.setAccounts(res.data)
      ElMessage.success('账号同步完成')
      if (appStore.isFirstTimeAccountManagement) {
        appStore.setAccountManagementVisited()
      }
    } else {
      ElMessage.error('获取账号数据失败')
      await fetchAccountsQuick()
    }
  } catch (error) {
    console.error('获取账号数据失败:', error)
    ElMessage.error('获取账号数据失败')
    await fetchAccountsQuick()
  } finally {
    appStore.setAccountRefreshing(false)
  }
}

const ACCOUNT_MONITOR_INTERVAL_MS = 5 * 60 * 1000
const OFFLINE_PROMPT_COOLDOWN_MS = 30 * 60 * 1000
let accountMonitorTimer = null
let accountMonitorRunning = false
const offlinePromptedIds = new Set()
const offlinePromptedAt = new Map()

const stopAccountMonitor = () => {
  if (accountMonitorTimer) {
    clearInterval(accountMonitorTimer)
    accountMonitorTimer = null
  }
}

const promptReLogin = (row) => {
  ElMessageBox.confirm(
    `账号「${row.name}」(${row.platform}) 已掉线，是否立即重新登录？`,
    '账号掉线提醒',
    {
      confirmButtonText: '重新登录',
      cancelButtonText: '稍后',
      type: 'warning',
    }
  )
    .then(() => {
      handleReLogin(row)
    })
    .catch(() => {})
}

const runAccountMonitor = async () => {
  if (accountMonitorRunning || sseConnecting.value || dialogVisible.value) return

  const candidates = accountStore.accounts.filter((account) => account.status === '正常')
  if (candidates.length === 0) return

  accountMonitorRunning = true
  try {
    for (const account of candidates) {
      if (sseConnecting.value || dialogVisible.value) break

      const res = await accountApi.checkAccount(account.id)
      if (res.code !== 200 || !res.data) continue

      const { valid, account: accountRow } = res.data
      if (valid) {
        offlinePromptedIds.delete(account.id)
        offlinePromptedAt.delete(account.id)
        continue
      }

      accountStore.updateAccount(account.id, { status: '异常' })

      const now = Date.now()
      const lastPromptAt = offlinePromptedAt.get(account.id) || 0
      if (!offlinePromptedIds.has(account.id) || now - lastPromptAt >= OFFLINE_PROMPT_COOLDOWN_MS) {
        offlinePromptedIds.add(account.id)
        offlinePromptedAt.set(account.id, now)
        promptReLogin({ ...account, status: '异常' })
      }
    }
  } catch (error) {
    console.error('账号掉线监测失败:', error)
  } finally {
    accountMonitorRunning = false
  }
}

const startAccountMonitor = () => {
  stopAccountMonitor()
  accountMonitorTimer = setInterval(runAccountMonitor, ACCOUNT_MONITOR_INTERVAL_MS)
}

onMounted(() => {
  fetchAccountsQuick()
  fetchLoginAgentStatus()
  void requestPairCode(true)
  loginAgentTimer = setInterval(fetchLoginAgentStatus, 5000)
  startAccountMonitor()
})

onBeforeUnmount(() => {
  if (loginAgentTimer) {
    clearInterval(loginAgentTimer)
    loginAgentTimer = null
  }
  closeSSEConnection()
  stopAccountMonitor()
})

// 获取平台标签类型
const getPlatformTagType = (platform) => {
  const typeMap = {
    '快手': 'success',
    '抖音': 'danger',
    '视频号': 'warning',
    '小红书': 'info',
    'TikTok': 'danger'
  }
  return typeMap[platform] || 'info'
}

// 判断状态是否可点击（异常状态可点击）
const isStatusClickable = (status) => {
  return status === '异常'; // 只有异常状态可点击，验证中不可点击
}

// 获取状态标签类型
const getStatusTagType = (status) => {
  if (status === '验证中') {
    return 'info'; // 验证中使用灰色
  } else if (status === '正常') {
    return 'success'; // 正常使用绿色
  } else {
    return 'danger'; // 无效使用红色
  }
}

// 处理状态点击事件
const handleStatusClick = (row) => {
  if (isStatusClickable(row.status)) {
    // 触发重新登录流程
    handleReLogin(row)
  }
}

// 过滤后的账号列表
const filteredAccounts = computed(() => {
  if (!searchKeyword.value) return accountStore.accounts
  return accountStore.accounts.filter(account =>
    account.name.includes(searchKeyword.value)
  )
})

// 按平台过滤的账号列表
const filteredKuaishouAccounts = computed(() => {
  return filteredAccounts.value.filter(account => account.platform === '快手')
})

const filteredDouyinAccounts = computed(() => {
  return filteredAccounts.value.filter(account => account.platform === '抖音')
})

const filteredChannelsAccounts = computed(() => {
  return filteredAccounts.value.filter(account => account.platform === '视频号')
})

const filteredXiaohongshuAccounts = computed(() => {
  return filteredAccounts.value.filter(account => account.platform === '小红书')
})

const filteredTikTokAccounts = computed(() => {
  return filteredAccounts.value.filter(account => account.platform === 'TikTok')
})

// 搜索处理
const handleSearch = () => {
  // 搜索逻辑已通过计算属性实现
}

// 对话框相关
const dialogVisible = ref(false)
const dialogType = ref('add') // 'add' 或 'edit'
const accountFormRef = ref(null)

// 账号表单
const accountForm = reactive({
  id: null,
  name: '',
  platform: '',
  status: '正常',
  proxyUrl: ''
})

// 选择平台时刷新助手状态（须在 accountForm 声明之后）
watch(() => accountForm.platform, (p) => {
  if (p) {
    fetchLoginAgentStatus()
  }
})

// 表单验证规则
const rules = {
  platform: [{ required: true, message: '请选择平台', trigger: 'change' }],
  name: [{ required: true, message: '请输入账号名称', trigger: 'blur' }]
}

// SSE连接状态
const sseConnecting = ref(false)
const qrCodeData = ref('')
const loginStatus = ref('')
const loginHint = ref('')
const loginAgentOnline = ref(false)
const loginAgentInfo = ref({ hostname: '', platform: '', agent_id: '' })
const loginAgentAgents = ref([])
const activeAgentId = ref('')
const localAgentHealth = ref({ running: false, agent_id: '', hostname: '', protocol: 0 })

const formatAgentLabel = (a, localId) => {
  const host = a.hostname || a.agent_id || '未知主机'
  const shortId = String(a.agent_id || '').slice(0, 8)
  const isLocal = localId && String(a.agent_id) === String(localId)
  const tag = isLocal ? '本机' : '其他'
  return `${tag} · ${host}${shortId ? ` (${shortId})` : ''}`
}

const loginAgentAgentsLabeled = computed(() => {
  const localId = localAgentHealth.value?.agent_id || ''
  return (loginAgentAgents.value || []).map(a => ({
    ...a,
    label: formatAgentLabel(a, localId),
    isLocal: !!(localId && String(a.agent_id) === String(localId)),
  }))
})

const currentAgentStatusText = computed(() => {
  if (!loginAgentOnline.value) return '助手未连接'
  const localId = localAgentHealth.value?.agent_id || ''
  const activeId = activeAgentId.value || loginAgentInfo.value?.agent_id || ''
  const host = loginAgentInfo.value?.hostname || activeId || '未知'
  if (localId && String(activeId) === String(localId)) {
    return `当前助手：本机 ${host}`
  }
  if (localId && activeId && String(activeId) !== String(localId)) {
    return `当前助手：其他机 ${host}（请点「连接助手」切回本机）`
  }
  return `当前助手：${host}`
})
const pairCode = ref('')
const agentLaunching = ref(false)
const agentDownloading = ref(false)
const agentConnectHint = ref('')
const agentInstalledHint = ref(localStorage.getItem('automedia_agent_installed') === '1')
let loginAgentTimer = null

const getApiServerUrl = () => {
  if (API_BASE_URL && API_BASE_URL.startsWith('http')) {
    return API_BASE_URL
  }
  const base = API_BASE_URL || '/api'
  return `${window.location.origin}${base.startsWith('/') ? base : `/${base}`}`
}

const toBase64Url = (text) => {
  const bytes = new TextEncoder().encode(text)
  let bin = ''
  bytes.forEach((b) => { bin += String.fromCharCode(b) })
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

const buildAgentLaunchUrl = (code, server) => {
  // 不用 &，避免 Windows 协议唤起时被 cmd 拆参
  return `automedia-agent://c/${encodeURIComponent(code)}/${toBase64Url(server)}`
}

const waitAgentOnline = async (maxMs = 20000) => {
  const start = Date.now()
  while (Date.now() - start < maxMs) {
    await fetchLoginAgentStatus()
    if (loginAgentOnline.value) {
      return true
    }
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }
  return false
}

const requestPairCode = async (silent = false) => {
  try {
    const res = await http.post('/login-agent/pair-code')
    if (res.code === 200 && res.data?.code) {
      pairCode.value = res.data.code
      if (!silent) {
        ElMessage.success(`连接码 ${res.data.code}（10 分钟内有效）`)
      }
      return true
    }
    if (!silent) {
      ElMessage.error(res.msg || '获取连接码失败')
    }
  } catch {
    if (!silent) ElMessage.error('获取连接码失败')
  }
  return false
}

const triggerProtocol = (url) => {
  try {
    const iframe = document.createElement('iframe')
    iframe.style.display = 'none'
    iframe.src = url
    document.body.appendChild(iframe)
    setTimeout(() => iframe.remove(), 4000)
  } catch {
    // ignore
  }
  try {
    const link = document.createElement('a')
    link.href = url
    document.body.appendChild(link)
    link.click()
    link.remove()
  } catch {
    // ignore
  }
}

const probeLocalAgent = async () => {
  const info = await fetchLocalAgentHealth()
  return !!info.running
}

const fetchLocalAgentHealth = async () => {
  // https 站点探测本机 http://127.0.0.1 需要 Private Network Access + CORS
  const empty = { running: false, agent_id: '', hostname: '', protocol: 0 }
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
      protocol: Number(data?.protocol || 0) || 0,
    }
  } catch {
    clearTimeout(timer)
    // no-cors fallback: only know that port responds, cannot read agent_id
    try {
      const ctrl2 = new AbortController()
      const timer2 = setTimeout(() => ctrl2.abort(), 800)
      await fetch('http://127.0.0.1:19876/health', {
        signal: ctrl2.signal,
        cache: 'no-store',
        mode: 'no-cors',
      })
      clearTimeout(timer2)
      return { running: true, agent_id: '', hostname: '', protocol: 0 }
    } catch {
      return empty
    }
  }
}

/** 本机助手是否达到多机隔离协议（protocol>=2） */
const isLocalAgentUpToDate = (local) => {
  if (!local?.running) return false
  // 旧包 / CORS 失败时 protocol=0：无法确认版本 → 视为过旧
  if (!local.protocol || local.protocol < 2) return false
  return true
}

const promptAgentUpdateRequired = async (reason) => {
  try {
    await ElMessageBox.confirm(
      `${reason}\n\n请立即「下载/更新助手」→ 解压覆盖原目录 → 再运行 SETUP.bat → 回到本页点「连接助手」。\n\n旧版助手无法隔离多台电脑，登录窗口可能开到别人机器上。`,
      '助手需要更新',
      {
        confirmButtonText: '立即下载更新',
        cancelButtonText: '稍后',
        type: 'warning',
        distinguishCancelAndClose: true,
      },
    )
    await downloadLoginAgent()
  } catch {
    // 用户取消
  }
}

/** TikTok：强制校验服务器 active 助手 == 本机助手，避免误发到开发机。 */
const ensureTikTokActiveIsLocal = async () => {
  await fetchLoginAgentStatus()
  const local = await fetchLocalAgentHealth()
  if (!local.running) {
    ElMessage.warning('本机助手未运行，请先启动并点「连接助手」')
    return false
  }
  if (!isLocalAgentUpToDate(local)) {
    await promptAgentUpdateRequired('本机助手版本过旧或未就绪，无法安全添加 TikTok。')
    return false
  }
  if (!activeAgentId.value) {
    ElMessage.warning('尚未选定当前助手，请先点「连接助手」把本机设为当前助手')
    return false
  }
  if (String(activeAgentId.value) !== String(local.agent_id)) {
    const remoteHost = loginAgentInfo.value?.hostname || activeAgentId.value
    const localHost = local.hostname || '本机'
    ElMessage.error(
      `当前助手是「${remoteHost}」，不是本机「${localHost}」。请先点「连接助手」切换到本机后再添加 TikTok。`,
    )
    return false
  }
  return true
}

const pairLocalAgentSilent = async (code, server) => {
  // 静默 POST，避免 window.open 弹出 ERR_EMPTY_RESPONSE 吓人页面
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 8000)
  try {
    const res = await fetch('http://127.0.0.1:19876/pair', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, server }),
      signal: ctrl.signal,
      mode: 'cors',
      cache: 'no-store',
    })
    clearTimeout(timer)
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(text || `pair HTTP ${res.status}`)
    }
    const data = await res.json().catch(() => ({}))
    if (data && data.ok === false) {
      throw new Error(data.msg || '配对失败')
    }
    // 本机配对成功后，把本机 agent 设为当前助手（防止被其它在线机器抢单）
    const agentId = (data && data.agent_id) ? data.agent_id : ''
    if (agentId) {
      try {
        await activateAgent(agentId)
      } catch (e) {
        // ignore activation errors; status poll will still work
      }
    }
    return true
  } catch (err) {
    clearTimeout(timer)
    throw err
  }
}

const connectLoginAgent = async () => {
  if (agentLaunching.value) return
  agentLaunching.value = true
  agentConnectHint.value = '正在准备连接…'
  try {
    // 必须始终重新配对当前这台机器：
    // 仅凭“服务器上已有助手在线”无法证明在线的就是当前浏览器所在主机。
    // 否则会把旧的开发机误当成当前助手，导致 TikTok 登录继续在开发机弹窗。
    await fetchLoginAgentStatus()

    // 每次点击用新连接码，避免旧码失效
    const ok = await requestPairCode(true)
    if (!ok || !pairCode.value) {
      agentConnectHint.value = ''
      ElMessage.error('获取连接码失败，请刷新页面后重试')
      return
    }

    const server = getApiServerUrl()
    const code = pairCode.value
    const protocolUrl = buildAgentLaunchUrl(code, server)

    const localUp = await probeLocalAgent()
    if (localUp) {
      const preHealth = await fetchLocalAgentHealth()
      localAgentHealth.value = preHealth
      // 旧助手：进程在跑但报不出 agent_id → 必须先更新，否则多机仍会串台
      if (preHealth.running && !isLocalAgentUpToDate(preHealth)) {
        agentConnectHint.value = ''
        await promptAgentUpdateRequired(
          '检测到本机助手正在运行，但版本过旧（不支持多机隔离）。',
        )
        return
      }
      agentConnectHint.value = '正在连接本机助手…'
      try {
        await pairLocalAgentSilent(code, server)
      } catch (pairErr) {
        console.warn('silent pair failed, try protocol', pairErr)
        // 静默失败再唤起协议；不再 window.open 127.0.0.1（易出 ERR_EMPTY_RESPONSE）
        triggerProtocol(protocolUrl)
      }
    } else {
      agentConnectHint.value = '本机助手未运行，正在尝试唤起…'
      ElMessage.info('正在唤起本机助手。若无反应，请先运行桌面上的「AutoMedia抖音助手」或 SETUP.bat')
      triggerProtocol(protocolUrl)
    }

    if (await waitAgentOnline(25000)) {
      localStorage.setItem('automedia_agent_installed', '1')
      agentInstalledHint.value = true
      await fetchLoginAgentStatus()
      const local = await fetchLocalAgentHealth()
      localAgentHealth.value = local
      if (!isLocalAgentUpToDate(local)) {
        agentConnectHint.value = ''
        await promptAgentUpdateRequired(
          '服务器侧已看到助手在线，但本机助手仍是旧版（未上报隔离标识）。请更新本机助手后再连接。',
        )
        return
      }
      if (local?.agent_id && String(activeAgentId.value) === String(local.agent_id)) {
        agentConnectHint.value = ''
        ElMessage.success(`已连接本机：${local.hostname || local.agent_id}`)
      } else if (local?.agent_id) {
        // 强制切到本机
        await activateAgent(local.agent_id)
        agentConnectHint.value = ''
        ElMessage.success(`已切换到本机：${local.hostname || local.agent_id}`)
      } else {
        agentConnectHint.value = ''
        ElMessage.success('助手已连接')
      }
      return
    }

    await fetchLoginAgentStatus()
    if (loginAgentOnline.value) {
      const local = await fetchLocalAgentHealth()
      localAgentHealth.value = local
      if (!isLocalAgentUpToDate(local)) {
        agentConnectHint.value = ''
        await promptAgentUpdateRequired(
          '当前连上的可能是其他电脑上的旧助手。请更新并启动本机助手后再点「连接助手」。',
        )
        return
      }
      if (local?.agent_id && String(activeAgentId.value) !== String(local.agent_id)) {
        await activateAgent(local.agent_id)
      }
      agentConnectHint.value = ''
      ElMessage.success(
        local?.hostname
          ? `助手已连接（本机 ${local.hostname}）`
          : '助手已连接',
      )
      return
    }

    agentConnectHint.value = ''
    await ElMessageBox.alert(
      '还没连上本机助手。\n\n1. 确认本机助手进程已启动（桌面「AutoMedia抖音助手」或 SETUP.bat）\n2. Clash 请保持运行即可，但把 127.0.0.1 / Chrome 设为直连，勿开 TUN 劫持本机环回\n3. 刷新页面后再点「连接助手」\n4. 允许弹窗与自定义协议\n\n填写了 TikTok 账号代理后，登录 Chrome 会走该代理访问 TikTok，不依赖 Clash 出国。',
      '未检测到本机助手',
      { confirmButtonText: '知道了', type: 'warning' },
    )
  } catch (e) {
    agentConnectHint.value = ''
    if (e !== 'cancel' && e?.toString?.() !== 'cancel') {
      ElMessage.error('连接助手失败，请重试')
    }
  } finally {
    agentLaunching.value = false
  }
}

const downloadLoginAgent = async () => {
  if (agentDownloading.value) return
  agentDownloading.value = true
  try {
    const infoRes = await http.get('/login-agent/installer-info')
    if (infoRes.code !== 200 || (!infoRes.data?.download_url && !infoRes.data?.proxy_path)) {
      ElMessage.error(infoRes.msg || '助手下载地址未配置')
      return
    }
    const cached = !!infoRes.data?.cached
    const directUrl = infoRes.data?.download_url
    const token = localStorage.getItem('sau_token') || ''

    let href
    if (cached) {
      // 服务器有本地缓存，走同源代理（快）
      href = `${buildApiUrl('/login-agent/download')}?token=${encodeURIComponent(token)}`
    } else if (directUrl) {
      // 服务器无缓存，直接跳转外链（避免服务器从 GitHub 拉取超时）
      href = directUrl
    } else {
      href = `${buildApiUrl('/login-agent/download')}?token=${encodeURIComponent(token)}`
    }

    const link = document.createElement('a')
    link.href = href
    link.rel = 'noopener'
    document.body.appendChild(link)
    link.click()
    link.remove()
    localStorage.setItem('automedia_agent_installed', '1')
    agentInstalledHint.value = true
    ElMessage.success({
      message: cached
        ? '已开始高速下载（服务器本地缓存）。完成后解压覆盖原助手目录，再双击 SETUP.bat。'
        : '已开始下载（来自 GitHub）。完成后解压覆盖并运行 SETUP.bat。',
      duration: 8000,
    })
  } catch (error) {
    console.error('下载助手失败:', error)
    try {
      const infoRes = await http.get('/login-agent/installer-info')
      const target = infoRes?.data?.download_url
      if (target) {
        window.open(target, '_blank', 'noopener,noreferrer')
        ElMessage.warning('同源下载失败，已打开直链。若较慢请换网络或稍后重试。')
        return
      }
    } catch {
      // ignore
    }
    ElMessage.error(error?.message || '下载助手失败，请重试')
  } finally {
    agentDownloading.value = false
  }
}

const fetchLoginAgentStatus = async () => {
  try {
    const local = await fetchLocalAgentHealth()
    localAgentHealth.value = local
    const res = await http.get('/login-agent/status')
    if (res.code === 200 && res.data) {
      const active = res.data.active || res.data
      loginAgentOnline.value = !!active?.online
      loginAgentInfo.value = active || { hostname: '', platform: '', agent_id: '' }
      loginAgentAgents.value = Array.isArray(res.data.agents) ? res.data.agents : []
      activeAgentId.value = (active && active.agent_id) ? active.agent_id : ''
    } else {
      loginAgentOnline.value = false
    }
  } catch {
    loginAgentOnline.value = false
  }
}

const activateAgent = async (agentId) => {
  const id = (agentId || '').toString().trim()
  if (!id) return
  const res = await http.post('/login-agent/activate', { agent_id: id })
  if (res.code === 200) {
    await fetchLoginAgentStatus()
    ElMessage.success(`已设为当前助手：${loginAgentInfo.value?.hostname || id}`)
  } else {
    ElMessage.error(res.msg || '设置当前助手失败')
  }
}

// 添加账号
const handleAddAccount = () => {
  dialogType.value = 'add'
  Object.assign(accountForm, {
    id: null,
    name: '',
    platform: '',
    status: '正常',
    proxyUrl: ''
  })
  // 重置SSE状态
  sseConnecting.value = false
  qrCodeData.value = ''
  loginStatus.value = ''
  loginHint.value = ''
  pairCode.value = ''
  fetchLoginAgentStatus()
  dialogVisible.value = true
}

// 编辑账号
const handleEdit = (row) => {
  dialogType.value = 'edit'
  Object.assign(accountForm, {
    id: row.id,
    name: row.name,
    platform: row.platform,
    status: row.status,
    proxyUrl: row.proxyUrl || ''
  })
  dialogVisible.value = true
}

// 删除账号
const handleDelete = (row) => {
  ElMessageBox.confirm(
    `确定要删除账号 ${row.name} 吗？`,
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  )
    .then(async () => {
      try {
        // 调用API删除账号
        const response = await accountApi.deleteAccount(row.id)

        if (response.code === 200) {
          // 从状态管理中删除账号
          accountStore.deleteAccount(row.id)
          ElMessage({
            type: 'success',
            message: '删除成功',
          })
        } else {
          ElMessage.error(response.msg || '删除失败')
        }
      } catch (error) {
        console.error('删除账号失败:', error)
        ElMessage.error('删除账号失败')
      }
    })
    .catch(() => {
      // 取消删除
    })
}

// 下载Cookie文件
const handleDownloadCookie = (row) => {
  // 从后端获取Cookie文件
  const downloadUrl = buildApiUrl(`/downloadCookie?filePath=${encodeURIComponent(row.filePath)}`)

  // 创建一个隐藏的链接来触发下载
  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = `${row.name}_cookie.json`
  link.target = '_blank'
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// 上传Cookie文件
const handleUploadCookie = (row) => {
  // 创建一个隐藏的文件输入框
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.style.display = 'none'
  document.body.appendChild(input)

  input.onchange = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    // 检查文件类型
    if (!file.name.endsWith('.json')) {
      ElMessage.error('请选择JSON格式的Cookie文件')
      document.body.removeChild(input)
      return
    }

    try {
      // 创建FormData对象
      const formData = new FormData()
      formData.append('file', file)
      formData.append('id', row.id)
      formData.append('platform', row.platform)

      // 使用统一的http封装发送上传请求
      const result = await http.upload('/uploadCookie', formData)

      ElMessage.success('Cookie文件上传成功')
      // 刷新账号列表以显示更新
      fetchAccounts()
    } catch (error) {
      ElMessage.error('Cookie文件上传失败')
    } finally {
      document.body.removeChild(input)
    }
  }

  input.click()
}

// 重新登录账号
const handleReLogin = async (row) => {
  // 设置表单信息
  dialogType.value = 'edit'
  Object.assign(accountForm, {
    id: row.id,
    name: row.name,
    platform: row.platform,
    status: row.status,
    proxyUrl: row.proxyUrl || ''
  })

  // 重置SSE状态
  sseConnecting.value = false
  qrCodeData.value = ''
  loginStatus.value = ''
  loginHint.value = ''

  // 显示对话框
  dialogVisible.value = true

  if (row.platform === 'TikTok') {
    const okLocal = await ensureTikTokActiveIsLocal()
    if (!okLocal) return
  }

  // 立即开始登录流程
  setTimeout(() => {
    connectSSE(row.platform, row.name, row.id)
  }, 300)
}

// 获取默认头像
const getDefaultAvatar = (name) => {
  // 使用简单的默认头像，可以基于用户名生成不同的颜色
  return `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=random`
}

// SSE事件源对象
let eventSource = null
let loginTimeoutId = null
let sseFinished = false

// 关闭SSE连接
const closeSSEConnection = () => {
  if (loginTimeoutId) {
    clearTimeout(loginTimeoutId)
    loginTimeoutId = null
  }
  if (eventSource) {
    try {
      eventSource.close()
    } catch {
      // ignore
    }
    eventSource = null
  }
}

// 建立SSE连接
const connectSSE = (platform, name, accountDbId = null) => {
  if (sseConnecting.value) {
    ElMessage.warning('登录流程进行中，请勿重复提交')
    return
  }

  // 关闭可能存在的连接
  closeSSEConnection()

  // 设置连接状态
  sseConnecting.value = true
  sseFinished = false
  qrCodeData.value = ''
  loginStatus.value = ''
  loginHint.value = ''

  // 获取平台类型编号
  const platformTypeMap = {
    '小红书': '1',
    '视频号': '2',
    '抖音': '3',
    '快手': '4',
    'TikTok': '5'
  }

  const type = platformTypeMap[platform] || '1'

  // 创建SSE连接（重新登录必须带 accountId，避免插出同名重复账号）
  // _nonce 防止 EventSource 异常自动重连再次派发登录
  const token = localStorage.getItem('sau_token') || ''
  const dbId = accountDbId || accountForm.id || ''
  const nonce = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  let url = buildApiUrl(`/login?type=${type}&id=${encodeURIComponent(name)}&token=${encodeURIComponent(token)}&_nonce=${encodeURIComponent(nonce)}`)
  if (dbId) {
    url += `&accountId=${encodeURIComponent(dbId)}`
  }
  if (platform === 'TikTok' && accountForm.proxyUrl) {
    url += `&proxyUrl=${encodeURIComponent(accountForm.proxyUrl)}`
  }
  // TikTok：把本机校验过的 active agent_id 传给后端，双保险防串台
  if (platform === 'TikTok' && activeAgentId.value) {
    url += `&agentId=${encodeURIComponent(activeAgentId.value)}`
  }

  eventSource = new EventSource(url)

  // 8 分钟无终态则自动结束，避免 SSE 断开后一直显示「请求中」
  loginTimeoutId = setTimeout(() => {
    if (sseConnecting.value && !loginStatus.value) {
      ElMessage.error('登录等待超时，请关闭后重试')
      sseFinished = true
      closeSSEConnection()
      sseConnecting.value = false
    }
  }, 8 * 60 * 1000)

  // 监听消息
  eventSource.onmessage = (event) => {
    const data = event.data

    if (data === '200' || data === '500') {
      sseFinished = true
      loginStatus.value = data
      // 立刻关掉，阻止浏览器 EventSource 自动重连再次打 /login
      closeSSEConnection()

      // 如果登录成功
      if (data === '200') {
        offlinePromptedIds.delete(accountForm.id)
        offlinePromptedAt.delete(accountForm.id)
        setTimeout(() => {
          setTimeout(() => {
            dialogVisible.value = false
            sseConnecting.value = false

            ElMessage.success(dialogType.value === 'edit' ? '重新登录成功' : '账号添加成功')

            // 登录刚成功时用快速列表，避免立即跑全量服务端校验把视频号误标异常
            fetchAccountsQuick().then(() => {
              ElMessage.success('账号信息已更新')
            })
          }, 1000)
        }, 1000)
      } else {
        ElMessage.error(loginHint.value || '登录失败，请重试')
        setTimeout(() => {
          sseConnecting.value = false
          qrCodeData.value = ''
          loginStatus.value = ''
        }, 1500)
      }
      return
    } else if (data.startsWith('data:image') || data.length > 500) {
      try {
        if (data.startsWith('data:image')) {
          qrCodeData.value = data
        } else {
          qrCodeData.value = `data:image/png;base64,${data}`
        }
      } catch (error) {
        // 处理二维码数据出错
      }
    } else if (data) {
      loginHint.value = data
      // 进度只写面板，避免 Toast 刷屏
    }
  }

  // 监听错误
  eventSource.onerror = () => {
    // 必须 close，否则浏览器会自动重连 /login → 反复开 Chrome
    closeSSEConnection()
    if (sseFinished || loginStatus.value) {
      return
    }
    ElMessage.error(loginHint.value || '登录连接已断开，请重试')
    sseConnecting.value = false
  }
}

// 提交账号表单
const submitAccountForm = () => {
  accountFormRef.value.validate(async (valid) => {
    if (valid) {
      if (dialogType.value === 'add') {
        if (sseConnecting.value) {
          ElMessage.warning('登录流程进行中，请稍候')
          return false
        }
        if (!loginAgentOnline.value) {
          ElMessage.warning('请先连接本机助手（账号管理页点「连接助手」）')
          return false
        }
        if (accountForm.platform === 'TikTok') {
          const okLocal = await ensureTikTokActiveIsLocal()
          if (!okLocal) return false
        }
        connectSSE(accountForm.platform, accountForm.name, accountForm.id || null)
      } else {
        // 编辑账号逻辑
        try {
          // 将平台名称转换为类型数字
          const platformTypeMap = {
            '小红书': 1,
            '视频号': 2,
            '抖音': 3,
            '快手': 4,
            'TikTok': 5
          };
          const type = platformTypeMap[accountForm.platform] || 1;

          const res = await accountApi.updateAccount({
            id: accountForm.id,
            type: type,
            userName: accountForm.name,
            proxy_url: accountForm.platform === 'TikTok' ? (accountForm.proxyUrl || '') : undefined
          })
          if (res.code === 200) {
            // 更新状态管理中的账号
            const updatedAccount = {
              id: accountForm.id,
              name: accountForm.name,
              platform: accountForm.platform,
              status: accountForm.status,
              proxyUrl: accountForm.proxyUrl || ''
            };
            accountStore.updateAccount(accountForm.id, updatedAccount)
            ElMessage.success('更新成功')
            dialogVisible.value = false
            // 刷新账号列表
            fetchAccounts()
          } else {
            ElMessage.error(res.msg || '更新账号失败')
          }
        } catch (error) {
          console.error('更新账号失败:', error)
          ElMessage.error('更新账号失败')
        }
      }
    } else {
      return false
    }
  })
}

// 组件卸载前关闭SSE连接
onBeforeUnmount(() => {
  stopAccountMonitor()
  closeSSEConnection()
})
</script>

<style lang="scss" scoped>
@use '@sau/styles/variables.scss' as *;

.tiktok-proxy-alert {
  margin: 0 0 12px;
}
.proxy-cell {
  color: #606266;
  font-size: 13px;
}

.account-management {
  .account-tabs {
    .account-tabs-nav {
      padding: 0;
    }
  }
  
  .account-list-container {
    .account-search {
      display: flex;
      justify-content: space-between;
      margin-bottom: 20px;
      
      .el-input {
        width: 300px;
      }
      
      .action-buttons {
        display: flex;
        gap: 10px;
        
        .el-icon.is-loading {
          animation: rotate 1s linear infinite;
        }
      }
    }
    
    .account-list {
      margin-bottom: 20px;
    }
    
    .empty-data {
      padding: 40px 0;
    }
  }
  
  // 二维码容器样式
  .clickable-status {
    cursor: pointer;
    transition: all 0.3s;

    &:hover {
      transform: scale(1.05);
      box-shadow: 0 0 8px rgba(0, 0, 0, 0.15);
    }
  }

  .login-agent-panel {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: 0;

    .login-agent-panel-main {
      flex: 1;
      min-width: 0;
    }

    .login-agent-panel-title {
      font-size: 14px;
      font-weight: 600;
      margin-bottom: 4px;
    }

    .login-agent-panel-desc {
      font-size: 13px;
      color: var(--el-text-color-secondary);
    }

    .login-agent-picker {
      margin-top: 8px;
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }

    .login-agent-panel-actions {
      display: flex;
      gap: 8px;
      flex-shrink: 0;
    }
  }

  .douyin-agent-bar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin: 8px 0 12px;
    padding: 10px 12px;
    background: var(--el-fill-color-light);
    border-radius: 6px;
    font-size: 13px;

    .agent-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;

      &.online {
        background: #67c23a;
      }

      &.offline {
        background: #e6a23c;
      }
    }

  }

  .qrcode-container {
    margin-top: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 250px;
    
    .qrcode-wrapper {
      text-align: center;
      
      .qrcode-tip {
        margin-bottom: 15px;
        color: #606266;
      }
      
      .qrcode-image {
        max-width: 200px;
        max-height: 200px;
        border: 1px solid #ebeef5;
        background-color: black;
      }
    }
    
    .loading-wrapper, .success-wrapper, .error-wrapper {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 10px;
      
      .el-icon {
        font-size: 48px;
        
        &.is-loading {
          animation: rotate 1s linear infinite;
        }
      }
      
      span {
        font-size: 16px;
      }
    }
    
    .success-wrapper .el-icon {
      color: #67c23a;
    }
    
    .error-wrapper .el-icon {
      color: #f56c6c;
    }
  }
}
</style>