<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore, type UserRole } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const warpRole = ref<UserRole | null>(null)
const storyArt = ref<HTMLElement | null>(null)
const galaxyCamera = ref<HTMLElement | null>(null)
const studentOrbit = ref<HTMLElement | null>(null)
const teacherOrbit = ref<HTMLElement | null>(null)
const adminOrbit = ref<HTMLElement | null>(null)
const focusStyle = ref('')
const coverStyle = ref('')

const roleScenes: Record<UserRole, { label: string; code: string }> = {
  student: { label: '学习星', code: 'ACCESS / STUDENT' },
  teacher: { label: '教师端', code: 'DEVICE / TEACHER' },
  admin: { label: '中枢星', code: 'CORE / ADMIN' }
}

const warpScene = computed(() => warpRole.value ? roleScenes[warpRole.value] : null)
const focusScale: Record<UserRole, number> = { student: 2.45, teacher: 2.45, admin: 2.55 }
const warpDuration = 1250
const coverDuration = 680
let focusFrame: number | null = null
let coverFrame: number | null = null
let coverTimer: number | null = null
let finishWarp: (() => void) | null = null
let isUnmounted = false

const orbitForRole = (role: UserRole) => ({
  student: studentOrbit,
  teacher: teacherOrbit,
  admin: adminOrbit
}[role]).value

const cancelFocusFrame = () => {
  if (focusFrame !== null && typeof window !== 'undefined') window.cancelAnimationFrame(focusFrame)
  focusFrame = null
}

const cancelCoverAnimation = () => {
  if (coverFrame !== null && typeof window !== 'undefined') window.cancelAnimationFrame(coverFrame)
  if (coverTimer !== null && typeof window !== 'undefined') window.clearTimeout(coverTimer)
  coverFrame = null
  coverTimer = null
}

const expandRoleCover = async (role: UserRole) => {
  if (isUnmounted || typeof window === 'undefined') return

  const orbit = orbitForRole(role)
  const planet = orbit?.querySelector<HTMLElement>('.role-planet')
  if (!planet) return

  const planetRect = planet.getBoundingClientRect()
  const originX = planetRect.left + planetRect.width / 2
  const originY = planetRect.top + planetRect.height / 2
  const farthestX = Math.max(originX, window.innerWidth - originX)
  const farthestY = Math.max(originY, window.innerHeight - originY)
  const radius = Math.ceil(Math.hypot(farthestX, farthestY) + 24)
  const origin = `${originX.toFixed(1)}px ${originY.toFixed(1)}px`

  coverStyle.value = `clip-path: circle(0px at ${origin});`
  await nextTick()
  if (isUnmounted) return

  await new Promise<void>((resolve) => {
    coverFrame = window.requestAnimationFrame(() => {
      coverFrame = null
      coverStyle.value = `clip-path: circle(${radius}px at ${origin});`
      coverTimer = window.setTimeout(() => {
        coverTimer = null
        resolve()
      }, coverDuration)
    })
  })
}

