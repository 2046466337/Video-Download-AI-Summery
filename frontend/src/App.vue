<script setup lang="ts">
import { AlertCircle } from 'lucide-vue-next'
import { nextTick, watch } from 'vue'
import AppFooter from './components/AppFooter.vue'
import AppHeader from './components/AppHeader.vue'
import FeatureSection from './components/FeatureSection.vue'
import HeroSearch from './components/HeroSearch.vue'
import HowItWorks from './components/HowItWorks.vue'
import ProSection from './components/ProSection.vue'
import SummaryCard from './components/SummaryCard.vue'
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
  summary,
  errorMessage: summaryError,
  chatMessages,
  chatInput,
  asking,
  startSummary,
  ask,
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

      <div class="mx-auto max-w-3xl space-y-4 px-4 pt-6 sm:px-6">
        <p
          v-if="errorMessage"
          role="alert"
          class="animate-rise flex items-start gap-2 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-600"
        >
          <AlertCircle class="mt-0.5 size-4 shrink-0" />
          <span>{{ errorMessage }}</span>
        </p>

        <div id="result" class="scroll-mt-24">
          <VideoResult
            v-if="video"
            v-model:selected="selectedOptionId"
            :video="video"
            @download="startDownload()"
            @summarize="onSummarize"
          />
        </div>

        <div id="summary" class="scroll-mt-24">
          <p
            v-if="summaryError"
            role="alert"
            class="animate-rise flex items-start gap-2 rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-600"
          >
            <AlertCircle class="mt-0.5 size-4 shrink-0" />
            <span>{{ summaryError }}</span>
          </p>
          <SummaryCard
            v-if="summary"
            v-model:chatInput="chatInput"
            :summary="summary"
            :chat-messages="chatMessages"
            :asking="asking"
            :video-url="video?.url || ''"
            @ask="ask"
          />
        </div>

        <div id="tasks" class="scroll-mt-24">
          <TaskList :tasks="tasks" @save="saveToDevice" @remove="removeTask" />
        </div>
      </div>

      <div class="mx-auto mt-16 max-w-3xl space-y-14 px-4 sm:px-6">
        <HowItWorks />
        <FeatureSection />
        <ProSection />
      </div>
    </main>

    <AppFooter />
  </div>
</template>
