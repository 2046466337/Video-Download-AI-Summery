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
