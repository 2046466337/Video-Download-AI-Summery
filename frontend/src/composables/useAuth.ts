import { computed, ref } from 'vue'
import { ApiError, fetchMe, login as apiLogin, register as apiRegister } from '../api'
import type { User } from '../types'

// 模块级单例状态：多个组件共享同一份登录态，无需跨层传递 props
const TOKEN_KEY = 'vd_token'
const USER_KEY = 'vd_user'
const CLIENT_KEY = 'vd_client_id'

function readStoredUser(): User | null {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

// 匿名客户端标识：持久化到 localStorage，用于未登录时的免费额度计数
function ensureClientId(): string {
  let id = localStorage.getItem(CLIENT_KEY)
  if (!id) {
    id =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`
    localStorage.setItem(CLIENT_KEY, id)
  }
  return id
}

const token = ref(localStorage.getItem(TOKEN_KEY) || '')
const user = ref<User | null>(readStoredUser())
const clientId = ref(ensureClientId())
const loading = ref(false)
const error = ref('')
const showAuthModal = ref(false)

const isLoggedIn = computed(() => !!token.value && !!user.value)

function persist(res: { token: string; user: User }) {
  token.value = res.token
  user.value = res.user
  localStorage.setItem(TOKEN_KEY, res.token)
  localStorage.setItem(USER_KEY, JSON.stringify(res.user))
}

async function login(email: string, password: string): Promise<boolean> {
  loading.value = true
  error.value = ''
  try {
    const res = await apiLogin({ email, password })
    persist(res)
    showAuthModal.value = false
    return true
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '登录失败，请稍后重试'
    return false
  } finally {
    loading.value = false
  }
}

async function register(email: string, password: string): Promise<boolean> {
  loading.value = true
  error.value = ''
  try {
    const res = await apiRegister({ email, password })
    persist(res)
    showAuthModal.value = false
    return true
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '注册失败，请稍后重试'
    return false
  } finally {
    loading.value = false
  }
}

function logout() {
  token.value = ''
  user.value = null
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

async function init() {
  if (!token.value) return
  try {
    const me = await fetchMe(token.value)
    user.value = me
    localStorage.setItem(USER_KEY, JSON.stringify(me))
  } catch {
    logout()
  }
}

function openAuth() {
  error.value = ''
  showAuthModal.value = true
}

function closeAuth() {
  showAuthModal.value = false
  error.value = ''
}

function clearError() {
  error.value = ''
}

export function useAuth() {
  return {
    token,
    user,
    clientId,
    isLoggedIn,
    loading,
    error,
    showAuthModal,
    login,
    register,
    logout,
    init,
    openAuth,
    closeAuth,
    clearError,
  }
}
