<script setup lang="ts">
import axios from 'axios'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listEquipments, listWorkOrders, type Equipment, type EquipmentStatus, type WorkOrder } from '@/api/equipment'
import { listColleges, listLaboratories, type College, type Laboratory } from '@/api/organization'
import { useAuthStore } from '@/stores/auth'
import ManagementSidebar from '@/components/ManagementSidebar.vue'

const auth = useAuthStore()
const router = useRouter()
const colleges = ref<College[]>([])
const laboratories = ref<Laboratory[]>([])
const equipments = ref<Equipment[]>([])
const workOrders = ref<WorkOrder[]>([])
const isLoading = ref(true)
const pageError = ref('')

const isAdmin = computed(() => auth.user?.role === 'admin')
const canManage = computed(() => auth.user?.role === 'admin' || auth.user?.role === 'teacher')
const roleLabel = computed(() => ({ admin: '管理员', teacher: '教师', student: '学生' }[auth.user?.role || 'student']))
const scopeLabel = computed(() => {
  if (isAdmin.value) return '全校实验室'
  if (auth.user?.role === 'teacher') return '我负责的实验室'
  return colleges.value[0]?.name || '本学院实验室'
})
const greeting = computed(() => {
  const hour = new Date().getHours()
  return hour < 11 ? '早上好' : hour < 18 ? '下午好' : '晚上好'
})

const statusLabels: Record<EquipmentStatus, string> = {
  available: '可用',
  in_use: '使用中',
  maintenance: '维护中',
  retired: '已报废'
}
const statusColors: Record<EquipmentStatus, string> = {
  available: 'available',
  in_use: 'in-use',
  maintenance: 'maintenance',
  retired: 'retired'
}
const statusCounts = computed<Record<EquipmentStatus, number>>(() => ({
  available: equipments.value.filter(({ status }) => status === 'available').length,
  in_use: equipments.value.filter(({ status }) => status === 'in_use').length,
  maintenance: equipments.value.filter(({ status }) => status === 'maintenance').length,
  retired: equipments.value.filter(({ status }) => status === 'retired').length
}))
const statusTotal = computed(() => equipments.value.length)
const openWorkOrders = computed(() => workOrders.value.filter(({ status }) =>
  status === 'submitted' || status === 'approved' || status === 'in_progress'
))
const reminderPriorityRank: Record<WorkOrder['priority'], number> = { urgent: 0, high: 1, normal: 2, low: 3 }
const workOrderReminders = computed(() => [...openWorkOrders.value]
  .sort((left, right) => reminderPriorityRank[left.priority] - reminderPriorityRank[right.priority]
    || new Date(right.created_at).getTime() - new Date(left.created_at).getTime())
  .slice(0, 3))
const recentWorkOrders = computed(() => [...workOrders.value]
  .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime())
  .slice(0, 5))
const laboratoriesWithEquipment = computed(() => laboratories.value.slice(0, 5).map((laboratory) => ({
  ...laboratory,
  equipmentCount: equipments.value.filter(({ laboratory_id }) => laboratory_id === laboratory.id).length
})))
const workOrderStatusLabels: Record<string, string> = {
  submitted: '待审核',
  approved: '已通过',
  in_progress: '处理中',
  completed: '已完成',
  rejected: '已拒绝',
  cancelled: '已取消'
}
const priorityLabels: Record<string, string> = { urgent: '紧急', high: '高', normal: '普通', low: '低' }

const loadOverview = async () => {
  isLoading.value = true
  pageError.value = ''
  try {
    const [collegeData, laboratoryData, equipmentData, workOrderData] = await Promise.all([
      listColleges(),
      listLaboratories(),
      listEquipments(),
      listWorkOrders()
    ])
    colleges.value = collegeData
    laboratories.value = laboratoryData
    equipments.value = equipmentData
    workOrders.value = workOrderData
  } catch (cause) {
    pageError.value = axios.isAxiosError<{ detail?: string }>(cause)
      ? cause.response?.data?.detail || `无法加载实验室概况${cause.response?.status ? `（HTTP ${cause.response.status}）` : ''}。`
      : cause instanceof Error ? cause.message : '无法加载实验室概况。'
  } finally {
    isLoading.value = false
  }
}

