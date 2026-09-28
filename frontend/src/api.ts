import type {
  AuthResponse,
  CheckoutResponse,
  MembershipState,
  SummaryState,
  TaskState,
  User,
  VideoInfo,
} from './types'

export class ApiError extends Error {}

// 抖音解析走真实浏览器打开页面，最慢可达 80 秒左右，单独给足超时；
// 其余接口（下载、统计、创建总结等）秒级返回，用较短超时即可。
const DEFAULT_TIMEOUT = 30_000
const PARSE_TIMEOUT = 90_000

async function request<T>(
  path: string,
  body?: unknown,
  timeout = DEFAULT_TIMEOUT,
  token?: string,
): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeout)

  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers['Authorization'] = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(path, {
      method: body === undefined ? 'GET' : 'POST',
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    })
  } catch (e) {
    if (controller.signal.aborted) {
      throw new ApiError('请求超时，请稍后重试')
    }
    throw new ApiError('网络连接失败，请检查服务是否已启动')
  } finally {
    window.clearTimeout(timer)
  }

  if (!response.ok) {
    // FastAPI 的业务异常统一放在 detail 里，直接透传给用户
    const payload = await response.json().catch(() => null)
    const detail = payload?.detail
    throw new ApiError(typeof detail === 'string' ? detail : '请求失败，请稍后重试')
  }

  return (await response.json()) as T
}

export interface CreateDownloadPayload {
  url: string
  option_id: string
  title: string
  quality: string
  platform: string
  client_id: string
  expected_size: number
}

export interface SummaryPayload {
  url: string
  title: string
  platform: string
  client_id: string
}

// 解析/下载/总结均「可选登录」：已登录则带 token，后端按用户识别会员与额度；
// 未登录则只带 client_id，按匿名客户端计额度。
export const parseVideo = (url: string, clientId: string, token?: string) =>
  request<VideoInfo>('/api/parse', { url, client_id: clientId }, PARSE_TIMEOUT, token)

export const createDownload = (payload: CreateDownloadPayload, token?: string) =>
  request<TaskState>('/api/downloads', payload, DEFAULT_TIMEOUT, token)

export const fetchTask = (id: string) => request<TaskState>(`/api/downloads/${id}`)

export const fetchStats = () => request<{ total_downloads: number }>('/api/stats')

// ---------------- AI 视频总结 ----------------

export const createSummary = (payload: SummaryPayload, token?: string) =>
  request<SummaryState>('/api/summaries', payload, DEFAULT_TIMEOUT, token)

export const fetchSummary = (id: string) => request<SummaryState>(`/api/summaries/${id}`)

export const askSummary = (id: string, message: string) =>
  request<{ answer: string }>(`/api/summaries/${id}/chat`, { message })

// ---------------- 用户与会员 ----------------

export const register = (payload: { email: string; password: string }) =>
  request<AuthResponse>('/api/auth/register', payload)

export const login = (payload: { email: string; password: string }) =>
  request<AuthResponse>('/api/auth/login', payload)

export const fetchMe = (token: string) =>
  request<User>('/api/auth/me', undefined, DEFAULT_TIMEOUT, token)

export const createCheckout = (token: string) =>
  request<CheckoutResponse>('/api/payments/checkout', {}, DEFAULT_TIMEOUT, token)

export const fetchMembership = (token: string) =>
  request<MembershipState>('/api/membership', undefined, DEFAULT_TIMEOUT, token)

export const completeMockPayment = (token: string) =>
  request<MembershipState>('/api/payments/mock/complete', {}, DEFAULT_TIMEOUT, token)