const waitForRoleWarp = async (role: UserRole) => {
  warpRole.value = role
  const reducedMotion = typeof window !== 'undefined'
    && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  if (reducedMotion || typeof window === 'undefined') return

  await new Promise<void>((resolve) => {
    const art = storyArt.value
    const camera = galaxyCamera.value
    const orbit = orbitForRole(role)
    const planet = orbit?.querySelector<HTMLElement>('.role-planet')
    if (!art || !camera || !planet) {
      resolve()
      return
    }

    const finalScale = focusScale[role]
    let currentScale = 1
    let currentShiftX = 0
    let currentShiftY = 0
    let initialLocalX: number | null = null
    let initialLocalY: number | null = null
    let startedAt: number | null = null

    finishWarp = () => {
      finishWarp = null
      cancelFocusFrame()
      resolve()
    }

    const tick = (timestamp: number) => {
      if (startedAt === null) startedAt = timestamp
      const progress = Math.min((timestamp - startedAt) / warpDuration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      const artRect = art.getBoundingClientRect()
      const artCenterX = artRect.width / 2
      const artCenterY = artRect.height / 2
      const planetRect = planet.getBoundingClientRect()
      const planetScreenX = planetRect.left + planetRect.width / 2 - artRect.left
      const planetScreenY = planetRect.top + planetRect.height / 2 - artRect.top
      const localX = (planetScreenX - artCenterX - currentShiftX) / currentScale + artCenterX
      const localY = (planetScreenY - artCenterY - currentShiftY) / currentScale + artCenterY
      if (initialLocalX === null || initialLocalY === null) {
        initialLocalX = localX
        initialLocalY = localY
      }

      const nextScale = 1 + (finalScale - 1) * eased
      currentShiftX = (initialLocalX - artCenterX) * (1 - eased) - (localX - artCenterX) * nextScale
      currentShiftY = (initialLocalY - artCenterY) * (1 - eased) - (localY - artCenterY) * nextScale
      currentScale = nextScale
      focusStyle.value = `transform: translate(${currentShiftX.toFixed(1)}px, ${currentShiftY.toFixed(1)}px) scale(${currentScale.toFixed(4)});`

      if (progress >= 1) {
        finishWarp?.()
        return
      }
      focusFrame = window.requestAnimationFrame(tick)
    }

    focusFrame = window.requestAnimationFrame(tick)
  })

  if (!isUnmounted) await expandRoleCover(role)
}

const submit = async () => {
  if (auth.isLoading || warpRole.value) return
  if (!username.value.trim() || !password.value) {
    auth.error = '请输入用户名和密码。'
    return
  }

  try {
    await auth.login(username.value.trim(), password.value)
    if (auth.user?.role) await waitForRoleWarp(auth.user.role)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    const safeRedirect = redirect.startsWith('/') && !redirect.startsWith('//') && !redirect.includes('\\')
      ? redirect
      : '/'
    await router.replace(safeRedirect)
  } catch {
    // Store owns the user-facing error message.
  }
}

onBeforeUnmount(() => {
  isUnmounted = true
  cancelFocusFrame()
  cancelCoverAnimation()
  finishWarp?.()
})
</script>

<template>
  <main class="login-page" :class="{ 'login-page--transitioning': warpRole }">
    <section class="login-story" aria-label="实验室设备助手介绍" :aria-busy="Boolean(warpRole)">
      <a class="brand" href="/" aria-label="实验室设备助手首页">
        <span class="brand-mark" aria-hidden="true"><span /><span /><span /></span>
        <span>LAB<span class="brand-light">DEVICE</span></span>
      </a>

      <div class="story-copy">
        <p class="eyebrow">LABORATORY EQUIPMENT ASSISTANT</p>
        <h1>武昌理工学院实验室</h1>
      </div>

      <div
        ref="storyArt"
        class="story-art"
        :class="[
          { 'story-art--warping': warpRole },
          warpRole ? `story-art--${warpRole}` : ''
        ]"
        aria-hidden="true"
      >
        <div ref="galaxyCamera" class="galaxy-camera" :style="focusStyle">
          <div class="galaxy-haze" />
          <div class="galaxy-stars galaxy-stars--far" />
          <div class="galaxy-stars galaxy-stars--near" />
          <div class="galaxy-sphere">
            <div class="sphere-glow" />
            <div class="sphere-surface" />
            <span class="sphere-line sphere-line--one" />
            <span class="sphere-line sphere-line--two" />
            <span class="sphere-line sphere-line--three" />
          </div>
          <div ref="studentOrbit" class="planet-orbit planet-orbit--student">
            <div class="role-planet role-planet--student" />
          </div>
          <div ref="teacherOrbit" class="planet-orbit planet-orbit--teacher">
            <div class="role-planet role-planet--teacher" />
          </div>
          <div ref="adminOrbit" class="planet-orbit planet-orbit--admin">
            <div class="role-planet role-planet--admin" />
          </div>
        </div>
        <div v-if="warpScene" class="warp-caption">
          <span>{{ warpScene.code }}</span>
          <strong>进入 {{ warpScene.label }}</strong>
        </div>
      </div>

    </section>

    <section class="login-panel" aria-labelledby="login-title">
      <div class="login-panel__top"><span>欢迎回来</span><span class="secure-note"><span class="secure-dot" /> 安全登录</span></div>

      <div class="login-form-wrap">
        <div class="form-heading">
          <p class="eyebrow">WORKSPACE ACCESS</p>
          <h2 id="login-title">登录工作台</h2>
        </div>

        <form class="login-form" @submit.prevent="submit">
          <label for="username">用户名</label>
          <div class="input-wrap">
            <svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="6.2" r="3.1" /><path d="M3.7 17c.5-3.2 2.8-5 6.3-5s5.8 1.8 6.3 5" /></svg>
            <input
              id="username"
              v-model="username"
              autocomplete="username"
              name="username"
              placeholder="输入用户名"
              required
              autofocus
            />
          </div>

          <label for="password">密码</label>
          <div class="input-wrap">
            <svg viewBox="0 0 20 20" aria-hidden="true"><rect x="3.5" y="8.5" width="13" height="9" rx="1.7" /><path d="M6.4 8.5V6.2a3.6 3.6 0 0 1 7.2 0v2.3M10 12v2" /></svg>
            <input
              id="password"
              v-model="password"
              autocomplete="current-password"
              name="password"
              placeholder="输入密码"
              required
              type="password"
            />
          </div>

          <p v-if="auth.error" class="form-error" role="alert">{{ auth.error }}</p>

          <button class="submit-button" type="submit" :disabled="auth.isLoading || Boolean(warpRole)">
            <span>{{ warpRole ? '正在进入工作台…' : auth.isLoading ? '正在登录…' : '登录工作台' }}</span>
            <svg v-if="!auth.isLoading && !warpRole" viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10h11M10 5l5 5-5 5" /></svg>
            <span v-else class="spinner" aria-hidden="true" />
          </button>
        </form>

      </div>

      <footer class="login-footer"><span>© 2026 LAB DEVICE</span></footer>
    </section>

    <div
      v-if="coverStyle"
      class="warp-cover"
      :class="`warp-cover--${warpRole}`"
      :style="coverStyle"
      aria-hidden="true"
    />
  </main>