const logout = async () => {
  auth.logout()
  await router.replace({ name: 'login' })
}

const formatDate = (value: string) => {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '时间未知'
    : new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric' }).format(date)
}

onMounted(() => {
  void loadOverview()
})
</script>

<template>
  <div class="overview-shell">
    <ManagementSidebar v-if="canManage" />
    <main class="overview-main">
      <div class="overview-content">
        <header class="overview-header">
          <div class="overview-brand">
            <span class="brand-mark" aria-hidden="true"><span /><span /><span /></span>
            <span>LAB<span class="brand-light">DEVICE</span></span>
          </div>
          <div class="overview-header__actions">
            <RouterLink class="assistant-link" :to="{ name: 'assistant' }">打开设备助手 <span aria-hidden="true">↗</span></RouterLink>
            <div class="account-menu" :title="auth.user?.username">
              <span class="account-avatar" aria-hidden="true">{{ auth.user?.display_name?.slice(0, 1) || '用' }}</span>
              <span class="account-copy"><strong>{{ auth.user?.display_name }}</strong><small>{{ roleLabel }}</small></span>
              <button class="logout-button" type="button" @click="logout">退出</button>
            </div>
          </div>
        </header>

        <section v-if="!isLoading && !pageError && canManage && openWorkOrders.length" class="overview-panel work-order-reminder" aria-labelledby="work-order-reminder-title">
          <div class="reminder-heading">
            <div class="reminder-heading__title">
              <span class="reminder-icon" aria-hidden="true">!</span>
              <div><p class="eyebrow">WORK ORDER ALERTS</p><h2 id="work-order-reminder-title">工单处理提醒 <span class="reminder-count">{{ openWorkOrders.length }}</span></h2></div>
            </div>
            <RouterLink class="panel-link" :to="{ name: 'management-work-orders' }">前往处理 <span aria-hidden="true">→</span></RouterLink>
          </div>
          <div class="reminder-list">
            <article v-for="order in workOrderReminders" :key="order.id" class="reminder-row">
              <div class="reminder-row__main">
                <strong>{{ order.title }}</strong>
                <small>{{ order.equipment_code }} · {{ order.equipment_name }} · {{ order.requester_name }}</small>
              </div>
              <div class="reminder-row__meta">
                <span class="priority-tag" :class="`priority-tag--${order.priority}`">{{ priorityLabels[order.priority] || order.priority }}</span>
                <span class="order-status" :class="`order-status--${order.status}`">{{ workOrderStatusLabels[order.status] || order.status }}</span>
                <time :datetime="order.created_at">{{ formatDate(order.created_at) }}</time>
              </div>
            </article>
          </div>
          <p v-if="openWorkOrders.length > workOrderReminders.length" class="reminder-more">另有 {{ openWorkOrders.length - workOrderReminders.length }} 条未结工单</p>
        </section>

        <section class="welcome-panel" aria-labelledby="overview-title">
          <div class="welcome-copy">
            <p class="eyebrow">LABORATORY EQUIPMENT</p>
            <h1 id="overview-title">{{ greeting }}，{{ auth.user?.display_name || '欢迎回来' }}</h1>
            <div v-if="canManage" class="welcome-actions">
              <RouterLink class="primary-action" :to="{ name: 'management-equipment' }">进入设备管理 <span aria-hidden="true">→</span></RouterLink>
            </div>
          </div>
        </section>

        <div v-if="pageError" class="overview-error" role="alert">
          <span>{{ pageError }}</span>
          <button type="button" @click="loadOverview">重试</button>
        </div>

        <section class="metric-grid" aria-label="关键数据">
          <article class="metric-card metric-card--colleges">
            <span class="metric-label">{{ isAdmin ? '学院' : '所属学院' }}</span>
            <strong>{{ isLoading || pageError ? '—' : isAdmin ? colleges.length : colleges.length ? 1 : 0 }}</strong>
          </article>
          <article class="metric-card metric-card--labs">
            <span class="metric-label">{{ auth.user?.role === 'teacher' ? '负责实验室' : '实验室' }}</span>
            <strong>{{ isLoading || pageError ? '—' : laboratories.length }}</strong>
          </article>
          <article class="metric-card metric-card--equipment">
            <span class="metric-label">设备总数</span>
            <strong>{{ isLoading || pageError ? '—' : equipments.length }}</strong>
          </article>
          <article class="metric-card metric-card--orders">
            <span class="metric-label">未结工单</span>
            <strong>{{ isLoading || pageError ? '—' : openWorkOrders.length }}</strong>
          </article>
        </section>

        <div v-if="isLoading" class="overview-loading" role="status">正在汇总实验室数据…</div>

        <template v-else-if="!pageError">
          <div class="overview-grid">
            <section class="overview-panel laboratory-panel" aria-labelledby="laboratories-title">
              <div class="panel-heading">
                <div><p class="eyebrow">LABORATORY DIRECTORY</p><h2 id="laboratories-title">实验室</h2></div>
                <RouterLink v-if="isAdmin" class="panel-link" :to="{ name: 'management-laboratories' }">管理实验室 <span aria-hidden="true">→</span></RouterLink>
                <RouterLink v-else-if="canManage" class="panel-link" :to="{ name: 'management-equipment' }">查看设备 <span aria-hidden="true">→</span></RouterLink>
                <span v-else class="panel-count">{{ laboratories.length }} 间</span>
              </div>
              <div v-if="laboratoriesWithEquipment.length" class="laboratory-list">
                <article v-for="laboratory in laboratoriesWithEquipment" :key="laboratory.id" class="laboratory-row">
                  <span class="lab-symbol" aria-hidden="true">⌂</span>
                  <div class="laboratory-row__copy">
                    <strong>{{ laboratory.laboratory_number }}</strong>
                    <small>{{ colleges.find(({ id }) => id === laboratory.college_id)?.name || scopeLabel }}<template v-if="isAdmin && laboratory.manager_name"> · {{ laboratory.manager_name }}</template></small>
                  </div>
                  <span class="laboratory-equipment-count">{{ laboratory.equipmentCount }} 台设备</span>
                </article>
              </div>
              <div v-else class="empty-state">
                <strong>还没有实验室数据</strong>
                <span>{{ isAdmin ? '可以从实验室管理中添加学院和实验室。' : '当前账号可见范围内暂未分配实验室。' }}</span>
                <RouterLink v-if="isAdmin" :to="{ name: 'management-laboratories' }">前往实验室管理 <span aria-hidden="true">→</span></RouterLink>
              </div>
              <p v-if="laboratories.length > laboratoriesWithEquipment.length" class="panel-footnote">显示 {{ laboratoriesWithEquipment.length }} 间，共 {{ laboratories.length }} 间</p>
            </section>

            <section class="overview-panel equipment-panel" aria-labelledby="equipment-title">
              <div class="panel-heading">
                <div><p class="eyebrow">EQUIPMENT STATUS</p><h2 id="equipment-title">设备运行状态</h2></div>
                <span class="status-total">{{ equipments.length }} <small>台设备</small></span>
              </div>
              <div v-if="statusTotal" class="status-distribution" aria-label="设备状态分布">
                <span v-for="status in (['available', 'in_use', 'maintenance', 'retired'] as EquipmentStatus[])" :key="status" :class="`status-segment status-segment--${statusColors[status]}`" :style="{ flexGrow: statusCounts[status] || 0 }" :title="`${statusLabels[status]} ${statusCounts[status]} 台`" />
              </div>
              <div v-if="statusTotal" class="status-list">
                <div v-for="status in (['available', 'in_use', 'maintenance', 'retired'] as EquipmentStatus[])" :key="status" class="status-row">
                  <span class="status-key"><i :class="`status-dot status-dot--${statusColors[status]}`" />{{ statusLabels[status] }}</span>
                  <strong>{{ statusCounts[status] }}<small> 台</small></strong>
                </div>
              </div>
              <div v-else class="empty-state empty-state--compact">
                <strong>暂无设备档案</strong>
              </div>
              <RouterLink v-if="canManage" class="panel-bottom-link" :to="{ name: 'management-equipment' }">查看设备档案 <span aria-hidden="true">→</span></RouterLink>
            </section>
          </div>

          <section class="overview-panel orders-panel" aria-labelledby="orders-title">
            <div class="panel-heading">
              <div><p class="eyebrow">MAINTENANCE LOG</p><h2 id="orders-title">近期维修工单</h2></div>
              <RouterLink class="panel-link" :to="{ name: 'management-work-orders' }">{{ canManage ? '前往工单管理' : '提交维修申请' }} <span aria-hidden="true">→</span></RouterLink>
            </div>
            <div v-if="recentWorkOrders.length" class="order-list">
              <article v-for="order in recentWorkOrders" :key="order.id" class="order-row">
                <div class="order-row__main">
                  <strong>{{ order.title }}</strong>
                  <span>{{ order.equipment_code }} · {{ order.equipment_name }}<template v-if="canManage"> · {{ order.requester_name }}</template></span>
                </div>
                <span class="priority-tag" :class="`priority-tag--${order.priority}`">{{ priorityLabels[order.priority] || order.priority }}</span>
                <span class="order-status" :class="`order-status--${order.status}`">{{ workOrderStatusLabels[order.status] || order.status }}</span>
                <time :datetime="order.created_at">{{ formatDate(order.created_at) }}</time>
              </article>
            </div>
            <div v-else class="empty-state empty-state--compact">
              <strong>暂无维修工单</strong>
              <span>设备报修后，处理进度会显示在这里。</span>
              <RouterLink :to="{ name: 'management-work-orders' }">提交维修申请 <span aria-hidden="true">→</span></RouterLink>
            </div>
          </section>
        </template>

        <footer class="overview-footer">
          <span>数据按当前账号权限显示</span>
          <span v-if="!isLoading && !pageError">{{ scopeLabel }} · {{ statusTotal }} 台设备</span>
        </footer>
      </div>
    </main>
  </div>
