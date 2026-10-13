<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { collapsedAfterNavigation } from '@/stores/managementSidebar'

const auth = useAuthStore()
const canManageLabs = computed(() => auth.user?.role === 'admin')
const collapseAfterClick = (event: MouseEvent) => {
  collapsedAfterNavigation.value = true
  ;(event.currentTarget as HTMLElement | null)?.blur()
}
const allowHoverExpand = () => {
  collapsedAfterNavigation.value = false
}
</script>

<template>
  <aside
    class="management-sidebar"
    :class="{ 'management-sidebar--collapsed': collapsedAfterNavigation }"
    aria-label="管理模块"
    @mouseleave="allowHoverExpand"
  >
    <div class="management-sidebar__brand">
      <span class="management-sidebar__mark" aria-hidden="true"><span /><span /><span /></span>
      <span class="management-sidebar__label">管理控制台</span>
    </div>
    <nav class="management-sidebar__nav">
      <RouterLink class="management-sidebar__link" :to="{ name: 'dashboard' }" title="实验室总览" @click="collapseAfterClick">
        <span class="management-sidebar__icon" aria-hidden="true">⌂</span>
        <span class="management-sidebar__label">实验室总览</span>
      </RouterLink>
      <RouterLink class="management-sidebar__link" :to="{ name: 'management-equipment' }" title="设备管理" @click="collapseAfterClick">
        <span class="management-sidebar__icon" aria-hidden="true">▦</span>
        <span class="management-sidebar__label">设备管理</span>
      </RouterLink>
      <RouterLink class="management-sidebar__link" :to="{ name: 'management-work-orders' }" title="工单管理" @click="collapseAfterClick">
        <span class="management-sidebar__icon" aria-hidden="true">▤</span>
        <span class="management-sidebar__label">工单管理</span>
      </RouterLink>
      <RouterLink class="management-sidebar__link" :to="{ name: 'management-users' }" title="用户管理" @click="collapseAfterClick">
        <span class="management-sidebar__icon" aria-hidden="true">◎</span>
        <span class="management-sidebar__label">用户管理</span>
      </RouterLink>
      <RouterLink v-if="canManageLabs" class="management-sidebar__link" :to="{ name: 'management-laboratories' }" title="实验室管理" @click="collapseAfterClick">
        <span class="management-sidebar__icon" aria-hidden="true">⌂</span>
        <span class="management-sidebar__label">实验室管理</span>
      </RouterLink>
    </nav>
    <RouterLink class="management-sidebar__back" :to="{ name: 'assistant' }" title="打开设备助手" @click="collapseAfterClick">
      <span aria-hidden="true">←</span>
      <span class="management-sidebar__label">设备助手</span>
    </RouterLink>
  </aside>
</template>

<style scoped>
.management-sidebar { position: sticky; top: 0; align-self: flex-start; display: flex; flex-direction: column; width: 68px; height: 100dvh; flex: 0 0 68px; min-height: 100dvh; padding: 28px 10px 24px; overflow: hidden; background: var(--c-bg-1); border-right: 1px solid var(--c-line-1); transition: width 220ms var(--ease-out), flex-basis 220ms var(--ease-out), padding 220ms var(--ease-out); }
.management-sidebar:hover { width: 220px; flex-basis: 220px; padding-right: 16px; padding-left: 16px; }
.management-sidebar__brand { display: flex; align-items: center; justify-content: center; gap: 10px; width: 100%; min-width: 0; padding: 0 0 28px; color: var(--c-fg-0); font-size: 13px; font-weight: var(--fw-semibold); letter-spacing: .04em; }
.management-sidebar:hover .management-sidebar__brand { justify-content: flex-start; }
.management-sidebar__mark { display: inline-flex; align-items: center; justify-content: center; gap: 2px; width: 25px; height: 25px; border: 1px solid var(--c-accent-line); border-radius: var(--r-sm); }
.management-sidebar__mark span { width: 2px; border-radius: 2px; background: var(--c-accent); }.management-sidebar__mark span:nth-child(1) { height: 7px; }.management-sidebar__mark span:nth-child(2) { height: 12px; }.management-sidebar__mark span:nth-child(3) { height: 9px; }
.management-sidebar__label { overflow: hidden; max-width: 0; opacity: 0; white-space: nowrap; transition: max-width 180ms var(--ease-out), opacity 120ms ease; }
.management-sidebar:hover .management-sidebar__label { max-width: 150px; opacity: 1; }
.management-sidebar__nav { display: grid; gap: 5px; }
.management-sidebar__link { display: flex; align-items: center; justify-content: center; gap: 10px; min-height: 40px; padding: 0 10px; color: var(--c-fg-1); border-radius: var(--r-sm); font-size: var(--fs-sm); transition: background var(--dur-fast), color var(--dur-fast); }
.management-sidebar:hover .management-sidebar__link { justify-content: flex-start; }
.management-sidebar__link:hover { color: var(--c-accent); background: var(--c-accent-soft); }.management-sidebar__link.router-link-active { color: var(--c-accent); background: var(--c-accent-soft); font-weight: var(--fw-semibold); }
.management-sidebar__icon { display: grid; width: 18px; height: 18px; place-items: center; color: currentColor; font-size: 16px; line-height: 1; }
.management-sidebar__back { display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; min-width: 0; margin-top: auto; padding: 10px 0; color: var(--c-fg-2); font-size: var(--fs-xs); }.management-sidebar:hover .management-sidebar__back { justify-content: flex-start; padding-right: 10px; padding-left: 10px; }.management-sidebar__back:hover { color: var(--c-accent); }
@media (min-width: 761px) {
  .management-sidebar.management-sidebar--collapsed, .management-sidebar.management-sidebar--collapsed:hover { width: 68px; flex-basis: 68px; padding-right: 10px; padding-left: 10px; }
  .management-sidebar.management-sidebar--collapsed .management-sidebar__brand, .management-sidebar.management-sidebar--collapsed:hover .management-sidebar__brand { justify-content: center; }
  .management-sidebar.management-sidebar--collapsed .management-sidebar__label, .management-sidebar.management-sidebar--collapsed:hover .management-sidebar__label { max-width: 0; opacity: 0; }
  .management-sidebar.management-sidebar--collapsed .management-sidebar__link, .management-sidebar.management-sidebar--collapsed:hover .management-sidebar__link { justify-content: center; }
  .management-sidebar.management-sidebar--collapsed .management-sidebar__back, .management-sidebar.management-sidebar--collapsed:hover .management-sidebar__back { justify-content: center; padding-right: 0; padding-left: 0; }
}
@media (max-width: 760px) { .management-sidebar { position: static; top: auto; align-self: stretch; width: 100%; height: auto; flex-basis: auto; min-height: auto; padding: 16px; overflow: visible; border-right: 0; border-bottom: 1px solid var(--c-line-1); transition: none; }.management-sidebar:hover, .management-sidebar:focus-within { width: 100%; flex-basis: auto; padding: 16px; }.management-sidebar__brand, .management-sidebar:hover .management-sidebar__brand, .management-sidebar:focus-within .management-sidebar__brand { justify-content: flex-start; min-width: 0; padding: 0 4px 14px; }.management-sidebar__label, .management-sidebar:hover .management-sidebar__label, .management-sidebar:focus-within .management-sidebar__label { max-width: 150px; opacity: 1; }.management-sidebar__nav { grid-template-columns: repeat(3, minmax(0, 1fr)); }.management-sidebar__link, .management-sidebar:hover .management-sidebar__link, .management-sidebar:focus-within .management-sidebar__link { justify-content: center; padding: 0 6px; }.management-sidebar__back { display: none; } }
</style>
