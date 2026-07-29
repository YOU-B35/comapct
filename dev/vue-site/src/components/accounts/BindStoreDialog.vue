<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { bindPlatformStore } from '@/api/platformAccounts'
import { useAuthStore } from '@/stores/auth'
import { formatCaughtError } from '@/utils/appErrorCode'
import { DTC_STORE_TYPE_OPTIONS } from '@/constants/platforms'

const props = defineProps({
  visible: { type: Boolean, default: false },
  defaultPlatform: { type: String, default: 'temu' },
  editStore: { type: Object, default: null },
})

const emit = defineEmits(['update:visible', 'success'])

const auth = useAuthStore()
const formRef = ref(null)
const submitting = ref(false)

const platformGroups = [
  {
    label: '跨境平台',
    options: [
      { value: 'temu', label: 'Temu' },
      { value: 'aliexpress', label: 'AliExpress' },
      { value: 'amazon', label: 'Amazon' },
      { value: 'walmart', label: 'Walmart' },
    ],
  },
  {
    label: '国内电商',
    options: [
      { value: 'pdd', label: '拼多多' },
      { value: 'douyin', label: '抖音' },
      { value: 'channels', label: '视频号' },
    ],
  },
  {
    label: '供应链',
    options: [{ value: '1688', label: '1688' }],
  },
  {
    label: '独立站',
    options: DTC_STORE_TYPE_OPTIONS,
  },
]

const form = reactive({
  platform: 'temu',
  storeName: '',
  account: '',
  password: '',
})

const isEdit = computed(() => Boolean(props.editStore?.id))
const dialogTitle = computed(() => (isEdit.value ? '编辑店铺绑定' : '绑定店铺'))

const rules = computed(() => ({
  platform: [{ required: true, message: '请选择平台', trigger: 'change' }],
  storeName: [{ required: true, message: '请填写店铺名称', trigger: 'blur' }],
  account: [{ required: true, message: '请填写登录账号', trigger: 'blur' }],
  password: isEdit.value
    ? []
    : [{ required: true, message: '请填写登录密码', trigger: 'blur' }],
}))

const dialogVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

function resetForm() {
  if (props.editStore?.id) {
    form.platform = props.editStore.platform || 'temu'
    form.storeName = props.editStore.storeName || ''
    form.account = props.editStore.account || ''
    form.password = ''
  } else {
    form.platform = props.defaultPlatform || 'temu'
    form.storeName = ''
    form.account = ''
    form.password = ''
  }
  formRef.value?.clearValidate?.()
}

async function submit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    const payload = {
      companyName: auth.company.name,
      platform: form.platform,
      storeName: form.storeName.trim(),
      account: form.account.trim(),
      password: form.password,
      externalShopId: '',
    }
    if (isEdit.value) {
      payload.id = props.editStore.id
    }

    const res = await bindPlatformStore(payload)
    ElMessage.success(res.message || (isEdit.value ? '保存成功' : '绑定成功'))
    emit('success')
    dialogVisible.value = false
  } catch (err) {
    ElMessage.error(formatCaughtError(err, isEdit.value ? '保存失败' : '绑定失败'))
  } finally {
    submitting.value = false
  }
}

watch(
  () => [props.visible, props.editStore],
  ([open]) => {
    if (open) resetForm()
  },
)
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    :title="dialogTitle"
    width="480px"
    destroy-on-close
    @closed="resetForm"
  >
    <el-alert
      v-if="form.platform === 'temu' && !isEdit"
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
      title="Temu 店铺说明"
    >
      <template #default>
        填写店铺名称与登录账号即可。绑定后，运维机定时同步会自动关联店铺并更新销量。
      </template>
    </el-alert>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px" class="bind-form">
      <el-form-item label="平台" prop="platform">
        <el-select
          v-model="form.platform"
          placeholder="选择平台"
          style="width: 100%"
          :disabled="isEdit"
        >
          <el-option-group v-for="group in platformGroups" :key="group.label" :label="group.label">
            <el-option
              v-for="item in group.options"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-option-group>
        </el-select>
      </el-form-item>
      <el-form-item label="店铺名称" prop="storeName">
        <el-input v-model="form.storeName" placeholder="便于识别的名称，如 Temu 泰州店" />
      </el-form-item>
      <el-form-item label="登录账号" prop="account">
        <el-input v-model="form.account" placeholder="平台登录账号 / 手机号" autocomplete="off" />
      </el-form-item>
      <el-form-item label="登录密码" prop="password">
        <el-input
          v-model="form.password"
          type="password"
          show-password
          :placeholder="isEdit ? '不修改请留空' : '平台登录密码'"
          autocomplete="new-password"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">
        {{ isEdit ? '保存' : '确认绑定' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.bind-form {
  padding-top: 4px;
}
</style>