</template>

<style scoped>
.overview-shell { display: flex; min-height: 100dvh; background: var(--c-bg-0); }
.overview-main { flex: 1; min-width: 0; padding: 0 40px 36px; }
.overview-content { width: min(100%, 1260px); margin: 0 auto; }
.overview-header { display: flex; align-items: center; justify-content: space-between; gap: 24px; min-height: 76px; border-bottom: 1px solid var(--c-line-1); }
.overview-brand { display: inline-flex; align-items: center; gap: 9px; color: var(--c-fg-0); font-size: 12px; font-weight: var(--fw-semibold); letter-spacing: .09em; }
.brand-light { color: var(--c-accent); }
.brand-mark { display: inline-flex; align-items: center; justify-content: center; gap: 2px; width: 24px; height: 24px; border: 1px solid var(--c-accent-line); border-radius: var(--r-sm); }
.brand-mark span { width: 2px; border-radius: 2px; background: var(--c-accent); }.brand-mark span:nth-child(1) { height: 7px; }.brand-mark span:nth-child(2) { height: 12px; }.brand-mark span:nth-child(3) { height: 9px; }
.overview-header__actions { display: flex; align-items: center; gap: 24px; }
.assistant-link, .panel-link, .panel-bottom-link { color: var(--c-accent); font-size: var(--fs-sm); font-weight: var(--fw-medium); }
.assistant-link span, .panel-link span, .panel-bottom-link span { margin-left: 4px; }
.assistant-link:hover, .panel-link:hover, .panel-bottom-link:hover { color: var(--c-accent-3); }
.account-menu { display: flex; align-items: center; gap: 9px; flex: 0 0 auto; min-width: max-content; padding-left: 16px; border-left: 1px solid var(--c-line-1); }
.account-avatar { display: grid; width: 31px; height: 31px; flex: 0 0 31px; place-items: center; border-radius: 50%; color: var(--c-accent); background: var(--c-accent-soft); font-size: 12px; font-weight: var(--fw-semibold); }
.account-copy { display: grid; gap: 1px; color: var(--c-fg-0); line-height: 1.3; }.account-copy strong { max-width: 110px; overflow: hidden; font-size: 11px; font-weight: var(--fw-semibold); text-overflow: ellipsis; white-space: nowrap; }.account-copy small { color: var(--c-fg-2); font-size: 10px; }
.logout-button { min-width: 38px; flex: 0 0 auto; padding: 5px 7px; color: var(--c-fg-1); border-radius: var(--r-sm); font-size: 11px; white-space: nowrap; }.logout-button:hover { color: var(--c-bad); background: var(--c-danger-soft); }
.welcome-panel { position: relative; display: flex; align-items: flex-end; justify-content: space-between; gap: 32px; min-height: 228px; padding: 34px 38px; margin-top: 28px; overflow: hidden; background: var(--c-bg-1); border: 1px solid var(--c-line-1); border-radius: var(--r-xl); animation: overview-card-enter 560ms var(--ease-out) 40ms both; }
.welcome-panel::after { position: absolute; right: 11%; bottom: -160px; width: 340px; height: 340px; border: 1px solid var(--c-accent-line); border-radius: 50%; content: ''; pointer-events: none; }
.welcome-panel::before { position: absolute; right: 17%; bottom: -100px; width: 220px; height: 220px; border: 1px solid var(--c-accent-line); border-radius: 50%; content: ''; opacity: .55; pointer-events: none; }
.welcome-copy { position: relative; z-index: 1; max-width: 680px; }
.eyebrow { color: var(--c-accent); font-size: 10px; font-weight: var(--fw-semibold); letter-spacing: .15em; }
.welcome-copy h1 { margin-top: 12px; font-size: clamp(25px, 3vw, 34px); letter-spacing: -.04em; }
.welcome-actions { display: flex; align-items: center; margin-top: 24px; }
.primary-action { display: inline-flex; align-items: center; gap: 18px; min-height: 38px; padding: 0 13px; color: var(--c-accent-fg); background: var(--c-accent); border-radius: var(--r-sm); font-size: var(--fs-sm); font-weight: var(--fw-semibold); transition: background var(--dur-fast) var(--ease-out), transform var(--dur-fast) var(--ease-out); }
.primary-action:hover { background: var(--c-accent-3); transform: translateY(-1px); }
.overview-error { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px 15px; margin-top: 20px; color: var(--c-bad); background: var(--c-danger-soft); border-left: 2px solid var(--c-bad); font-size: var(--fs-sm); }
.overview-error button { flex: 0 0 auto; color: inherit; font-weight: var(--fw-semibold); text-decoration: underline; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 18px; }
.metric-card { display: grid; gap: 7px; min-height: 126px; padding: 18px 20px; background: var(--c-bg-1); border: 1px solid var(--c-line-1); border-radius: var(--r-xl); animation: overview-card-enter 520ms var(--ease-out) both; }
.metric-card:nth-child(1) { animation-delay: 120ms; }.metric-card:nth-child(2) { animation-delay: 190ms; }.metric-card:nth-child(3) { animation-delay: 260ms; }.metric-card:nth-child(4) { animation-delay: 330ms; }
.metric-label { color: var(--c-fg-1); font-size: var(--fs-sm); }.metric-card strong { color: var(--c-fg-0); font-size: 30px; font-weight: var(--fw-medium); letter-spacing: -.04em; line-height: 1; }
.metric-card--orders strong { color: var(--c-accent); }
.overview-grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(290px, .8fr); gap: 16px; margin-top: 18px; }
.overview-panel { min-width: 0; padding: 22px 24px; background: var(--c-bg-1); border: 1px solid var(--c-line-1); border-radius: var(--r-xl); animation: overview-card-enter 520ms var(--ease-out) both; }
.overview-grid .overview-panel:nth-child(1) { animation-delay: 420ms; }.overview-grid .overview-panel:nth-child(2) { animation-delay: 490ms; }.orders-panel { animation-delay: 560ms; }
.work-order-reminder { margin-top: 16px; border-left: 3px solid var(--c-warn); }
.reminder-heading, .reminder-heading__title, .reminder-row, .reminder-row__meta { display: flex; align-items: center; }
.reminder-heading { justify-content: space-between; gap: 18px; }
.reminder-heading__title { gap: 11px; min-width: 0; }
.reminder-icon { display: grid; width: 32px; height: 32px; flex: 0 0 32px; place-items: center; color: var(--c-warn); background: var(--c-warning-soft); border-radius: 50%; font-size: 16px; font-weight: var(--fw-semibold); }
.reminder-heading h2 { display: flex; align-items: center; gap: 8px; margin-top: 5px; font-size: 16px; }
.reminder-count { display: inline-grid; min-width: 22px; height: 22px; place-items: center; padding: 0 6px; color: var(--c-warn); background: var(--c-warning-soft); border-radius: var(--r-pill); font-size: var(--fs-xs); font-weight: var(--fw-semibold); }
.reminder-list { display: grid; margin-top: 12px; }
.reminder-row { justify-content: space-between; gap: 18px; min-width: 0; padding: 12px 0; border-top: 1px solid var(--c-line-1); }
.reminder-row__main { display: grid; gap: 4px; min-width: 0; }
.reminder-row__main strong { overflow: hidden; color: var(--c-fg-0); font-size: var(--fs-sm); font-weight: var(--fw-semibold); text-overflow: ellipsis; white-space: nowrap; }
.reminder-row__main small { overflow: hidden; color: var(--c-fg-2); font-size: var(--fs-xs); text-overflow: ellipsis; white-space: nowrap; }
.reminder-row__meta { flex: 0 0 auto; gap: 8px; }
.reminder-row__meta time { color: var(--c-fg-2); font-size: var(--fs-xs); white-space: nowrap; }
.reminder-more { padding-top: 10px; color: var(--c-fg-2); border-top: 1px solid var(--c-line-1); font-size: var(--fs-xs); }
.panel-heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 18px; }.panel-heading h2 { margin-top: 6px; font-size: 17px; letter-spacing: -.02em; }.panel-count { color: var(--c-fg-2); font: 11px var(--ff-mono); }.panel-link { flex: 0 0 auto; }
.laboratory-list { display: grid; }.laboratory-row { display: flex; align-items: center; gap: 12px; min-height: 64px; border-top: 1px solid var(--c-line-1); }.lab-symbol { display: grid; width: 34px; height: 34px; flex: 0 0 34px; place-items: center; color: var(--c-accent); background: var(--c-accent-soft); border-radius: var(--r-sm); font-size: 17px; }.laboratory-row__copy { display: grid; gap: 3px; min-width: 0; }.laboratory-row__copy strong { overflow: hidden; color: var(--c-fg-0); font-size: var(--fs-sm); font-weight: var(--fw-semibold); text-overflow: ellipsis; white-space: nowrap; }.laboratory-row__copy small { overflow: hidden; color: var(--c-fg-2); font-size: var(--fs-xs); text-overflow: ellipsis; white-space: nowrap; }.laboratory-equipment-count { margin-left: auto; color: var(--c-fg-1); font-size: var(--fs-xs); white-space: nowrap; }.panel-footnote { margin-top: 12px; color: var(--c-fg-2); font-size: var(--fs-xs); }
.equipment-panel { display: flex; flex-direction: column; }.status-total { color: var(--c-fg-0); font-size: 16px; font-weight: var(--fw-semibold); white-space: nowrap; }.status-total small, .status-row strong small { color: var(--c-fg-2); font-size: var(--fs-xs); font-weight: var(--fw-regular); }.status-distribution { display: flex; gap: 3px; height: 9px; margin: 6px 0 18px; overflow: hidden; border-radius: var(--r-pill); background: var(--c-bg-2); }.status-segment { min-width: 0; border-radius: var(--r-pill); }.status-segment--available, .status-dot--available { background: var(--c-ok); }.status-segment--in-use, .status-dot--in-use { background: var(--c-accent); }.status-segment--maintenance, .status-dot--maintenance { background: var(--c-warn); }.status-segment--retired, .status-dot--retired { background: var(--c-fg-3); }.status-list { display: grid; gap: 12px; }.status-row { display: flex; align-items: center; justify-content: space-between; color: var(--c-fg-1); font-size: var(--fs-sm); }.status-key { display: inline-flex; align-items: center; gap: 8px; }.status-dot { width: 7px; height: 7px; border-radius: 50%; }.status-row strong { color: var(--c-fg-0); font-size: var(--fs-sm); font-weight: var(--fw-semibold); }.panel-bottom-link { margin-top: auto; padding-top: 20px; }
.orders-panel { margin-top: 16px; }.order-list { display: grid; }.order-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto 76px; align-items: center; gap: 16px; min-height: 62px; border-top: 1px solid var(--c-line-1); }.order-row__main { display: grid; gap: 4px; min-width: 0; }.order-row__main strong { overflow: hidden; color: var(--c-fg-0); font-size: var(--fs-sm); font-weight: var(--fw-medium); text-overflow: ellipsis; white-space: nowrap; }.order-row__main span, .order-row time { overflow: hidden; color: var(--c-fg-2); font-size: var(--fs-xs); text-overflow: ellipsis; white-space: nowrap; }.order-row time { text-align: right; }.priority-tag, .order-status { display: inline-flex; justify-content: center; min-width: 42px; padding: 4px 7px; border-radius: var(--r-xs); font-size: 10px; white-space: nowrap; }.priority-tag--urgent, .priority-tag--high { color: var(--c-bad); background: var(--c-danger-soft); }.priority-tag--normal { color: var(--c-accent); background: var(--c-accent-soft); }.priority-tag--low { color: var(--c-fg-1); background: var(--c-neutral-soft); }.order-status { color: var(--c-fg-1); background: var(--c-bg-2); }.order-status--submitted { color: var(--c-warn); background: var(--c-warning-soft); }.order-status--in_progress { color: var(--c-accent); background: var(--c-accent-soft); }.order-status--completed { color: var(--c-ok); background: var(--c-success-soft); }
.empty-state { display: grid; justify-items: start; gap: 6px; padding: 30px 0 18px; color: var(--c-fg-2); font-size: var(--fs-xs); }.empty-state strong { color: var(--c-fg-0); font-size: var(--fs-sm); }.empty-state a { margin-top: 5px; color: var(--c-accent); font-size: var(--fs-xs); font-weight: var(--fw-semibold); }.empty-state--compact { padding: 26px 0; }
.overview-loading { padding: 28px 0; color: var(--c-fg-2); font-size: var(--fs-sm); text-align: center; }.overview-footer { display: flex; justify-content: space-between; gap: 12px; padding: 18px 2px 0; color: var(--c-fg-2); font-size: 10px; }
@keyframes overview-card-enter { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
@media (max-width: 1120px) { .overview-main { padding-right: 28px; padding-left: 28px; }.overview-grid { grid-template-columns: minmax(0, 1fr) minmax(260px, .85fr); }.welcome-panel { padding: 30px; } }
@media (max-width: 860px) { .overview-main { padding-right: 22px; padding-left: 22px; }.metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.overview-grid { grid-template-columns: 1fr; }.equipment-panel { min-height: 280px; }.welcome-panel { min-height: 210px; } }
@media (max-width: 760px) { .overview-shell { display: block; }.overview-main { padding: 0 16px 28px; }.overview-header { min-height: 64px; }.overview-header__actions { gap: 12px; }.account-copy { display: none; }.account-menu { gap: 6px; padding-left: 10px; }.welcome-panel { align-items: flex-start; flex-direction: column; gap: 20px; padding: 24px 22px; margin-top: 18px; }.welcome-panel::after { right: -50px; }.welcome-panel::before { right: 0; }.overview-grid, .orders-panel { margin-top: 14px; }.overview-panel { padding: 19px; } }
@media (max-width: 540px) { .overview-brand { font-size: 11px; }.overview-header__actions { gap: 8px; }.assistant-link { max-width: 90px; font-size: 10px; }.account-avatar { width: 28px; height: 28px; flex-basis: 28px; }.logout-button { min-width: 34px; padding: 5px 4px; }.welcome-copy h1 { font-size: 24px; }.welcome-actions { margin-top: 20px; }.metric-grid { gap: 9px; margin-top: 12px; }.metric-card { min-height: 112px; padding: 14px; }.metric-card strong { font-size: 26px; }.overview-footer { flex-direction: column; }.order-row { grid-template-columns: minmax(0, 1fr) auto; gap: 9px 12px; padding: 12px 0; }.order-row__main { grid-column: 1 / -1; }.order-row time { text-align: left; }.panel-heading { align-items: flex-start; }.panel-link { max-width: 110px; text-align: right; }.work-order-reminder { padding: 17px; }.reminder-heading { align-items: flex-start; }.reminder-row { align-items: flex-start; flex-direction: column; gap: 8px; }.reminder-row__main { width: 100%; }.reminder-row__meta { flex-wrap: wrap; } }
@media (prefers-reduced-motion: reduce) { .primary-action { transition: none; }.welcome-panel, .metric-card, .overview-panel { animation: none; } }
</style>
