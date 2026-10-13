<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import {
  createWorkOrder,
  listEquipments,
  listWorkOrders,
  updateWorkOrder,
  type Equipment,
  type WorkOrder,
  type WorkOrderPriority
} from '@/api/equipment'
import { useAuthStore } from '@/stores/auth'
import ManagementSidebar from '@/components/ManagementSidebar.vue'

const auth = useAuthStore()
const router = useRouter()

const equipments = ref<Equipment[]>([])
const workOrders = ref<WorkOrder[]>([])
const workOrderResolutions = reactive<Record<string, string>>({})
const workOrderForm = reactive({
  equipment_id: '',
  title: '',
  description: '',
  priority: 'normal' as WorkOrderPriority
})
const isLoading = ref(true)
const activeRequest = ref<'create' | 'update' | null>(null)
const pageError = ref('')
const successMessage = ref('')

const isStudent = computed(() => auth.user?.role === 'student')
const canManage = computed(() => auth.user?.role === 'teacher' || auth.user?.role === 'admin')
const selectedEquipment = computed(() => equipments.value.find(({ id }) => id === workOrderForm.equipment_id))
const pendingCount = computed(() => workOrders.value.filter(({ status }) => status === 'submitted').length)
const processingCount = computed(() => workOrders.value.filter(({ status }) => status === 'approved' || status === 'in_progress').length)
const finishedCount = computed(() => workOrders.value.filter(({ status }) => status === 'completed' || status === 'rejected' || status === 'cancelled').length)

const priorityLabels: Record<WorkOrderPriority, string> = {
  low: '低',
  normal: '普通',
  high: '高',
  urgent: '紧急'
}
const workOrderStatusLabels: Record<string, string> = {
  submitted: '待审核',
  approved: '已通过',
  rejected: '已拒绝',
  in_progress: '处理中',
  completed: '已完成',
  cancelled: '已取消'
}

const errorDetail = (cause: unknown, fallback: string) => {
  if (axios.isAxiosError<{ detail?: string }>(cause)) {
    return cause.response?.data?.detail || `${fallback}${cause.response?.status ? `（HTTP ${cause.response.status}）` : ''}`
  }
  return cause instanceof Error ? cause.message : fallback
}

const resetMessages = () => {
  pageError.value = ''
  successMessage.value = ''
}

const loadData = async () => {
  isLoading.value = true
  pageError.value = ''
  try {
    const [equipmentData, workOrderData] = await Promise.all([listEquipments(), listWorkOrders()])
    equipments.value = equipmentData
    workOrders.value = workOrderData
    if (!workOrderForm.equipment_id && equipmentData.length) workOrderForm.equipment_id = equipmentData[0].id
  } catch (cause) {
    pageError.value = errorDetail(cause, '无法加载工单数据。')
  } finally {
    isLoading.value = false
  }
}

const submitWorkOrder = async () => {
  if (activeRequest.value) return
  resetMessages()
  activeRequest.value = 'create'
  try {
    const created = await createWorkOrder({
      equipment_id: workOrderForm.equipment_id,
      title: workOrderForm.title.trim(),
      description: workOrderForm.description.trim(),
      priority: workOrderForm.priority
    })
    workOrders.value = [created, ...workOrders.value]
    workOrderForm.title = ''
    workOrderForm.description = ''
    successMessage.value = `维修工单「${created.title}」已提交。`
  } catch (cause) {
    pageError.value = errorDetail(cause, '维修工单提交失败，请检查填写内容。')
  } finally {
    activeRequest.value = null
  }
}

const reviewWorkOrder = async (order: WorkOrder, status: string) => {
  if (activeRequest.value || !canManage.value) return
  resetMessages()
  activeRequest.value = 'update'
  try {
    const resolution = workOrderResolutions[order.id]?.trim()
    const updated = await updateWorkOrder(order.id, {
      status,
      ...(resolution ? { resolution } : {})
    })
    workOrders.value = workOrders.value.map((item) => item.id === updated.id ? updated : item)
    successMessage.value = `工单「${order.title}」已更新为${workOrderStatusLabels[status] || status}。`
    delete workOrderResolutions[order.id]
  } catch (cause) {
    pageError.value = errorDetail(cause, '工单状态更新失败。')
  } finally {
    activeRequest.value = null
  }
}

const formatDate = (value: string) => new Intl.DateTimeFormat('zh-CN', {
  dateStyle: 'medium',
  timeStyle: 'short'
}).format(new Date(value))

