import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/OverviewView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/assistant',
      name: 'assistant',
      component: () => import('@/views/AssistantView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { guestOnly: true }
    },
    {
      path: '/management',
      alias: '/equipment-management',
      name: 'equipment-management',
      component: () => import('@/views/EquipmentManagementView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/management/equipment',
      name: 'management-equipment',
      component: () => import('@/views/EquipmentManagementView.vue'),
      meta: { requiresAuth: true, roles: ['teacher', 'admin'] }
    },
    {
      path: '/management/work-orders',
      name: 'management-work-orders',
      component: () => import('@/views/WorkOrderManagementView.vue'),
      meta: { requiresAuth: true, roles: ['student', 'teacher', 'admin'] }
    },
    {
      path: '/management/users',
      name: 'management-users',
      component: () => import('@/views/EquipmentManagementView.vue'),
      meta: { requiresAuth: true, roles: ['teacher', 'admin'] }
    },
    {
      path: '/management/laboratories',
      name: 'management-laboratories',
      component: () => import('@/views/EquipmentManagementView.vue'),
      meta: { requiresAuth: true, roles: ['admin'] }
    }
  ]
})

router.beforeEach((to) => {
  const auth = useAuthStore()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.guestOnly && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }

  if (to.name === 'equipment-management' && (auth.user?.role === 'teacher' || auth.user?.role === 'admin')) {
    return { name: 'management-equipment' }
  }

  const roles = to.meta.roles as string[] | undefined
  if (roles && (!auth.user || !roles.includes(auth.user.role))) {
    return { name: 'dashboard' }
  }
})
