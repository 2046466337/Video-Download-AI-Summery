<script setup lang="ts">
import { AlertCircle } from 'lucide-vue-next'
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import AppFooter from './components/AppFooter.vue'
import AppHeader from './components/AppHeader.vue'
import AuthModal from './components/AuthModal.vue'
import FeatureSection from './components/FeatureSection.vue'
import HeroSearch from './components/HeroSearch.vue'
import HowItWorks from './components/HowItWorks.vue'
import ProSection from './components/ProSection.vue'
import SummaryPanel from './components/SummaryPanel.vue'
import TaskList from './components/TaskList.vue'
import VideoResult from './components/VideoResult.vue'
import { useAuth } from './composables/useAuth'
import { useDownloader } from './composables/useDownloader'
import { useMembership } from './composables/useMembership'
import { useSummarizer } from './composables/useSummarizer'

const { isLoggedIn, init: initAuth } = useAuth()
const { isPro, load: loadMembership } = useMembership()

const {
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
} = useDownloader()

const {
  activeTab,
  tabStatus,
  errorMessage: summaryError,
  summaryText,
  keyPoints,
  transcript,
  chapters,
  mindmapMarkdown,
  chatMessages,
  chatInput,
  asking,
  startSummary,
  startFromTaskId,
  selectTab,
  ask,
  downloadSubtitles,
  reset: resetSummary,
} = useSummarizer()

function onSummarize() {
  if (!video.value) return
  startSummary(video.value)
  nextTick(() => {
    document.getElementById('summary')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

watch(video, async (info) => {
  resetSummary()
  if (!info) return
  // 解析成功后，后端已自动触发 AI 总结任务，前端直接进入总结流式展示（沿用现有逻辑）
  if (info.summary_task_id) {
    startFromTaskId(info.summary_task_id)
  }
  await nextTick()
  document.getElementById('result')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
})

watch(
  () => tasks.length,
  async (count, previous) => {
    if (count <= (previous ?? 0)) return
    await nextTick()
    document.getElementById('tasks')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  },
)

// ---------------- 登录态与会员 ----------------
const paymentBanner = ref('')
let bannerTimer: number | undefined

// 显示支付结果横幅，几秒后自动消失，避免一直挡在页面顶部
function showPaymentBanner(message: string) {
  paymentBanner.value = message
  if (bannerTimer !== undefined) window.clearTimeout(bannerTimer)
  bannerTimer = window.setTimeout(() => {
    paymentBanner.value = ''
  }, 3000)
}

watch(isLoggedIn, () => {
  loadMembership()
})

onMounted(async () => {
  await initAuth()
  await loadMembership()

  // 真实 Stripe 支付跳回后的处理：轮询等待 webhook 落库
  const params = new URLSearchParams(window.location.search)
  const paymentResult = params.get('payment')
  if (paymentResult === 'success') {
    showPaymentBanner('支付成功，正在为你开通会员…')
    for (let i = 0; i < 10; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1500))
      await loadMembership()
      if (isPro.value) {
        showPaymentBanner('Pro 会员已开通，感谢支持！')
        break
      }
    }
  } else if (paymentResult === 'cancel') {
    showPaymentBanner('已取消支付')
  }
  // 清理 query，避免刷新时重复提示
  if (window.location.search) {
    window.history.replaceState(null, '', window.location.pathname)
  }
})

onUnmounted(() => {
  if (bannerTimer !== undefined) window.clearTimeout(bannerTimer)
})
</script>

<template>
  <div id="top" class="min-h-screen">
    <AppHeader />

    <main>
      <!-- 支付结果横幅 -->
      <div v-if="paymentBanner" class="mx-auto max-w-7xl px-4 sm:px-6">
        <p
          role="status"
          class="animate-rise my-4 flex items-start gap-2 rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700"
        >
          <AlertCircle class="mt-0.5 size-4 shrink-0" />
          <span>{{ paymentBanner }}</span>
        </p>
      </div>

      <HeroSearch
        v-model="url"
        :parsing="parsing"
        :total-downloads="totalDownloads"
        @parse="parse"
      />

      <!-- 解析/下载错误提示：独立于结果区，解析失败（video 为空）时也必须可见 -->
      <div v-if="errorMessage" class="mx-auto max-w-7xl px-4 sm:px-6">
        <p
          role="alert"
          class="animate-rise my-4 flex items-start gap-2 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-600"
        >
          <AlertCircle class="mt-0.5 size-4 shrink-0" />
          <span>{{ errorMessage }}</span>
        </p>
      </div>

      <!-- 视频解析后的左右分栏：桌面 4:6 并排，移动端上下流式 -->
      <div v-if="video" class="mx-auto max-w-7xl px-4 pt-6 sm:px-6">
        <div class="grid grid-cols-1 gap-4 lg:grid-cols-10">
          <!-- 左栏：视频预览卡片（4/10） -->
          <div id="result" class="scroll-mt-24 lg:col-span-4">
            <VideoResult
              v-model:selected="selectedOptionId"
              :video="video"
              @download="startDownload()"
              @summarize="onSummarize"
            />
          </div>

          <!-- 右栏：Tab 面板（6/10） -->
          <div id="summary" class="flex scroll-mt-24 flex-col lg:col-span-6">
            <!-- 自动总结因免费额度用尽未触发时的提示 -->
            <p
              v-if="video.summary_quota_message"
              role="status"
              class="animate-rise mb-4 flex items-start gap-2 rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-700"
            >
              <AlertCircle class="mt-0.5 size-4 shrink-0" />
              <span>{{ video.summary_quota_message }}</span>
            </p>
            <p
              v-if="summaryError"
              role="alert"
              class="animate-rise mb-4 flex items-start gap-2 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-600"
            >
              <AlertCircle class="mt-0.5 size-4 shrink-0" />
              <span>{{ summaryError }}</span>
            </p>
            <SummaryPanel
              v-model:chat-input="chatInput"
              :active-tab="activeTab"
              :tab-status="tabStatus"
              :summary-text="summaryText"
              :key-points="keyPoints"
              :transcript="transcript"
              :chapters="chapters"
              :mindmap-markdown="mindmapMarkdown"
              :chat-messages="chatMessages"
              :asking="asking"
              :video-url="video.url"
              @select-tab="selectTab"
              @ask="ask"
              @download-subtitles="downloadSubtitles"
            />
          </div>
        </div>

        <div id="tasks" class="mt-4 scroll-mt-24">
          <TaskList :tasks="tasks" @save="saveToDevice" @remove="removeTask" />
        </div>

        <!-- 解析状态下也保留 Pro 对比卡片，供顶栏「Pro 会员」锚点跳转 -->
        <div class="mx-auto mt-14 max-w-3xl">
          <ProSection />
        </div>
      </div>

      <!-- 未解析时的引导内容 -->
      <div v-else class="mx-auto mt-16 max-w-3xl space-y-14 px-4 sm:px-6">
        <HowItWorks />
        <FeatureSection />
        <ProSection />
      </div>
    </main>

    <AppFooter />
    <AuthModal />
  </div>
</template>
