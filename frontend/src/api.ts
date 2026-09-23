import type { TaskState, VideoInfo } from './types'

export class ApiError extends Error {}

async function request<T>(path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('网络连接失败，请检查服务是否已启动')
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
  expected_size: number
}

export const parseVideo = (url: string) => request<VideoInfo>('/api/parse', { url })

export const createDownload = (payload: CreateDownloadPayload) =>
  request<TaskState>('/api/downloads', payload)

export const fetchTask = (id: string) => request<TaskState>(`/api/downloads/${id}`)

export const fetchStats = () => request<{ total_downloads: number }>('/api/stats')
