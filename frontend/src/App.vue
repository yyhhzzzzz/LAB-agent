<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const activeTheme = computed(() => route.name === 'login' ? 'guest' : auth.user?.role || 'guest')
</script>

<template>
  <div class="app-shell" :data-role="activeTheme">
    <RouterView />
  </div>
</template>

<style>
.app-shell {
  min-height: 100%;
  background: var(--c-bg-0);
  transition: background-color 260ms ease;
}
</style>
