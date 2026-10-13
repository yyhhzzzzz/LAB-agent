<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import axios from 'axios'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { useRouter } from 'vue-router'
import { apiClient } from '@/api/client'
import { listEquipments } from '@/api/equipment'
import { getConversation, listConversations, type CitationSource, type ConversationSummary } from '@/api/assistant'
import { useAuthStore, type UserRole } from '@/stores/auth'
import ManagementSidebar from '@/components/ManagementSidebar.vue'

type MessageRole = 'assistant' | 'user'

interface AssistantMessage {
  id: string
  role: MessageRole
  text: string
  sources?: CitationSource[]
  error?: boolean
}

interface EquipmentOption {
  id: string
  label: string
}

const auth = useAuthStore()
const router = useRouter()
const input = ref('')
const selectedEquipment = ref('')
const isLoading = ref(false)
const errorMessage = ref('')
const apiStatus = ref<'checking' | 'online' | 'offline'>('checking')
const inputElement = ref<HTMLTextAreaElement | null>(null)
const messageListElement = ref<HTMLElement | null>(null)
const conversationId = ref<string | null>(null)
const isRestoringConversation = ref(true)
const messages = ref<AssistantMessage[]>([])
const conversations = ref<ConversationSummary[]>([])
const isLoadingConversations = ref(false)
const conversationError = ref('')
const isLoadingConversation = ref(false)
const conversationStorageKey = computed(
  () => `lab-device-assistant-conversation:${auth.user?.id ?? 'unknown'}`
)
const promptText = '遇到什么问题了，可以询问一下我'
const animatedPrompt = ref('')
const isPromptFading = ref(false)
const canShowPrompt = computed(() => !isRestoringConversation.value
  && !input.value
  && !messages.value.some(({ role }) => role === 'user'))
let promptTimer: number | undefined
let promptGeneration = 0

const equipmentOptions = ref<EquipmentOption[]>([{ id: '', label: '所有设备' }])

const clearPromptTimer = () => {
  if (promptTimer !== undefined) window.clearTimeout(promptTimer)
  promptTimer = undefined
}

const stopPromptAnimation = () => {
  promptGeneration += 1
  clearPromptTimer()
  animatedPrompt.value = ''
  isPromptFading.value = false
}

const startPromptAnimation = () => {
  stopPromptAnimation()
  if (!canShowPrompt.value) return

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    animatedPrompt.value = promptText
    return
  }

  const generation = promptGeneration
  const characters = Array.from(promptText)
  let index = 0

  const typeNextCharacter = () => {
    if (generation !== promptGeneration || !canShowPrompt.value) return

    if (index < characters.length) {
      animatedPrompt.value += characters[index]
      index += 1
      promptTimer = window.setTimeout(typeNextCharacter, 100)
      return
    }

    promptTimer = window.setTimeout(() => {
      if (generation !== promptGeneration || !canShowPrompt.value) return
      isPromptFading.value = true
      promptTimer = window.setTimeout(() => {
        if (generation !== promptGeneration || !canShowPrompt.value) return
        animatedPrompt.value = ''
        isPromptFading.value = false
        promptTimer = window.setTimeout(startPromptAnimation, 240)
      }, 240)
    }, 1000)
  }

  typeNextCharacter()
}

watch(canShowPrompt, (shouldShow) => {
  if (shouldShow) startPromptAnimation()
  else stopPromptAnimation()
}, { immediate: true })

