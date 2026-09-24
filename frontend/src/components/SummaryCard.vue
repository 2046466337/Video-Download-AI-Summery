<script setup lang="ts">
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  ListChecks,
  Loader2,
  Network,
  Send,
  Sparkles,
  User,
} from 'lucide-vue-next'
import { computed } from 'vue'
import type { ChatMessage, SummaryState } from '../types'
import MindMapTree from './MindMapTree.vue'

const props = defineProps<{
  summary: SummaryState
  chatMessages: ChatMessage[]
  asking: boolean
  videoUrl: string
}>()

const chatInput = defineModel<string>('chatInput', { required: true })
const emit = defineEmits<{ ask: [] }>()

const isRunning = computed(
  () => props.summary.status === 'queued' || props.summary.status === 'running',
)

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
</script>

<template>
  <section class="card animate-rise overflow-hidden">
    <!-- 头部 -->
    <div class="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3 sm:px-5">
      <div class="flex items-center gap-2">
        <span class="grid size-8 place-items-center rounded-lg bg-brand-50 text-brand-600">
          <Sparkles class="size-4" />
        </span>
        <div class="min-w-0">
          <p class="truncate text-sm font-semibold text-slate-900">AI 视频总结</p>
          <p class="truncate text-xs text-slate-400">{{ summary.title }}</p>
        </div>
      </div>
      <span
        v-if="summary.status === 'success'"
        class="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-600"
      >
        <CheckCircle2 class="size-3.5" />完成
      </span>
    </div>

    <!-- 加载态 -->
    <div v-if="isRunning" class="px-4 py-8 text-center sm:px-5">
      <Loader2 class="mx-auto size-6 animate-spin text-brand-500" />
      <p class="mt-3 text-sm font-medium text-slate-700">{{ summary.stage }}</p>
      <div class="mx-auto mt-4 h-1.5 max-w-xs overflow-hidden rounded-full bg-slate-100">
        <div
          class="h-full rounded-full bg-gradient-to-r from-brand-400 to-brand-600 transition-[width] duration-500"
          :style="{ width: `${summary.progress}%` }"
        />
      </div>
      <p class="mt-2 text-xs text-slate-400">正在提取字幕并生成总结，请稍候…</p>
    </div>

    <!-- 失败态 -->
    <div v-else-if="summary.status === 'failed'" class="px-4 py-8 text-center sm:px-5">
      <AlertCircle class="mx-auto size-6 text-rose-400" />
      <p class="mt-3 text-sm text-rose-500">{{ summary.error }}</p>
    </div>

    <!-- 成功态 -->
    <div v-else-if="summary.result" class="space-y-6 px-4 py-5 sm:px-5">
      <!-- 摘要 -->
      <div>
        <h3 class="headline text-sm text-slate-900">内容摘要</h3>
        <p class="mt-2 text-sm leading-relaxed whitespace-pre-line text-slate-600">
          {{ summary.result.summary }}
        </p>
      </div>

      <!-- 核心要点 -->
      <div v-if="summary.result.key_points.length">
        <h3 class="headline flex items-center gap-1.5 text-sm text-slate-900">
          <ListChecks class="size-4 text-brand-500" />核心要点
        </h3>
        <ul class="mt-2.5 space-y-2">
          <li
            v-for="(point, index) in summary.result.key_points"
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

      <!-- 章节 -->
      <div v-if="summary.result.chapters.length">
        <h3 class="headline flex items-center gap-1.5 text-sm text-slate-900">
          <Clock class="size-4 text-brand-500" />章节大纲
        </h3>
        <div class="mt-2.5 space-y-1.5">
          <button
            v-for="(chapter, index) in summary.result.chapters"
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
        <p class="mt-1.5 px-2 text-[11px] text-slate-400">点击章节可跳转到原视频对应时间点</p>
      </div>

      <!-- 思维导图 -->
      <div v-if="summary.result.mindmap?.topic">
        <h3 class="headline flex items-center gap-1.5 text-sm text-slate-900">
          <Network class="size-4 text-brand-500" />思维导图
        </h3>
        <div class="mt-2.5 rounded-xl bg-slate-50 p-3">
          <div class="rounded-lg bg-white p-2.5">
            <p class="text-sm font-semibold text-slate-900">{{ summary.result.mindmap.topic }}</p>
            <div v-if="summary.result.mindmap.children?.length" class="mt-2 space-y-1.5">
              <MindMapTree
                v-for="(child, index) in summary.result.mindmap.children"
                :key="index"
                :node="child"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- AI 追问 -->
      <div>
        <h3 class="headline text-sm text-slate-900">针对本视频提问</h3>
        <div v-if="chatMessages.length" class="mt-2.5 space-y-2">
          <div
            v-for="(message, index) in chatMessages"
            :key="index"
            class="flex gap-2"
            :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <div
              class="max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-relaxed"
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
        <div class="mt-3 flex items-center gap-2">
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
  </section>
</template>
