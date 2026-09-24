import { computed, onUnmounted, reactive, ref } from 'vue'
import { ApiError, createSummary } from '../api'
import type { Chapter, ChatMessage, VideoInfo } from '../types'

export type TabId = 'summary' | 'subtitle' | 'mindmap' | 'chat'

export type TabStatus = 'idle' | 'loading' | 'done' | 'error'

export interface TabState {
  status: TabStatus
  error: string
}

/** 解析「[MM:SS] 标题｜说明」或「MM:SS 标题｜说明」为章节列表。 */
function parseChapters(raw: string): Chapter[] {
  const chapters: Chapter[] = []
  for (const line of raw.split('\n')) {
    const t = line.trim()
    if (!t) continue
    const m = t.match(/^\[?(\d{1,2}):(\d{2})\]?\s*(.*)$/)
    if (!m) continue
    const start = Number(m[1]) * 60 + Number(m[2])
    let title = m[3].trim()
    let summary = ''
    const idx = title.search(/[｜|]/)
    if (idx >= 0) {
      summary = title.slice(idx + 1).trim()
      title = title.slice(0, idx).trim()
    }
    if (title) chapters.push({ start, end: start, title, summary })
  }
  for (let i = 0; i < chapters.length; i++) {
    chapters[i].end = i + 1 < chapters.length ? chapters[i + 1].start : chapters[i].start
  }
  return chapters
}

