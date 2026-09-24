import { onUnmounted, reactive, ref } from 'vue'
import { ApiError, askSummary, createSummary, fetchSummary } from '../api'
import type { ChatMessage, SummaryState, VideoInfo } from '../types'

const POLL_INTERVAL = 1200

export function useSummarizer() {
  const summary = ref<SummaryState | null>(null)
  const errorMessage = ref('')
  const chatMessages = reactive<ChatMessage[]>([])
  const chatInput = ref('')
  const asking = ref(false)

  let timer: number | undefined

  function stopPolling() {
    if (timer !== undefined) {
      window.clearInterval(timer)
      timer = undefined
    }
  }

  function ensurePolling() {
    if (timer !== undefined) return
    timer = window.setInterval(async () => {
      const current = summary.value
      if (!current || (current.status !== 'queued' && current.status !== 'running')) {
        stopPolling()
        return
      }
      try {
        const latest = await fetchSummary(current.id)
        summary.value = latest
      } catch {
        // 单次轮询失败不打断，下一拍重试
      }
    }, POLL_INTERVAL)
  }

  async function startSummary(info: VideoInfo) {
    summary.value = null
    errorMessage.value = ''
    chatMessages.length = 0
    try {
      const task = await createSummary({
        url: info.url,
        title: info.title,
        platform: info.platform,
      })
      summary.value = task
      ensurePolling()
    } catch (error) {
      errorMessage.value =
        error instanceof ApiError ? error.message : '创建总结任务失败'
    }
  }

  async function ask() {
    const question = chatInput.value.trim()
    const current = summary.value
    if (!question || !current || asking.value) return

    chatMessages.push({ role: 'user', content: question })
    chatInput.value = ''
    asking.value = true
    try {
      const { answer } = await askSummary(current.id, question)
      chatMessages.push({ role: 'assistant', content: answer })
    } catch (error) {
      errorMessage.value =
        error instanceof ApiError ? error.message : '提问失败，请稍后重试'
    } finally {
      asking.value = false
    }
  }

  function reset() {
    stopPolling()
    summary.value = null
    errorMessage.value = ''
    chatMessages.length = 0
    chatInput.value = ''
  }

  onUnmounted(stopPolling)

  return {
    summary,
    errorMessage,
    chatMessages,
    chatInput,
    asking,
    startSummary,
    ask,
    reset,
  }
}
