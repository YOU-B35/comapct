import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAccountStore = defineStore('sauAccount', () => {
  // 存储所有账号信息
  const accounts = ref([])
  
  // 平台类型映射
  const platformTypes = {
    1: '小红书',
    2: '视频号',
    3: '抖音',
    4: '快手',
    5: 'TikTok'
  }
  
  // 设置账号列表
  const setAccounts = (accountsData) => {
    // 转换后端返回的数据格式为前端使用的格式
    // 固定列：id,type,filePath,userName,status,owner_id,profile_dir,profile_bound_at,
    // proxy_url,proxy_updated_at,bound_agent_id,bound_agent_hostname
    accounts.value = accountsData.map(item => {
      return {
        id: item[0],
        type: item[1],
        filePath: item[2],
        name: item[3],
        status: item[4] === -1 ? '验证中' : (item[4] === 1 ? '正常' : '异常'),
        platform: platformTypes[item[1]] || '未知',
        profileDir: item[6] || '',
        proxyUrl: item[8] || '',
        boundAgentId: item[10] || '',
        boundAgentHostname: item[11] || '',
      }
    })
  }
  
  // 添加账号
  const addAccount = (account) => {
    accounts.value.push(account)
  }
  
  // 更新账号
  const updateAccount = (id, updatedAccount) => {
    const index = accounts.value.findIndex(acc => acc.id === id)
    if (index !== -1) {
      accounts.value[index] = { ...accounts.value[index], ...updatedAccount }
    }
  }
  
  // 删除账号
  const deleteAccount = (id) => {
    accounts.value = accounts.value.filter(acc => acc.id !== id)
  }

  const clearAccounts = () => {
    accounts.value = []
  }
  
  // 根据平台获取账号
  const getAccountsByPlatform = (platform) => {
    return accounts.value.filter(acc => acc.platform === platform)
  }
  
  return {
    accounts,
    setAccounts,
    addAccount,
    updateAccount,
    deleteAccount,
    clearAccounts,
    getAccountsByPlatform
  }
})