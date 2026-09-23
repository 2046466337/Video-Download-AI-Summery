import { onUnmounted, reactive, ref } from 'vue'
import { ApiError, createDownload, fetchStats, fetchTask, parseVideo } from '../api'
import type { QualityOption, TaskState, VideoInfo } from '../types'

const POLL_INTERVAL = 800

export function useDownloader() {
  const url = ref('')
  const parsing = ref(false)
  const errorMessage = ref('')
  const video = ref<VideoInfo | null>(null)
  const selectedOptionId = ref('')
  const tasks = reactive<TaskState[]>([])
  const totalDownloads = ref(0)

  let timer: number | undefined

  const selectedOption = () =>
    video.value?.options.find((o) => o.id === selectedOptionId.value) ?? null

  function stopPolling() {
    if (timer !== undefined) {
      window.clearInterval(timer)
      timer = undefined
    }
  }

  function ensurePolling() {
    if (timer !== undefined) return
    timer = window.setInterval(async () => {
      const pending = tasks.filter((t) => t.status === 'queued' || t.status === 'running')
      if (pending.length === 0) {
        stopPolling()
        refreshStats()
        return
      }
      await Promise.all(
        pending.map(async (task) => {
          try {
            const latest = await fetchTask(task.id)
            Object.assign(task, latest)
          } catch {
            // 单次轮询失败不打断整体流程，下一拍会自动重试
          }
        }),
      )
    }, POLL_INTERVAL)
  }

  async function refreshStats() {
    try {
      totalDownloads.value = (await fetchStats()).total_downloads
    } catch {
      /* 统计数字属于锦上添花，失败静默 */
    }
  }

  async function parse() {
    const target = url.value.trim()
    if (!target || parsing.value) return

    parsing.value = true
    errorMessage.value = ''
    video.value = null
    try {
      const info = await parseVideo(target)
      video.value = info
      selectedOptionId.value =
        info.options.find((o) => o.recommended)?.id ?? info.options[0]?.id ?? ''
    } catch (error) {
      errorMessage.value =
        error instanceof ApiError ? error.message : '解析失败，请稍后重试'
    } finally {
      parsing.value = false
    }
  }

  async function startDownload(option?: QualityOption) {
    const info = video.value
    const target = option ?? selectedOption()
    if (!info || !target) return

    try {
      const task = await createDownload({
        url: info.url,
        option_id: target.id,
        title: info.title,
        quality: target.label,
        platform: info.platform,
        expected_size: target.filesize ?? 0,
      })
      tasks.unshift(task)
      ensurePolling()
    } catch (error) {
      errorMessage.value =
        error instanceof ApiError ? error.message : '创建下载任务失败'
    }
  }

  function saveToDevice(task: TaskState) {
    if (!task.download_url) return
    // 手机 Safari 对 JS blob 下载支持很差，交给浏览器直接跳转到带 attachment 头的地址最稳
    window.location.href = task.download_url
  }

  function removeTask(taskId: string) {
    const index = tasks.findIndex((t) => t.id === taskId)
    if (index >= 0) tasks.splice(index, 1)
  }

  function reset() {
    url.value = ''
    video.value = null
    errorMessage.value = ''
  }

  onUnmounted(stopPolling)
  refreshStats()

  return {
    url,
    parsing,
    errorMessage,
    video,
    selectedOptionId,
    tasks,
    totalDownloads,
    parse,
    startDownload,
    saveToDevice,
    removeTask,
    reset,
  }
}