</template>

<style scoped>
.login-page { min-height: 100dvh; display: grid; grid-template-columns: minmax(480px, 1.06fr) minmax(460px, .94fr); background: var(--c-bg-1); }
.login-story { position: relative; isolation: isolate; display: flex; flex-direction: column; min-height: 100dvh; padding: 38px clamp(38px, 6vw, 92px) 28px; overflow: hidden; color: #f5f6f0; background: #123b37; }
.login-story::before, .login-story::after { position: absolute; z-index: -1; content: ''; border: 1px solid rgba(214, 227, 214, .09); border-radius: 50%; }
.login-story::before { width: 780px; height: 780px; top: 12%; left: -36%; }
.login-story::after { width: 520px; height: 520px; bottom: -36%; right: -23%; }
.brand { display: inline-flex; align-items: center; align-self: flex-start; gap: 11px; color: #f7f8f1; font-size: 15px; font-weight: 700; letter-spacing: .13em; }
.brand-light { color: #a8c4b6; font-weight: 400; }
.brand-mark { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; gap: 3px; border: 1px solid rgba(228, 239, 226, .62); border-radius: 8px; }
.brand-mark span { width: 3px; border-radius: 3px; background: #c7dbca; }
.brand-mark span:nth-child(1) { height: 8px; }.brand-mark span:nth-child(2) { height: 14px; }.brand-mark span:nth-child(3) { height: 10px; }
.story-copy { position: relative; z-index: 1; margin-top: clamp(74px, 12vh, 130px); max-width: 470px; }
.eyebrow { color: #829d90; font-size: 10px; font-weight: 600; letter-spacing: .16em; }
.story-copy h1 { margin-top: 22px; color: #f4f5ef; font-size: clamp(34px, 4vw, 50px); line-height: 1.36; letter-spacing: -.045em; }
.story-description { max-width: 340px; margin-top: 20px; color: #b1c2b8; font-size: 14px; line-height: 1.9; }
.story-art { position: absolute; width: min(500px, 92%); aspect-ratio: 1; right: 0; bottom: 6%; opacity: .9; transition: opacity .6s ease; }
.story-art--warping { opacity: 1; }
.galaxy-camera { position: absolute; inset: 0; transform-origin: center; will-change: transform; }
.galaxy-haze { position: absolute; inset: 2%; border-radius: 50%; background: radial-gradient(circle, rgba(135, 189, 170, .14) 0 23%, transparent 62%); filter: blur(12px); }
.galaxy-stars { position: absolute; inset: 0; border-radius: 50%; opacity: .8; background-image: radial-gradient(circle at 12% 25%, rgba(240, 248, 226, .9) 0 1px, transparent 1.8px), radial-gradient(circle at 78% 24%, rgba(240, 248, 226, .8) 0 1px, transparent 1.8px), radial-gradient(circle at 27% 78%, rgba(240, 248, 226, .7) 0 1.2px, transparent 2px), radial-gradient(circle at 90% 68%, rgba(240, 248, 226, .6) 0 1px, transparent 1.8px); }
.galaxy-stars--far { transform: scale(.84); opacity: .42; animation: star-drift 22s linear infinite; }
.galaxy-stars--near { transform: scale(1.13); opacity: .68; animation: star-drift 14s linear infinite reverse; }
.galaxy-sphere { position: absolute; top: 50%; left: 50%; width: 184px; height: 184px; transform: translate(-50%, -50%); border-radius: 50%; box-shadow: 0 0 0 16px rgba(184, 225, 191, .05), 0 0 56px 16px rgba(107, 190, 148, .2); animation: sphere-pulse 7s ease-in-out infinite; }
.sphere-surface { position: absolute; inset: 0; overflow: hidden; border: 1px solid rgba(216, 242, 216, .68); border-radius: 50%; background: radial-gradient(circle at 32% 22%, rgba(229, 250, 218, .68), transparent 19%), radial-gradient(circle at 63% 70%, rgba(25, 119, 92, .95), transparent 57%), linear-gradient(145deg, #9cc89f 0%, #397b65 48%, #133b36 100%); box-shadow: inset -24px -22px 42px rgba(7, 26, 26, .57), inset 16px 13px 28px rgba(223, 245, 216, .18); }
.sphere-surface::before, .sphere-surface::after { position: absolute; content: ''; border: 1px solid rgba(196, 234, 202, .16); border-radius: 50%; }
.sphere-surface::before { inset: 22% -12%; transform: rotate(-18deg); }.sphere-surface::after { inset: -10% 24%; transform: rotate(34deg); }
.sphere-glow { position: absolute; inset: -8px; border-radius: 50%; background: radial-gradient(circle, transparent 56%, rgba(170, 229, 173, .17) 70%, transparent 72%); animation: glow-pulse 4s ease-in-out infinite; }
.sphere-line { position: absolute; z-index: 2; top: 50%; left: 50%; border: 1px solid rgba(226, 246, 223, .2); border-radius: 50%; transform: translate(-50%, -50%); }
.sphere-line--one { width: 136px; height: 44px; transform: translate(-50%, -50%) rotate(26deg); }.sphere-line--two { width: 82px; height: 148px; transform: translate(-50%, -50%) rotate(-25deg); }.sphere-line--three { width: 150px; height: 92px; transform: translate(-50%, -50%) rotate(-62deg); }
.planet-orbit { position: absolute; top: 50%; left: 50%; border: 1px solid rgba(190, 215, 197, .24); border-radius: 50%; pointer-events: none; transform-origin: center; }
.planet-orbit--student { width: 250px; height: 250px; margin: -125px; border-color: rgba(190, 215, 197, .24); animation: orbit-spin-student 16s linear infinite; }
.planet-orbit--teacher { width: 330px; height: 330px; margin: -165px; border-color: rgba(190, 215, 197, .18); animation: orbit-spin-teacher 23s linear infinite; }
.planet-orbit--admin { width: 410px; height: 410px; margin: -205px; border-color: rgba(190, 215, 197, .14); animation: orbit-spin-admin 31s linear infinite; }
.role-planet { position: absolute; z-index: 4; top: -23px; left: 50%; width: 46px; height: 46px; margin-left: -23px; border-radius: 50%; transition: transform .7s cubic-bezier(.16, 1, .3, 1), opacity .7s ease; }
.role-planet::before { position: absolute; inset: 0; content: ''; border-radius: 50%; background: radial-gradient(circle at 32% 25%, #f2e8bc 0 7%, transparent 8%), radial-gradient(circle at 60% 60%, rgba(15, 43, 52, .7) 0 16%, transparent 17%), linear-gradient(145deg, #d0d485, #456e5e 58%, #163a39); box-shadow: inset -10px -8px 13px rgba(4, 22, 24, .45), 0 0 0 1px rgba(218, 241, 212, .45); }
.role-planet--teacher::before { background: radial-gradient(circle at 35% 28%, #ffe2a9 0 7%, transparent 8%), linear-gradient(145deg, #a2d2bd, #28756d 52%, #193e4a); }
.role-planet--admin::before { background: radial-gradient(circle at 35% 25%, #ffe4ad 0 7%, transparent 8%), linear-gradient(145deg, #d9a96e, #7a4f45 52%, #2c2b49); }
.story-art--warping .role-planet { opacity: .16; transform: scale(.66); }
.story-art--student .role-planet--student, .story-art--teacher .role-planet--teacher, .story-art--admin .role-planet--admin { opacity: 1; transform: scale(2.25); }
.warp-caption { position: absolute; z-index: 8; left: 50%; bottom: 4%; display: grid; gap: 5px; width: max-content; transform: translateX(-50%); text-align: center; text-shadow: 0 1px 18px rgba(4, 21, 20, .8); animation: caption-in .45s var(--ease-out) both; }
.warp-caption span { color: #a9c9b1; font-family: var(--ff-mono); font-size: 9px; letter-spacing: .14em; }.warp-caption strong { color: #eff7e9; font-size: 15px; font-weight: 600; letter-spacing: -.02em; }
.warp-cover { position: fixed; z-index: 100; inset: 0; pointer-events: none; clip-path: circle(0 at 50% 50%); transition: clip-path 680ms cubic-bezier(.16, 1, .3, 1); }
.warp-cover--student { background: radial-gradient(circle at 32% 24%, #f2e8bc 0 7%, transparent 17%), radial-gradient(circle at 66% 68%, rgba(15, 43, 52, .78) 0 14%, transparent 38%), linear-gradient(145deg, #d0d485 0%, #456e5e 57%, #163a39 100%); }
.warp-cover--teacher { background: radial-gradient(circle at 35% 27%, #ffe2a9 0 7%, transparent 17%), radial-gradient(circle at 65% 68%, rgba(25, 62, 74, .72) 0 17%, transparent 42%), linear-gradient(145deg, #a2d2bd 0%, #28756d 54%, #193e4a 100%); }
.warp-cover--admin { background: radial-gradient(circle at 35% 24%, #ffe4ad 0 7%, transparent 17%), radial-gradient(circle at 65% 70%, rgba(44, 43, 73, .76) 0 16%, transparent 42%), linear-gradient(145deg, #d9a96e 0%, #7a4f45 54%, #2c2b49 100%); }
.story-footer { position: relative; z-index: 1; margin-top: auto; color: #81988b; font-size: 10px; letter-spacing: .08em; }.story-footer span { margin: 0 6px; color: #b7cbb9; }
.login-panel { display: flex; flex-direction: column; min-height: 100dvh; padding: 38px clamp(36px, 6vw, 88px) 28px; }
.login-panel__top { display: flex; justify-content: space-between; color: var(--c-fg-1); font-size: 12px; }.secure-note { display: inline-flex; align-items: center; gap: 7px; color: var(--c-fg-2); font-size: 11px; }.secure-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--c-ok); }
.login-form-wrap { width: 100%; max-width: 380px; margin: auto; padding: 48px 0; }.form-heading .eyebrow { color: var(--c-accent); }.form-heading h2 { margin-top: 14px; font-size: 30px; letter-spacing: -.04em; }.form-heading > p:last-child { margin-top: 10px; color: var(--c-fg-1); font-size: 13px; }
.login-form { display: flex; flex-direction: column; margin-top: 36px; }.login-form label { margin: 0 0 9px; color: #45453f; font-size: 12px; font-weight: 600; }.login-form label:not(:first-child) { margin-top: 22px; }
.input-wrap { display: flex; align-items: center; gap: 12px; height: 48px; padding: 0 14px; border: 1px solid var(--c-line-2); border-radius: 5px; background: #fff; transition: border-color var(--dur-fast), box-shadow var(--dur-fast); }.input-wrap:focus-within { border-color: var(--c-accent); box-shadow: 0 0 0 3px var(--c-accent-soft); }.input-wrap svg { width: 17px; height: 17px; fill: none; stroke: #92928a; stroke-linecap: round; stroke-linejoin: round; stroke-width: 1.4; }.input-wrap input { width: 100%; height: 100%; border: 0; outline: none; color: var(--c-fg-0); background: transparent; font-size: 13px; }.input-wrap input::placeholder { color: #b1b0a9; }
.form-error { margin-top: 12px; color: var(--c-bad); font-size: 12px; }.submit-button { display: flex; justify-content: center; align-items: center; gap: 12px; height: 48px; margin-top: 27px; border-radius: 5px; color: #fff; background: #12675f; font-size: 13px; font-weight: 600; transition: background var(--dur-fast), transform var(--dur-fast); }.submit-button:hover:not(:disabled) { background: #0d5c55; }.submit-button:active:not(:disabled) { transform: translateY(1px); }.submit-button:disabled { cursor: wait; opacity: .7; }.submit-button svg { width: 17px; fill: none; stroke: currentColor; stroke-linecap: round; stroke-linejoin: round; stroke-width: 1.5; }.spinner { width: 14px; height: 14px; border: 2px solid rgba(255,255,255,.35); border-top-color: white; border-radius: 50%; animation: spin .7s linear infinite; }
.access-note { display: flex; align-items: flex-start; gap: 10px; margin-top: 24px; padding: 13px 14px; border: 1px solid #efeee8; border-radius: 5px; background: #faf9f6; }.access-note__icon { display: grid; flex: 0 0 auto; width: 16px; height: 16px; place-items: center; border: 1px solid #aaa99f; border-radius: 50%; color: #77766e; font-family: Georgia, serif; font-size: 11px; font-style: italic; }.access-note p { color: var(--c-fg-1); font-size: 11px; line-height: 1.65; }
.login-footer { display: flex; justify-content: space-between; color: var(--c-fg-2); font-size: 10px; letter-spacing: .04em; }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes star-drift { from { transform: rotate(0deg) scale(.84); } to { transform: rotate(360deg) scale(.84); } }
@keyframes orbit-spin-student { from { transform: rotate(-20deg); } to { transform: rotate(340deg); } }
@keyframes orbit-spin-teacher { from { transform: rotate(90deg); } to { transform: rotate(450deg); } }
@keyframes orbit-spin-admin { from { transform: rotate(180deg); } to { transform: rotate(540deg); } }
@keyframes sphere-pulse { 0%, 100% { transform: translate(-50%, -50%) scale(1); } 50% { transform: translate(-50%, -50%) scale(1.03); } }
@keyframes glow-pulse { 0%, 100% { opacity: .58; transform: scale(.96); } 50% { opacity: 1; transform: scale(1.04); } }
@keyframes caption-in { from { opacity: 0; transform: translate(-50%, 8px); } to { opacity: 1; transform: translate(-50%, 0); } }
@media (prefers-reduced-motion: reduce) { .galaxy-stars, .galaxy-sphere, .sphere-glow, .planet-orbit { animation: none; }.story-art, .galaxy-camera { transition: none; }.warp-caption { animation: none; } }
@media (max-width: 920px) { .login-page { grid-template-columns: minmax(300px, .85fr) minmax(380px, 1.15fr); }.login-story { padding-right: 32px; padding-left: 38px; }.story-art { right: -18%; opacity: .65; }.story-copy h1 { font-size: 36px; }.login-panel { padding-right: 38px; padding-left: 38px; } }
@media (max-width: 680px) { .login-page { display: block; background: var(--c-bg-1); }.login-story { min-height: 0; height: 210px; padding: 24px; }.story-copy { position: relative; z-index: 6; margin-top: 30px; }.story-copy .eyebrow, .story-description, .story-footer { display: none; }.story-art { z-index: 2; top: 18px; right: -52px; bottom: auto; width: 260px; opacity: .56; }.story-art--warping { opacity: .96; }.galaxy-sphere { width: 132px; height: 132px; }.planet-orbit--student { width: 170px; height: 170px; margin: -85px; }.planet-orbit--teacher { width: 220px; height: 220px; margin: -110px; }.planet-orbit--admin { width: 268px; height: 268px; margin: -134px; }.role-planet { width: 38px; height: 38px; top: -19px; margin-left: -19px; }.story-copy h1 { margin: 0; font-size: 25px; line-height: 1.35; }.login-panel { min-height: calc(100dvh - 210px); padding: 20px 24px 22px; }.login-panel__top { display: none; }.login-form-wrap { max-width: 420px; padding: 42px 0; }.form-heading h2 { font-size: 27px; }.login-footer { font-size: 9px; }.warp-caption { bottom: -10%; transform: translateX(-50%) scale(.85); } }
</style>
