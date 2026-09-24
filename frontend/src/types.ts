export interface QualityOption {
  id: string
  label: string
  note: string
  kind: 'video' | 'audio'
  height: number | null
  ext: string
  filesize: number | null
  filesize_text: string
  needs_merge: boolean
  recommended: boolean
}

export interface VideoInfo {
  url: string
  title: string
  thumbnail: string | null
  duration: number | null
  duration_text: string
  uploader: string
  platform: string
  view_count: number | null
  options: QualityOption[]
  /** 解析成功后后端自动触发的 AI 总结任务 id；为空表示未触发 */
  summary_task_id?: string
}

export type TaskStatus = 'queued' | 'running' | 'success' | 'failed'

export interface TaskState {
  id: string
  status: TaskStatus
  stage: string
  progress: number
  title: string
  quality: string
  speed_text: string
  eta_text: string
  downloaded_text: string
  total_text: string
  filename: string
  filesize_text: string
  download_url: string
  error: string
}

// ---------------- AI 视频总结 ----------------

export type SummaryStatus = 'queued' | 'running' | 'success' | 'failed'

export interface Chapter {
  start: number
  end: number
  title: string
  summary: string
}

export interface MindMapNode {
  topic: string
  children: MindMapNode[]
}

export interface SummaryResult {
  summary: string
  key_points: string[]
  chapters: Chapter[]
  mindmap: MindMapNode
}

export interface SummaryState {
  id: string
  status: SummaryStatus
  stage: string
  progress: number
  title: string
  platform: string
  error: string
  result: SummaryResult | null
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}
