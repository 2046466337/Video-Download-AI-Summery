<script setup lang="ts">
import {
  AlertCircle,
  Brain,
  ChevronDown,
  Clock,
  Download,
  FilePen,
  FileText,
  ListChecks,
  Loader2,
  MessageCircle,
  Send,
  User,
} from 'lucide-vue-next'
import { computed, ref, type Component } from 'vue'
import type { Chapter, ChatMessage } from '../types'
import type { SubtitleFormat, TabId, TabState } from '../composables/useSummarizer'
import MarkmapView from './MarkmapView.vue'

interface TabDef {
  id: TabId
  label: string
  icon: Component
}

const TABS: TabDef[] = [
  { id: 'summary', label: '总结摘要', icon: FilePen },
  { id: 'subtitle', label: '字幕文本', icon: FileText },
  { id: 'mindmap', label: '思维导图', icon: Brain },
  { id: 'chat', label: 'AI问答', icon: MessageCircle },
]

const props = defineProps<{
  activeTab: TabId
  tabStatus: Record<TabId, TabState>
  summaryText: string
  keyPoints: string[]
  transcript: string
  chapters: Chapter[]
  mindmapMarkdown: string
  chatMessages: ChatMessage[]
  asking: boolean
  videoUrl: string
}>()

const chatInput = defineModel<string>('chatInput', { required: true })
const emit = defineEmits<{
  selectTab: [tab: TabId]
  ask: []
  downloadSubtitles: [format: SubtitleFormat]
}>()

const SUBTITLE_FORMATS: { id: SubtitleFormat; label: string }[] = [
  { id: 'srt', label: 'SRT 字幕 (.srt)' },
  { id: 'vtt', label: 'WebVTT (.vtt)' },
  { id: 'md', label: 'Markdown (.md)' },
]
const subtitleMenuOpen = ref(false)

// 仅思维导图 / AI 问答两个 Tab 需要内容区撑满，与左栏主卡片等高
const fillHeight = computed(() => props.activeTab === 'mindmap' || props.activeTab === 'chat')

function downloadSubtitle(format: SubtitleFormat) {
  subtitleMenuOpen.value = false
  emit('downloadSubtitles', format)
}