export function useSummarizer() {
  const activeTab = ref<TabId>('summary')
  const tabStatus = reactive<Record<TabId, TabState>>({
    summary: { status: 'idle', error: '' },
    subtitle: { status: 'idle', error: '' },
    mindmap: { status: 'idle', error: '' },
    chat: { status: 'idle', error: '' },
  })

  const errorMessage = ref('')
  const taskId = ref('')

  // 总结摘要 Tab
  const summaryText = ref('')
  const keyPointsRaw = ref('')
  const keyPoints = computed(() =>
    keyPointsRaw.value
      .split('\n')
      .map((p) => p.replace(/^-\s*/, '').trim())
      .filter(Boolean),
  )

  // 字幕文本 Tab
  const transcript = ref('')
  const chaptersRaw = ref('')
  const chapters = computed(() => parseChapters(chaptersRaw.value))

  // 思维导图 Tab
  const mindmapMarkdown = ref('')

  // AI 问答 Tab
  const chatMessages = reactive<ChatMessage[]>([])
  const chatInput = ref('')
  const asking = ref(false)

  const controllers = new Set<AbortController>()

  function newController() {
    const controller = new AbortController()
    controllers.add(controller)
    return controller
  }

  async function consumeSSE(
    url: string,
    onEvent: (event: string, data: any) => void,
    signal?: AbortSignal,
  ) {
    const res = await fetch(url, { signal })
    if (!res.ok) {
      let detail = '请求失败，请稍后重试'
      try {
        const payload = await res.json()
        if (typeof payload?.detail === 'string') detail = payload.detail
      } catch {
        /* 非 JSON 错误体，沿用默认文案 */
      }
      throw new ApiError(detail)
    }
    if (!res.body) throw new ApiError('无法读取流式响应')

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let idx: number
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)

        let event = 'message'
        const dataLines: string[] = []
        for (const line of raw.split('\n')) {
          if (line.startsWith('event:')) event = line.slice(6).trim()
          else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
        }
        if (!dataLines.length) continue

        let data: any = {}
        try {
          data = JSON.parse(dataLines.join('\n'))
        } catch {
          data = {}
        }
        onEvent(event, data)
      }
    }
  }

  function streamUrl(module: TabId, question = '') {
    const params = new URLSearchParams({ module })
    if (question) params.set('question', question)
    return `/api/summaries/${taskId.value}/stream?${params.toString()}`
  }

  function applyDelta(tab: TabId, phase: string, content: string) {
    if (tab === 'summary') {
      if (phase === 'summary') summaryText.value += content
      else if (phase === 'points') keyPointsRaw.value += content
    } else if (tab === 'subtitle') {
      if (phase === 'transcript') transcript.value += content
      else if (phase === 'chapters') chaptersRaw.value += content
    } else if (tab === 'mindmap') {
      mindmapMarkdown.value += content
    }
  }

  async function loadTab(tab: TabId) {
    const state = tabStatus[tab]
    if (state.status === 'loading' || state.status === 'done') return
    state.status = 'loading'
    state.error = ''

    const controller = newController()
    let phase = ''

    try {
      await consumeSSE(
        streamUrl(tab),
        (event, data) => {
          if (event === 'phase') {
            phase = data.phase || ''
          } else if (event === 'delta') {
            applyDelta(tab, phase, data.content || '')
          } else if (event === 'error') {
            state.error = data.message || '加载失败'
          }
        },
        controller.signal,
      )
      state.status = 'done'
    } catch (e) {
      if (controller.signal.aborted) return
      state.status = 'error'
      state.error = e instanceof ApiError ? e.message : '加载失败，请稍后重试'
    } finally {
      controllers.delete(controller)
    }
  }

  async function startSummary(info: VideoInfo) {
    reset()
    try {
      const task = await createSummary({
        url: info.url,
        title: info.title,
        platform: info.platform,
      })
      taskId.value = task.id
      activeTab.value = 'summary'
      // 自动加载链：先摘要，完成后自动预加载字幕；单个失败也继续下一个
      loadTab('summary').finally(() => loadTab('subtitle'))
    } catch (error) {
      errorMessage.value =
        error instanceof ApiError ? error.message : '创建总结任务失败'
    }
  }

  function selectTab(tab: TabId) {
    activeTab.value = tab
    // AI 问答需用户输入问题后才发起请求，这里只激活输入界面
    if (tab === 'chat') return
    // 尚未开始加载的 Tab 在首次点击时按需加载（已加载/加载中的直接展示）
    if (tabStatus[tab].status === 'idle') {
      loadTab(tab)
    }
  }

  async function ask() {
    const question = chatInput.value.trim()
    if (!question || asking.value || !taskId.value) return

    chatInput.value = ''
    asking.value = true
    tabStatus.chat.status = 'loading'
    tabStatus.chat.error = ''

    chatMessages.push({ role: 'user', content: question })
    chatMessages.push({ role: 'assistant', content: '' })
    const lastIdx = chatMessages.length - 1

    const controller = newController()
    try {
      await consumeSSE(
        streamUrl('chat', question),
        (event, data) => {
          if (event === 'delta') {
            chatMessages[lastIdx].content += data.content || ''
          } else if (event === 'error') {
            chatMessages[lastIdx].content = data.message || '回答失败'
          }
        },
        controller.signal,
      )
      tabStatus.chat.status = 'done'
    } catch (e) {
      if (controller.signal.aborted) return
      const msg = e instanceof ApiError ? e.message : '提问失败，请稍后重试'
      if (!chatMessages[lastIdx].content) chatMessages[lastIdx].content = msg
      tabStatus.chat.status = 'error'
      tabStatus.chat.error = msg
    } finally {
      asking.value = false
      controllers.delete(controller)
    }
  }

  function reset() {
    for (const controller of controllers) controller.abort()
    controllers.clear()

    taskId.value = ''
    errorMessage.value = ''
    activeTab.value = 'summary'

    summaryText.value = ''
    keyPointsRaw.value = ''
    transcript.value = ''
    chaptersRaw.value = ''
    mindmapMarkdown.value = ''

    chatMessages.length = 0
    chatInput.value = ''
    asking.value = false

    for (const key of Object.keys(tabStatus) as TabId[]) {
      tabStatus[key] = { status: 'idle', error: '' }
    }
  }

  onUnmounted(reset)

  return {
    activeTab,
    tabStatus,
    errorMessage,
    summaryText,
    keyPoints,
    transcript,
    chapters,
    mindmapMarkdown,
    chatMessages,
    chatInput,
    asking,
    startSummary,
    selectTab,
    ask,
    reset,
  }
}
