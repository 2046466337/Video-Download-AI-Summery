<script setup lang="ts">
import { AlertCircle } from 'lucide-vue-next'
import { nextTick, watch } from 'vue'
import AppFooter from './components/AppFooter.vue'
import AppHeader from './components/AppHeader.vue'
import FeatureSection from './components/FeatureSection.vue'
import HeroSearch from './components/HeroSearch.vue'
import HowItWorks from './components/HowItWorks.vue'
import ProSection from './components/ProSection.vue'
import SummaryPanel from './components/SummaryPanel.vue'
import TaskList from './components/TaskList.vue'
import VideoResult from './components/VideoResult.vue'
import { useDownloader } from './composables/useDownloader'
import { useSummarizer } from './composables/useSummarizer'

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
</script>

<template>
  <div id="top" class="min-h-screen">
    <AppHeader />

    <main>
      <HeroSearch
        v-model="url"
        :parsing="parsing"
        :total-downloads="totalDownloads"
        @parse="parse"
      />

      <!-- 视频解析后的左右分栏：桌面 4:6 并排，移动端上下流式 -->
      <div v-if="video" class="mx-auto max-w-7xl px-4 pt-6 sm:px-6">
        <p
          v-if="errorMessage"
          role="alert"
          class="animate-rise mb-4 flex items-start gap-2 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-600"
        >
          <AlertCircle class="mt-0.5 size-4 shrink-0" />
          <span>{{ errorMessage }}</span>
        </p>

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
      </div>

      <!-- 未解析时的引导内容 -->
      <div v-else class="mx-auto mt-16 max-w-3xl space-y-14 px-4 sm:px-6">
        <HowItWorks />
        <FeatureSection />
        <ProSection />
      </div>
    </main>

    <AppFooter />
  </div>
</template>