const apiStatusLabel = computed(() => ({ checking: '检查 API', online: 'API 已连接', offline: 'API 未连接' })[apiStatus.value])
const roleLabel = computed(() => ({ student: '学生', teacher: '教师', admin: '管理员' })[auth.user?.role as UserRole] ?? '用户')
const canManageEquipment = computed(() => auth.user?.role === 'teacher' || auth.user?.role === 'admin')
const createId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`

const formatConversationDate = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间未知'
  return new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric' }).format(date)
}

const conversationTitle = (conversation: ConversationSummary) => conversation.title?.trim() || '未命名对话'
const conversationEquipmentLabel = (conversation: ConversationSummary) => {
  if (!conversation.equipment_id) return '通用对话'
  return equipmentOptions.value.find(({ id }) => id === conversation.equipment_id)?.label || '关联设备'
}

const renderAssistantMessage = (text: string) => {
  const options = {
    gfm: true,
    breaks: true
  }
  const tokens = marked.lexer(text, options)
  return DOMPurify.sanitize(marked.parser(tokens, options))
}

interface AssistantResponse {
  conversation_id: string
  query: string
  answer: string
  status: string
  sources: CitationSource[]
}

const checkApiHealth = async () => {
  try {
    await apiClient.get('/api/health')
    apiStatus.value = 'online'
  } catch {
    apiStatus.value = 'offline'
  }
}

const loadEquipmentOptions = async () => {
  try {
    const equipment = await listEquipments()
    equipmentOptions.value = [
      { id: '', label: '所有设备' },
      ...equipment.map((item) => ({ id: item.id, label: `${item.equipment_code} ${item.name}` }))
    ]
    if (!equipmentOptions.value.some((option) => option.id === selectedEquipment.value)) {
      selectedEquipment.value = ''
    }
  } catch {
    equipmentOptions.value = [{ id: '', label: '所有设备' }]
  }
}

const resetConversation = () => {
  messages.value = []
  conversationId.value = null
  sessionStorage.removeItem(conversationStorageKey.value)
  errorMessage.value = ''
  conversationError.value = ''
  void nextTick(() => inputElement.value?.focus())
}

const loadConversations = async () => {
  isLoadingConversations.value = true
  conversationError.value = ''
  try {
    conversations.value = await listConversations()
  } catch (cause) {
    conversationError.value = axios.isAxiosError(cause) && cause.response?.status === 401
      ? '登录已失效，请重新登录。'
      : '对话列表加载失败。'
  } finally {
    isLoadingConversations.value = false
  }
}

const restoreConversationById = async (id: string) => {
  if (isLoading.value || isLoadingConversation.value || id === conversationId.value) return
  isLoadingConversation.value = true
  conversationError.value = ''
  isRestoringConversation.value = true
  try {
    const data = await getConversation(id)
    selectedEquipment.value = data.equipment_selector ?? data.equipment_id ?? ''
    conversationId.value = data.conversation_id
    messages.value = data.messages.map((message) => ({
      id: message.id,
      role: message.role,
      text: message.content,
      sources: message.sources
    }))
    sessionStorage.setItem(conversationStorageKey.value, data.conversation_id)
    await nextTick()
    if (messageListElement.value) {
      messageListElement.value.scrollTop = messageListElement.value.scrollHeight
    }
  } catch (cause) {
    conversationError.value = axios.isAxiosError(cause) && cause.response?.status === 404
      ? '该对话不存在或已无权访问。'
      : '对话加载失败，请稍后重试。'
  } finally {
    isRestoringConversation.value = false
    isLoadingConversation.value = false
  }
}

const restoreConversation = async () => {
  const savedId = sessionStorage.getItem(conversationStorageKey.value)
  if (!savedId) {
    isRestoringConversation.value = false
    return
  }

  isRestoringConversation.value = true
  try {
    const data = await getConversation(savedId)
    isRestoringConversation.value = true
    conversationId.value = data.conversation_id
    messages.value = data.messages.map((message) => ({
      id: message.id,
      role: message.role,
      text: message.content,
      sources: message.sources
    }))
  } catch {
    sessionStorage.removeItem(conversationStorageKey.value)
  } finally {
    await nextTick()
    isRestoringConversation.value = false
  }
}

const logout = async () => {
  auth.logout()
  await router.replace({ name: 'login' })
}

const submitQuery = async () => {
  const question = input.value.trim()
  if (!question || isLoading.value) return

  messages.value.push({ id: createId(), role: 'user', text: question })
  input.value = ''
  errorMessage.value = ''
  isLoading.value = true

  try {
    const { data: payload } = await apiClient.post<Partial<AssistantResponse>>('/api/v1/assistant/chat', {
      query: question,
      equipment_id: selectedEquipment.value || null,
      conversation_id: conversationId.value
    })
    if (payload.conversation_id) {
      conversationId.value = payload.conversation_id
      sessionStorage.setItem(conversationStorageKey.value, payload.conversation_id)
      void loadConversations()
    }
    apiStatus.value = 'online'

    messages.value.push({
      id: createId(),
      role: 'assistant',
      text: payload.answer ?? 'Assistant 服务未返回回答。',
      sources: payload.sources ?? []
    })
  } catch (cause) {
    const detail = axios.isAxiosError<{ detail?: string }>(cause)
      ? cause.response?.data?.detail || `Assistant 服务暂时不可用${cause.response?.status ? `（HTTP ${cause.response.status}）` : ''}`
      : cause instanceof Error ? cause.message : 'Assistant 服务暂时不可用'
    apiStatus.value = axios.isAxiosError(cause) && cause.response ? 'online' : 'offline'
    errorMessage.value = detail
    if (axios.isAxiosError(cause) && cause.response?.status === 401) {
      auth.logout()
      await router.replace({ name: 'login' })
      return
    }
    messages.value.push({
      id: createId(),
      role: 'assistant',
      error: true,
      text: '这次回答没有完成。请确认后端 API 和模型配置正常，然后重试。'
    })
  } finally {
    isLoading.value = false
    void nextTick(() => inputElement.value?.focus())
  }
}

onMounted(() => {
  void checkApiHealth()
  void loadEquipmentOptions()
  void loadConversations()
  void restoreConversation()
})

onBeforeUnmount(stopPromptAnimation)

watch(selectedEquipment, () => {
  if (!isRestoringConversation.value) resetConversation()
})
</script>

<template>
  <div class="assistant-shell">
    <ManagementSidebar v-if="canManageEquipment" />
    <main class="workspace-main">
      <header class="workspace-header">
        <h1>实验室设备助手</h1>
        <div class="workspace-header__meta">
          <span class="connection-state" :class="`connection-state--${apiStatus}`">
            <span class="status-dot" aria-hidden="true" /> {{ apiStatusLabel }}
          </span>
          <button class="new-thread" type="button" :disabled="isLoading" @click="resetConversation">
            <span aria-hidden="true">＋</span>
            <span>新建会话</span>
          </button>
          <RouterLink class="management-link" :to="{ name: 'dashboard' }">实验室总览</RouterLink>
          <RouterLink v-if="canManageEquipment" class="management-link" :to="{ name: 'management-equipment' }">管理控制台</RouterLink>
          <div class="account-menu" :title="auth.user?.username">
            <span class="account-avatar" aria-hidden="true">{{ auth.user?.display_name?.slice(0, 1) || '用' }}</span>
            <span class="account-copy"><strong>{{ auth.user?.display_name }}</strong><small>{{ roleLabel }}</small></span>
            <button class="logout-button" type="button" @click="logout">退出</button>
          </div>
        </div>
      </header>

      <div class="assistant-layout">
        <section class="conversation" aria-labelledby="conversation-heading">
          <div class="conversation__topline">
            <h2 id="conversation-heading" class="sr-only">对话</h2>
            <label class="conversation__scope" for="equipment-select">
              <span class="sr-only">设备</span>
              <select id="equipment-select" v-model="selectedEquipment" class="equipment-select">
                <option v-for="option in equipmentOptions" :key="option.id || 'all'" :value="option.id">
                  {{ option.label }}
                </option>
              </select>
            </label>
          </div>

          <div ref="messageListElement" class="message-list" aria-live="polite">
            <article
              v-for="message in messages"
              :key="message.id"
              class="message"
              :class="[`message--${message.role}`, { 'message--error': message.error }]"
            >
              <div class="message__meta">
                <span class="message__role">{{ message.role === 'assistant' ? 'ASSISTANT' : '你' }}</span>
              </div>
              <div v-if="message.role === 'assistant'" class="message__body message__body--markdown" v-html="renderAssistantMessage(message.text)" />
              <div v-else class="message__body">
                <p v-for="(paragraph, index) in message.text.split('\n\n')" :key="index">{{ paragraph }}</p>
              </div>
              <ul v-if="message.sources?.length" class="message__sources" aria-label="回答来源">
                <li v-for="source in message.sources" :key="source.id">
                  <span class="mono">{{ source.id }}</span>
                  <span v-if="source.type === 'work_order'">维修工单：{{ source.title }}</span>
                  <span v-else>{{ source.title }} / {{ source.chapter || '未标注章节' }}</span>
                  <span v-if="source.type === 'work_order' && source.resolution">{{ source.resolution }}</span>
                  <span v-if="source.type !== 'work_order' && source.page_start" class="mono">
                    第 {{ source.page_start }}<template v-if="source.page_end && source.page_end !== source.page_start">-{{ source.page_end }}</template> 页
                  </span>
                </li>
              </ul>
            </article>

            <div v-if="isLoading" class="message message--assistant message--loading" aria-label="正在生成回答">
              <div class="message__meta">
                <span class="message__role">ASSISTANT</span>
              </div>
              <div class="loading-line"><span /><span /><span /></div>
            </div>
          </div>

          <div class="composer-wrap">
            <div v-if="errorMessage" class="composer-error" role="alert">{{ errorMessage }}</div>
            <form class="composer" @submit.prevent="submitQuery">
              <textarea
                ref="inputElement"
                v-model="input"
                :class="{ 'composer__textarea--fading': isPromptFading }"
                rows="1"
                aria-label="输入设备问题"
                :placeholder="animatedPrompt"
                @keydown.enter.exact.prevent="submitQuery"
              />
              <div class="composer__footer">
                <button class="send-button" type="submit" :disabled="isLoading || !input.trim()" title="发送问题">
                  <span aria-hidden="true">↑</span>
                  <span class="sr-only">发送问题</span>
                </button>
              </div>
            </form>
          </div>
        </section>

        <aside class="conversation-history" aria-labelledby="conversation-history-heading">
          <div class="conversation-history__heading">
            <div>
              <p class="eyebrow">YOUR WORKSPACE</p>
              <h2 id="conversation-history-heading">对话记录</h2>
            </div>
            <button type="button" class="history-refresh" :disabled="isLoadingConversations" aria-label="刷新对话列表" @click="loadConversations">↻</button>
          </div>
          <p v-if="conversationError" class="history-error" role="alert">{{ conversationError }}</p>
          <p v-if="isLoadingConversations && !conversations.length" class="history-empty">正在加载对话…</p>
          <p v-else-if="!conversations.length" class="history-empty">还没有历史对话。开始提问后，对话会保存在这里。</p>
          <nav v-else class="conversation-history__list" aria-label="当前用户的所有对话">
            <button
              v-for="conversation in conversations"
              :key="conversation.id"
              type="button"
              class="conversation-history__item"
              :class="{ 'conversation-history__item--active': conversation.id === conversationId }"
              :disabled="isLoadingConversation || isLoading"
              :aria-current="conversation.id === conversationId ? 'page' : undefined"
              @click="restoreConversationById(conversation.id)"
            >
              <span class="conversation-history__title">{{ conversationTitle(conversation) }}</span>
              <span class="conversation-history__meta">
                <span>{{ formatConversationDate(conversation.updated_at) }}</span>
                <span class="conversation-history__scope" :title="conversationEquipmentLabel(conversation)">{{ conversationEquipmentLabel(conversation) }}</span>
              </span>
            </button>
          </nav>
          <p v-if="isLoadingConversation" class="history-loading" role="status">正在恢复对话…</p>
        </aside>

      </div>
    </main>
  </div>
</template>

<style scoped>
.assistant-shell {
  height: 100dvh;
  display: flex;
  overflow: hidden;
  background: var(--c-bg-0);
}

.new-thread {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 34px;
  padding: 0 10px;
  color: var(--c-fg-1);
  border: 1px solid var(--c-line-2);
  border-radius: var(--r-sm);
  font-size: var(--fs-sm);
  transition: background var(--dur-fast) var(--ease-out), color var(--dur-fast) var(--ease-out);
}

.new-thread:hover { color: var(--c-accent); background: var(--c-accent-soft); border-color: var(--c-accent-line); }
.new-thread:active { transform: translateY(1px); }
.management-link { padding: 5px 8px; color: var(--c-accent); border: 1px solid var(--c-accent-line); border-radius: var(--r-sm); font-size: var(--fs-sm); }
.management-link:hover { background: var(--c-accent-soft); }

.status-dot { display: inline-block; width: 6px; height: 6px; flex: 0 0 auto; background: var(--c-ok); border-radius: 50%; }

.workspace-main { display: flex; flex: 1; flex-direction: column; min-width: 0; min-height: 0; height: 100dvh; padding: 32px 48px 40px; overflow: hidden; }
.workspace-header { display: flex; align-items: center; justify-content: space-between; gap: 24px; max-width: 1280px; margin: 0 auto 24px; padding-bottom: 16px; border-bottom: 1px solid var(--c-line-1); flex-wrap: wrap; }
.workspace-header h1 { font-size: 24px; }
.workspace-header__meta { display: flex; align-items: center; justify-content: flex-end; gap: 18px; min-width: 0; color: var(--c-fg-1); font-size: var(--fs-sm); flex-wrap: wrap; }
.connection-state { display: inline-flex; align-items: center; gap: 7px; }
.connection-state--checking .status-dot { background: var(--c-warn); }
.connection-state--offline .status-dot { background: var(--c-bad); }
.account-menu { display: flex; align-items: center; gap: 9px; flex: 0 0 auto; min-width: max-content; padding-left: 15px; border-left: 1px solid var(--c-line-1); }
.account-avatar { display: grid; width: 30px; height: 30px; place-items: center; border-radius: 50%; color: var(--c-accent); background: var(--c-accent-soft); font-size: 12px; font-weight: 600; }
.account-copy { display: grid; gap: 1px; min-width: 0; color: var(--c-fg-0); line-height: 1.3; }
.account-copy strong { max-width: 100px; overflow: hidden; font-size: 11px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.account-copy small { color: var(--c-fg-2); font-size: 10px; }
.logout-button { min-width: 38px; flex: 0 0 auto; padding: 5px 7px; color: var(--c-fg-1); border-radius: var(--r-sm); font-size: 11px; white-space: nowrap; }
.logout-button:hover { color: var(--c-bad); background: var(--c-danger-soft); }

.assistant-layout { display: grid; flex: 1; grid-template-columns: minmax(0, 1fr) 270px; grid-template-rows: minmax(0, 1fr); gap: 24px; width: 100%; max-width: 1280px; min-height: 0; margin: 0 auto; }
.conversation { display: flex; min-width: 0; min-height: 0; flex-direction: column; }
.conversation-history { display: flex; min-width: 0; min-height: 0; flex-direction: column; padding: 16px 12px; overflow: hidden; background: var(--c-bg-1); border: 1px solid var(--c-line-1); border-radius: var(--r-md); }
.conversation-history__heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 2px 4px 14px; border-bottom: 1px solid var(--c-line-1); }
.conversation-history__heading h2 { margin-top: 6px; font-size: 15px; }
.history-refresh { display: grid; width: 30px; height: 30px; place-items: center; color: var(--c-fg-1); border: 1px solid var(--c-line-2); border-radius: var(--r-sm); font-size: 17px; }.history-refresh:hover:not(:disabled) { color: var(--c-accent); background: var(--c-accent-soft); }.history-refresh:disabled { opacity: .5; }
.conversation-history__list { display: grid; align-content: start; gap: 4px; min-height: 0; padding-top: 10px; overflow-y: auto; overscroll-behavior: contain; }
.conversation-history__item { display: grid; gap: 7px; width: 100%; min-width: 0; padding: 11px 10px; color: var(--c-fg-1); border: 1px solid transparent; border-radius: var(--r-sm); text-align: left; transition: background var(--dur-fast), border-color var(--dur-fast), color var(--dur-fast); }
.conversation-history__item:hover:not(:disabled) { color: var(--c-fg-0); background: var(--c-bg-2); }.conversation-history__item--active { color: var(--c-accent); background: var(--c-accent-soft); border-color: var(--c-accent-line); }.conversation-history__item:disabled { cursor: wait; opacity: .65; }
.conversation-history__title { overflow: hidden; font-size: var(--fs-sm); font-weight: var(--fw-medium); text-overflow: ellipsis; white-space: nowrap; }
.conversation-history__meta { display: flex; justify-content: space-between; gap: 8px; color: var(--c-fg-2); font-size: 10px; }.conversation-history__scope { color: var(--c-accent); }
.history-empty { padding: 18px 5px; color: var(--c-fg-2); font-size: var(--fs-xs); line-height: 1.55; }.history-error { padding: 8px 5px; color: var(--c-bad); font-size: var(--fs-xs); }.history-loading { padding: 9px 5px; color: var(--c-fg-2); font-size: var(--fs-xs); }
.conversation__topline { display: flex; align-items: center; justify-content: flex-end; gap: 16px; padding: 0 0 12px; }
.conversation__scope { width: min(280px, 45%); color: var(--c-fg-1); font-size: var(--fs-sm); }
.message-list { flex: 1; min-height: 0; padding: 8px 0 22px; overflow-y: auto; overscroll-behavior: contain; }
.message { max-width: 760px; padding: 20px 0; border-bottom: 1px solid var(--c-line-1); animation: messageIn var(--dur-base) var(--ease-out) both; }
.message--user { margin-left: auto; padding: 15px 16px; margin-top: 12px; margin-bottom: 12px; background: var(--c-bg-2); border: 0; border-left: 2px solid var(--c-accent-line); border-radius: var(--r-sm); }
.message--error { border-left: 2px solid var(--c-bad); padding-left: 14px; }
.message__meta { display: flex; align-items: center; gap: 9px; margin-bottom: 9px; color: var(--c-fg-2); font: 500 10px/1.2 var(--ff-mono); letter-spacing: 0.09em; }
.message--user .message__meta { justify-content: flex-end; }
.message__role { color: var(--c-accent); }
.message--user .message__role { color: var(--c-fg-1); }
.message__body { max-width: 68ch; color: var(--c-fg-0); font-size: 14px; line-height: 1.72; }
.message--user .message__body { text-align: right; }
.message__body p + p { margin-top: 10px; }
.message__body--markdown :deep(p + p) { margin-top: 10px; }
.message__body--markdown :deep(h1), .message__body--markdown :deep(h2), .message__body--markdown :deep(h3) { margin: 18px 0 8px; color: var(--c-fg-0); font-weight: var(--fw-semibold); line-height: 1.35; }
.message__body--markdown :deep(h1:first-child), .message__body--markdown :deep(h2:first-child), .message__body--markdown :deep(h3:first-child) { margin-top: 0; }
.message__body--markdown :deep(ul), .message__body--markdown :deep(ol) { display: grid; gap: 5px; padding-left: 22px; margin: 10px 0; }
.message__body--markdown :deep(li)::marker { color: var(--c-accent); }
.message__body--markdown :deep(blockquote) { padding: 8px 13px; margin: 12px 0; color: var(--c-fg-1); border-left: 2px solid var(--c-accent-line); background: var(--c-bg-2); }
.message__body--markdown :deep(code) { padding: 2px 5px; color: var(--c-accent); background: var(--c-accent-soft); border-radius: var(--r-xs); font: .9em var(--ff-mono); }
.message__body--markdown :deep(pre) { padding: 12px 14px; margin: 12px 0; overflow-x: auto; background: var(--c-bg-2); border: 1px solid var(--c-line-1); border-radius: var(--r-sm); }
.message__body--markdown :deep(pre code) { padding: 0; color: var(--c-fg-0); background: transparent; font-size: 12px; }
.message__body--markdown :deep(a) { color: var(--c-accent); text-decoration: underline; text-underline-offset: 2px; }
.message__body--markdown :deep(hr) { margin: 16px 0; border: 0; border-top: 1px solid var(--c-line-1); }
.message__body--markdown :deep(table) { display: block; width: 100%; margin: 12px 0; overflow-x: auto; border-collapse: collapse; font-size: var(--fs-sm); }
.message__body--markdown :deep(th), .message__body--markdown :deep(td) { padding: 7px 9px; border: 1px solid var(--c-line-1); text-align: left; vertical-align: top; }
.message__body--markdown :deep(th) { color: var(--c-fg-0); background: var(--c-bg-2); font-weight: var(--fw-semibold); }
.message__sources { display: grid; gap: 7px; padding: 12px 0 0; margin: 14px 0 0; border-top: 1px solid var(--c-line-1); color: var(--c-fg-1); font-size: var(--fs-xs); list-style: none; }
.message__sources li { display: flex; flex-wrap: wrap; gap: 6px 10px; }
.message__sources .mono { color: var(--c-accent); }

.loading-line { display: flex; align-items: center; gap: 5px; height: 23px; }
.loading-line span { width: 6px; height: 6px; background: var(--c-accent); border-radius: 50%; animation: loadingPulse 1.1s ease-in-out infinite; }
.loading-line span:nth-child(2) { animation-delay: 120ms; }
.loading-line span:nth-child(3) { animation-delay: 240ms; }

.composer-wrap { flex: 0 0 auto; padding-top: 14px; }
.composer-error { padding: 8px 10px; margin-bottom: 8px; color: var(--c-bad); background: rgba(185, 28, 28, 0.06); border-left: 2px solid var(--c-bad); font-size: var(--fs-sm); }
.composer { padding: 12px 14px 10px; background: var(--c-bg-1); border: 1px solid var(--c-line-2); border-radius: var(--r-md); transition: border-color var(--dur-fast), box-shadow var(--dur-fast); }
.composer:focus-within { border-color: var(--c-accent); box-shadow: 0 0 0 3px var(--c-accent-soft); }
.composer textarea { display: block; width: 100%; min-height: 42px; max-height: 120px; resize: vertical; color: var(--c-fg-0); background: transparent; border: 0; outline: 0; font-size: 14px; line-height: 1.6; }
.composer textarea::placeholder { color: var(--c-fg-2); opacity: 1; transition: opacity 240ms ease; }
.composer textarea.composer__textarea--fading::placeholder { opacity: 0; }
.composer__footer { display: flex; align-items: center; justify-content: flex-end; margin-top: 8px; }
.send-button { display: grid; place-items: center; width: 28px; height: 28px; flex: 0 0 auto; color: var(--c-accent-fg); background: var(--c-accent); border-radius: var(--r-sm); font-size: 18px; line-height: 1; transition: background var(--dur-fast), transform var(--dur-fast), opacity var(--dur-fast); }
.send-button:hover:not(:disabled) { background: var(--c-accent-3); }
.send-button:active:not(:disabled) { transform: translateY(1px) scale(0.98); }
.send-button:disabled { cursor: not-allowed; opacity: 0.35; }

.equipment-select { width: 100%; padding: 8px 28px 8px 9px; color: var(--c-fg-0); background: var(--c-bg-1); border: 1px solid var(--c-line-2); border-radius: var(--r-sm); outline: 0; font-size: var(--fs-sm); }
.equipment-select:focus { border-color: var(--c-accent); }

.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@keyframes messageIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
@keyframes loadingPulse { 0%, 100% { opacity: 0.28; transform: scale(0.82); } 50% { opacity: 1; transform: scale(1); } }

@media (prefers-reduced-motion: reduce) {
  .composer textarea::placeholder { transition: none; }
}

@media (max-width: 1120px) {
  .workspace-main { padding: 28px 30px 36px; }
}

@media (max-width: 760px) {
  .assistant-shell { flex-direction: column; }
  .workspace-main { width: 100%; height: auto; padding: 20px 16px 16px; }
  .workspace-header { margin-bottom: 16px; }
  .workspace-header h1 { font-size: 20px; }
  .workspace-header__meta { gap: 10px; font-size: var(--fs-xs); }
  .account-menu { gap: 6px; padding-left: 8px; }
  .account-copy { display: none; }
  .logout-button { padding: 5px; }
  .new-thread { padding: 0 8px; font-size: var(--fs-xs); }
  .assistant-layout { grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(420px, 1fr) auto; gap: 16px; min-height: 0; }
  .conversation-history { max-height: 280px; }
  .conversation-history__list { max-height: 180px; }
  .conversation__scope { width: 100%; max-width: 100%; }
}
</style>