function fmtTs(seconds: number) {
  const total = Math.floor(seconds || 0)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function jumpTo(start: number) {
  try {
    const url = new URL(props.videoUrl)
    url.searchParams.set('t', String(Math.floor(start)))
    window.open(url.toString(), '_blank', 'noopener')
  } catch {
    /* 链接不可跳转时静默忽略 */
  }
}

function submitAsk() {
  if (chatInput.value.trim() && !props.asking) emit('ask')
}

const state = (tab: TabId) => props.tabStatus[tab]
</script>

<template>
  <section class="card animate-rise flex flex-col overflow-hidden" :class="fillHeight ? 'flex-1' : ''">
    <!-- Tab 标签栏 -->
    <div class="flex items-center gap-1 overflow-x-auto border-b border-slate-100 px-2 sm:px-3">
      <button
        v-for="tab in TABS"
        :key="tab.id"
        type="button"
        class="relative flex shrink-0 items-center gap-1.5 px-2.5 py-3 text-sm font-medium whitespace-nowrap transition sm:px-3"
        :class="activeTab === tab.id ? 'text-brand-600' : 'text-slate-500 hover:text-slate-800'"
        @click="emit('selectTab', tab.id)"
      >
        <component :is="tab.icon" class="size-4" />
        <span>{{ tab.label }}</span>
        <Loader2
          v-if="state(tab.id).status === 'loading'"
          class="size-3.5 animate-spin text-brand-400"
        />
        <span v-else-if="state(tab.id).status === 'error'" class="size-1.5 rounded-full bg-rose-400" />
        <span
          v-if="activeTab === tab.id"
          class="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-brand-500"
        />
      </button>
    </div>

    <!-- 内容区 -->
    <div class="p-4 sm:p-5" :class="fillHeight ? 'flex min-h-0 flex-1 flex-col' : ''">
      <!-- 总结摘要 -->
      <div v-if="activeTab === 'summary'" class="space-y-6">
        <div v-if="state('summary').status === 'idle'" class="py-10 text-center text-sm text-slate-400">
          点击「AI 总结」开始生成
        </div>

        <div v-if="state('summary').status === 'loading' && !summaryText" class="py-10 text-center">
          <Loader2 class="mx-auto size-6 animate-spin text-brand-500" />
          <p class="mt-3 text-sm text-slate-500">正在生成内容摘要…</p>
        </div>

        <div v-if="state('summary').status === 'error' && !summaryText" class="py-10 text-center">
          <AlertCircle class="mx-auto size-6 text-rose-400" />
          <p class="mt-3 text-sm text-rose-500">{{ state('summary').error }}</p>
        </div>

        <div v-if="summaryText">
          <h3 class="headline text-sm text-slate-900">内容摘要</h3>
          <p class="mt-2 text-sm leading-relaxed whitespace-pre-line text-slate-600">
            {{ summaryText }}
          </p>
        </div>

        <div v-if="keyPoints.length || state('summary').status === 'loading'">
          <h3 class="headline flex items-center gap-1.5 text-sm text-slate-900">
            <ListChecks class="size-4 text-brand-500" />核心要点
          </h3>
          <ul v-if="keyPoints.length" class="mt-2.5 space-y-2">
            <li
              v-for="(point, index) in keyPoints"
              :key="index"
              class="flex items-start gap-2 text-sm text-slate-600"
            >
              <span
                class="mt-1 grid size-4 shrink-0 place-items-center rounded-full bg-brand-50 text-[10px] font-semibold text-brand-600"
              >
                {{ index + 1 }}
              </span>
              <span class="leading-relaxed">{{ point }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- 字幕文本 -->
      <div v-else-if="activeTab === 'subtitle'" class="space-y-6">
        <div v-if="state('subtitle').status === 'idle'" class="py-10 text-center text-sm text-slate-400">
          点击「AI 总结」开始生成
        </div>

        <div v-if="state('subtitle').status === 'error' && !transcript" class="py-10 text-center">
          <AlertCircle class="mx-auto size-6 text-rose-400" />
          <p class="mt-3 text-sm text-rose-500">{{ state('subtitle').error }}</p>
        </div>

        <div v-if="transcript">
          <div class="flex items-center justify-between gap-2">
            <h3 class="headline text-sm text-slate-900">原始字幕</h3>
            <div class="relative">
              <button
                type="button"
                class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-brand-300 hover:bg-slate-50"
                @click="subtitleMenuOpen = !subtitleMenuOpen"
              >
                <Download class="size-3.5" />
                下载字幕
                <ChevronDown class="size-3.5" :class="subtitleMenuOpen ? 'rotate-180' : ''" />
              </button>
              <div
                v-if="subtitleMenuOpen"
                class="card absolute right-0 top-full z-20 mt-1 w-44 p-1 shadow-lift"
              >
                <button
                  v-for="item in SUBTITLE_FORMATS"
                  :key="item.id"
                  type="button"
                  class="flex w-full items-center rounded-lg px-3 py-2 text-left text-sm text-slate-700 transition hover:bg-slate-50"
                  @click="downloadSubtitle(item.id)"
                >
                  {{ item.label }}
                </button>
              </div>
            </div>
          </div>
          <div
            class="mt-2 max-h-72 overflow-y-auto rounded-xl bg-slate-50 p-3 text-xs leading-relaxed whitespace-pre-wrap text-slate-600"
          >
            {{ transcript }}
          </div>
        </div>

        <div v-if="chapters.length || state('subtitle').status === 'loading'">
          <h3 class="headline flex items-center gap-1.5 text-sm text-slate-900">
            <Clock class="size-4 text-brand-500" />章节大纲
          </h3>
          <div v-if="chapters.length" class="mt-2.5 space-y-1.5">
            <button
              v-for="(chapter, index) in chapters"
              :key="index"
              type="button"
              class="flex w-full items-start gap-2.5 rounded-lg px-2 py-1.5 text-left transition hover:bg-slate-50"
              @click="jumpTo(chapter.start)"
            >
              <span
                class="mt-0.5 shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium tabular-nums text-slate-500"
              >
                {{ fmtTs(chapter.start) }}
              </span>
              <span class="min-w-0 flex-1">
                <span class="block truncate text-sm font-medium text-slate-800">{{ chapter.title }}</span>
                <span v-if="chapter.summary" class="block text-xs text-slate-400">
                  {{ chapter.summary }}
                </span>
              </span>
            </button>
          </div>
          <p v-if="chapters.length" class="mt-1.5 px-2 text-[11px] text-slate-400">
            点击章节可跳转到原视频对应时间点
          </p>
        </div>
      </div>

      <!-- 思维导图 -->
      <div v-else-if="activeTab === 'mindmap'" class="flex min-h-0 flex-1 flex-col">
        <div v-if="state('mindmap').status === 'idle'" class="py-10 text-center text-sm text-slate-400">
          点击本标签生成思维导图
        </div>

        <div v-else-if="state('mindmap').status === 'loading' && !mindmapMarkdown" class="py-10 text-center">
          <Loader2 class="mx-auto size-6 animate-spin text-brand-500" />
          <p class="mt-3 text-sm text-slate-500">正在生成思维导图…</p>
        </div>

        <div v-else-if="state('mindmap').status === 'error'" class="py-10 text-center">
          <AlertCircle class="mx-auto size-6 text-rose-400" />
          <p class="mt-3 text-sm text-rose-500">{{ state('mindmap').error }}</p>
        </div>

        <div v-else-if="mindmapMarkdown" class="flex min-h-0 flex-1 flex-col">
          <MarkmapView :markdown="mindmapMarkdown" class="min-h-0 flex-1" />
        </div>
      </div>

      <!-- AI 问答 -->
      <div v-else class="flex min-h-0 flex-1 flex-col">
        <div class="min-h-40 flex-1 space-y-2 overflow-y-auto">
          <div v-if="!chatMessages.length" class="py-10 text-center text-sm text-slate-400">
            针对本视频提问，AI 将基于字幕内容回答
          </div>
          <div
            v-for="(message, index) in chatMessages"
            :key="index"
            class="flex gap-2"
            :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <div
              class="max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap"
              :class="
                message.role === 'user'
                  ? 'bg-brand-500 text-white'
                  : 'bg-slate-100 text-slate-700'
              "
            >
              {{ message.content }}
            </div>
          </div>
        </div>

        <div class="mt-3 flex items-center gap-2 border-t border-slate-100 pt-3">
          <div class="relative flex-1">
            <User class="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
            <input
              v-model="chatInput"
              type="text"
              placeholder="例如：这个视频的核心结论是什么？"
              class="w-full rounded-full border border-slate-200 bg-white py-2 pr-4 pl-9 text-sm text-slate-900 outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-500/20"
              @keyup.enter="submitAsk"
            />
          </div>
          <button
            type="button"
            :disabled="asking || !chatInput.trim()"
            class="inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-full bg-brand-500 px-4 py-2 text-sm font-semibold text-white transition hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-40"
            @click="submitAsk"
          >
            <Loader2 v-if="asking" class="size-4 animate-spin" />
            <Send v-else class="size-4" />
            发送
          </button>
        </div>
      </div>
    </div>

    <!-- 点击外部关闭字幕格式下拉 -->
    <div v-if="subtitleMenuOpen" class="fixed inset-0 z-10" @click="subtitleMenuOpen = false"></div>
  </section>
</template>