const logout = async () => {
  auth.logout()
  await router.replace({ name: 'login' })
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="work-order-shell">
    <ManagementSidebar v-if="canManage" />
    <main class="work-order-main">
      <header class="work-order-header">
        <div>
          <button class="back-link" type="button" @click="router.push({ name: 'dashboard' })">← 返回总览</button>
          <p class="eyebrow">REPAIR WORKFLOW</p>
          <h1>{{ isStudent ? '我的维修工单' : '工单管理' }}</h1>
          <p class="header-copy">{{ isStudent ? '提交设备报修，并查看自己的维修进度。' : '审核报修申请，跟踪维修处理状态。' }}</p>
        </div>
        <div class="header-account">
          <span class="account-avatar" aria-hidden="true">{{ auth.user?.display_name?.slice(0, 1) || '用' }}</span>
          <span class="header-account__copy"><strong>{{ auth.user?.display_name }}</strong><small>{{ auth.user?.role === 'admin' ? '管理员' : isStudent ? '学生' : '教师' }}</small></span>
          <button class="logout-button" type="button" @click="logout">退出</button>
        </div>
      </header>

      <p v-if="pageError" class="feedback feedback--error" role="alert">{{ pageError }}</p>
      <p v-if="successMessage" class="feedback feedback--success" role="status">{{ successMessage }}</p>
      <div v-if="isLoading" class="loading-state" role="status">正在加载工单…</div>

      <template v-else>
        <section class="metric-grid" aria-label="工单统计">
          <article class="metric-card"><span>{{ isStudent ? '我的工单' : '工单总数' }}</span><strong>{{ workOrders.length }}</strong></article>
          <article class="metric-card metric-card--pending"><span>{{ isStudent ? '等待处理' : '待审核' }}</span><strong>{{ pendingCount }}</strong></article>
          <article class="metric-card metric-card--progress"><span>处理中</span><strong>{{ processingCount }}</strong></article>
          <article class="metric-card metric-card--finished"><span>已结束</span><strong>{{ finishedCount }}</strong></article>
        </section>

        <div class="work-order-grid">
          <section class="panel request-panel" aria-labelledby="request-heading">
            <div class="panel-heading">
              <div><p class="eyebrow">NEW REQUEST</p><h2 id="request-heading">{{ isStudent ? '提交维修申请' : '新建维修工单' }}</h2></div>
            </div>
            <form class="stack-form" @submit.prevent="submitWorkOrder">
              <label>关联设备
                <select v-model="workOrderForm.equipment_id" required>
                  <option value="" disabled>选择设备</option>
                  <option v-for="equipment in equipments" :key="equipment.id" :value="equipment.id">{{ equipment.equipment_code }} · {{ equipment.name }}</option>
                </select>
              </label>
              <p v-if="selectedEquipment" class="field-hint">设备当前状态：{{ { available: '可用', in_use: '使用中', maintenance: '维修中', retired: '已报废' }[selectedEquipment.status] }}</p>
              <label>问题标题<input v-model="workOrderForm.title" required maxlength="200" placeholder="如 运行时出现异常振动" /></label>
              <label>问题描述<textarea v-model="workOrderForm.description" required rows="5" maxlength="10000" placeholder="描述故障现象、发生时间和已采取的处理措施" /></label>
              <label>优先级
                <select v-model="workOrderForm.priority">
                  <option v-for="(label, value) in priorityLabels" :key="value" :value="value">{{ label }}</option>
                </select>
              </label>
              <button class="primary-button" type="submit" :disabled="activeRequest !== null || !workOrderForm.equipment_id || !workOrderForm.title.trim() || !workOrderForm.description.trim() || !equipments.length">
                {{ activeRequest === 'create' ? '提交中…' : isStudent ? '提交维修申请' : '创建工单' }}
              </button>
              <p v-if="!equipments.length" class="field-hint">当前可用范围内没有设备，暂时无法提交工单。</p>
            </form>
          </section>

          <section class="panel orders-panel" aria-labelledby="orders-heading">
            <div class="panel-heading">
              <div><p class="eyebrow">WORK ORDER QUEUE</p><h2 id="orders-heading">{{ isStudent ? '我的工单进度' : '工单列表' }}</h2></div>
              <span class="panel-count">{{ workOrders.length }} 条</span>
            </div>
            <div v-if="workOrders.length" class="order-list">
              <article v-for="order in workOrders" :key="order.id" class="order-card">
                <div class="order-card__heading">
                  <div><span class="eyebrow">{{ order.equipment_code }} · {{ order.equipment_name }}</span><h3>{{ order.title }}</h3></div>
                  <span class="order-status" :class="`order-status--${order.status}`">{{ workOrderStatusLabels[order.status] || order.status }}</span>
                </div>
                <p class="order-description">{{ order.description }}</p>
                <div class="order-meta">
                  <span :class="`priority priority--${order.priority}`">{{ priorityLabels[order.priority] }}优先级</span>
                  <span v-if="canManage">提交人：{{ order.requester_name }}</span>
                  <time :datetime="order.created_at">{{ formatDate(order.created_at) }}</time>
                </div>
                <p v-if="order.resolution" class="resolution-note"><strong>处理说明</strong>{{ order.resolution }}</p>
                <div v-if="canManage" class="order-actions">
                  <input v-if="order.status === 'submitted' || order.status === 'in_progress'" v-model="workOrderResolutions[order.id]" placeholder="填写拒绝或完成说明" maxlength="10000" />
                  <button v-if="order.status === 'submitted'" type="button" :disabled="activeRequest !== null" @click="reviewWorkOrder(order, 'approved')">通过</button>
                  <button v-if="order.status === 'submitted'" type="button" class="danger-action" :disabled="activeRequest !== null || !workOrderResolutions[order.id]?.trim()" @click="reviewWorkOrder(order, 'rejected')">拒绝</button>
                  <button v-if="order.status === 'approved'" type="button" :disabled="activeRequest !== null" @click="reviewWorkOrder(order, 'in_progress')">开始处理</button>
                  <button v-if="order.status === 'in_progress'" type="button" :disabled="activeRequest !== null || !workOrderResolutions[order.id]?.trim()" @click="reviewWorkOrder(order, 'completed')">完成</button>
                </div>
              </article>
            </div>
            <div v-else class="empty-state"><strong>还没有维修工单</strong><span>{{ isStudent ? '提交报修后，处理状态会显示在这里。' : '收到新的设备报修后，会显示在这里。' }}</span></div>
          </section>
        </div>
      </template>
    </main>
  </div>
</template>

<style scoped>
.work-order-shell { display: flex; min-height: 100dvh; background: var(--c-bg-0); }
.work-order-main { flex: 1; min-width: 0; width: min(1320px, calc(100% - 48px)); max-width: 1320px; margin: 0 auto; padding: 32px 24px 56px; }
.work-order-header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; gap: 24px; padding-bottom: 24px; border-bottom: 1px solid var(--c-line-1); }
.back-link { margin-bottom: 24px; color: var(--c-accent); font-size: var(--fs-sm); }.back-link:hover { text-decoration: underline; }
.eyebrow { color: var(--c-accent); font-size: 10px; font-weight: var(--fw-semibold); letter-spacing: .15em; }
h1 { margin-top: 10px; font-size: 30px; letter-spacing: -.035em; }.header-copy { margin-top: 8px; color: var(--c-fg-1); }
.header-account { display: flex; align-items: center; gap: 9px; flex: 0 0 auto; min-width: max-content; margin-left: auto; padding-top: 9px; color: var(--c-fg-0); }
.account-avatar { display: grid; width: 31px; height: 31px; flex: 0 0 31px; place-items: center; border-radius: 50%; color: var(--c-accent); background: var(--c-accent-soft); font-size: 12px; font-weight: 600; }
.header-account__copy { display: grid; gap: 1px; }.header-account strong { font-size: 12px; }.header-account small { color: var(--c-fg-2); font-size: 10px; }
.logout-button { padding: 5px 7px; color: var(--c-fg-1); border-radius: var(--r-sm); font-size: 11px; }.logout-button:hover { color: var(--c-bad); background: var(--c-danger-soft); }
.feedback { padding: 10px 12px; margin-top: 18px; border-left: 2px solid; font-size: var(--fs-sm); }.feedback--error { color: var(--c-bad); background: var(--c-danger-soft); border-color: var(--c-bad); }.feedback--success { color: var(--c-ok); background: var(--c-success-soft); border-color: var(--c-ok); }
.loading-state { padding: 56px 0; color: var(--c-fg-1); text-align: center; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 24px; }.metric-card { display: grid; gap: 9px; padding: 16px 18px; background: var(--c-bg-1); border: 1px solid var(--c-line-1); border-radius: var(--r-md); }.metric-card span { color: var(--c-fg-2); font-size: var(--fs-xs); }.metric-card strong { font-size: 25px; font-variant-numeric: tabular-nums; }.metric-card--pending strong { color: var(--c-warn); }.metric-card--progress strong { color: var(--c-accent); }.metric-card--finished strong { color: var(--c-ok); }
.work-order-grid { display: grid; grid-template-columns: minmax(280px, .72fr) minmax(0, 1.6fr); align-items: start; gap: 18px; margin-top: 18px; }.panel { min-width: 0; padding: 22px; background: var(--c-bg-1); border: 1px solid var(--c-line-1); border-radius: var(--r-md); }.panel-heading { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 20px; }.panel-heading h2 { margin-top: 7px; font-size: 17px; }.panel-count { color: var(--c-fg-2); font: 11px var(--ff-mono); white-space: nowrap; }
.stack-form { display: grid; gap: 14px; }label { display: grid; gap: 6px; color: var(--c-fg-1); font-size: var(--fs-sm); font-weight: var(--fw-medium); }
input, select, textarea { width: 100%; padding: 9px 10px; color: var(--c-fg-0); background: var(--c-bg-1); border: 1px solid var(--c-line-2); border-radius: var(--r-sm); outline: 0; font-size: var(--fs-sm); }textarea { resize: vertical; line-height: 1.5; }input:focus, select:focus, textarea:focus { border-color: var(--c-accent); box-shadow: 0 0 0 3px var(--c-accent-soft); }
.field-hint { margin-top: -8px; color: var(--c-fg-2); font-size: var(--fs-xs); line-height: 1.5; }.primary-button { min-height: 38px; padding: 0 14px; color: var(--c-accent-fg); background: var(--c-accent); border-radius: var(--r-sm); font-size: var(--fs-sm); font-weight: var(--fw-semibold); }.primary-button:hover:not(:disabled) { background: var(--c-accent-3); }.primary-button:disabled { cursor: not-allowed; opacity: .5; }
.order-list { display: grid; gap: 12px; }.order-card { padding: 16px; border: 1px solid var(--c-line-1); border-radius: var(--r-sm); }.order-card__heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; }.order-card__heading h3 { margin-top: 6px; font-size: 15px; }.order-status { flex: 0 0 auto; padding: 4px 8px; color: var(--c-fg-1); background: var(--c-neutral-soft); border-radius: var(--r-xs); font-size: var(--fs-xs); }.order-status--submitted { color: var(--c-warn); background: var(--c-warning-soft); }.order-status--approved, .order-status--in_progress { color: var(--c-accent); background: var(--c-accent-soft); }.order-status--completed { color: var(--c-ok); background: var(--c-success-soft); }.order-status--rejected, .order-status--cancelled { color: var(--c-bad); background: var(--c-danger-soft); }
.order-description { margin-top: 12px; color: var(--c-fg-1); font-size: var(--fs-sm); line-height: 1.6; white-space: pre-wrap; }.order-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; margin-top: 12px; color: var(--c-fg-2); font-size: var(--fs-xs); }.priority { padding: 3px 6px; border-radius: var(--r-xs); }.priority--urgent, .priority--high { color: var(--c-bad); background: var(--c-danger-soft); }.priority--normal { color: var(--c-accent); background: var(--c-accent-soft); }.priority--low { background: var(--c-neutral-soft); }.resolution-note { display: grid; gap: 4px; margin-top: 12px; padding: 10px 12px; color: var(--c-fg-1); background: var(--c-bg-0); border-radius: var(--r-xs); font-size: var(--fs-xs); line-height: 1.5; }.resolution-note strong { color: var(--c-fg-0); }
.order-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 14px; }.order-actions input { max-width: 260px; }.order-actions button { min-height: 30px; padding: 0 9px; color: var(--c-accent); background: var(--c-accent-soft); border: 1px solid var(--c-accent-line); border-radius: var(--r-xs); font-size: var(--fs-xs); }.order-actions button:disabled { cursor: not-allowed; opacity: .5; }.order-actions .danger-action { color: var(--c-bad); background: var(--c-danger-soft); border-color: rgba(185, 28, 28, .2); }
.empty-state { display: grid; gap: 6px; padding: 36px 8px; color: var(--c-fg-2); font-size: var(--fs-sm); text-align: center; }.empty-state strong { color: var(--c-fg-1); }
@media (max-width: 1000px) { .work-order-grid { grid-template-columns: 1fr; }.request-panel { order: 1; }.orders-panel { order: 2; } }
@media (max-width: 760px) { .work-order-shell { display: block; }.work-order-main { width: min(100% - 32px, 680px); padding: 24px 16px 40px; } }
@media (max-width: 560px) { .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.work-order-header { display: block; }.header-account { margin-top: 18px; }.panel { padding: 17px; }.order-card__heading { display: grid; } }
</style>
