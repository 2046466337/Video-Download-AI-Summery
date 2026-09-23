<script setup lang="ts">
import { AlertCircle, CheckCircle2, Download, Loader2, X } from 'lucide-vue-next'
import { computed } from 'vue'
import type { TaskState } from '../types'

const props = defineProps<{ tasks: TaskState[] }>()
const emit = defineEmits<{ save: [task: TaskState]; remove: [id: string] }>()

const activeCount = computed(
  () => props.tasks.filter((t) => t.status === 'queued' || t.status === 'running').length,
)

const badgeClass = (task: TaskState) => {
  if (task.status === 'success') return 'bg-emerald-50 text-emerald-600'
  if (task.status === 'failed') return 'bg-rose-50 text-rose-500'
  return 'bg-brand-50 text-brand-600'
}
</script>

<template>
  <section v-if="tasks.length" class="animate-rise">
    <div class="flex items-center justify-between px-1">
      <h2 class="headline text-lg text-slate-900">下载任务</h2>
      <span v-if="activeCount" class="text-xs text-slate-400">{{ activeCount }} 个进行中</span>
    </div>

    <div class="mt-3 space-y-2.5">
      <article v-for="task in tasks" :key="task.id" class="card p-4">
        <div class="flex items-start gap-3">
          <span
            class="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full"
            :class="badgeClass(task)"
          >
            <CheckCircle2 v-if="task.status === 'success'" class="size-4" />
            <AlertCircle v-else-if="task.status === 'failed'" class="size-4" />
            <Loader2 v-else class="size-4 animate-spin" />
          </span>

          <div class="min-w-0 flex-1">
            <div class="flex items-start justify-between gap-3">
              <p class="truncate text-sm font-medium text-slate-900">{{ task.title }}</p>
              <button
                type="button"
                aria-label="移除任务"
                class="shrink-0 text-slate-300 transition hover:text-slate-500"
                @click="emit('remove', task.id)"
              >
                <X class="size-4" />
              </button>
            </div>

            <div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-400">
              <span
                v-if="task.quality"
                class="rounded bg-slate-100 px-1.5 py-0.5 font-medium text-slate-500"
              >
                {{ task.quality }}
              </span>
              <span>{{ task.stage }}</span>
              <span v-if="task.total_text" class="tabular-nums">
                {{ task.downloaded_text }} / {{ task.total_text }}
              </span>
              <span v-if="task.speed_text" class="tabular-nums">{{ task.speed_text }}</span>
              <span v-if="task.eta_text">剩余 {{ task.eta_text }}</span>
            </div>

            <div
              v-if="task.status !== 'failed'"
              class="mt-2.5 h-1.5 overflow-hidden rounded-full bg-slate-100"
            >
              <div
                class="h-full rounded-full bg-gradient-to-r from-brand-400 to-brand-600 transition-[width] duration-500 ease-out"
                :style="{ width: `${task.progress}%` }"
              ></div>
            </div>

            <p v-if="task.error" class="mt-2 text-xs text-rose-500">{{ task.error }}</p>

            <button
              v-if="task.status === 'success'"
              type="button"
              class="mt-3 inline-flex items-center gap-1.5 rounded-full bg-brand-500 px-4 py-2 text-xs font-semibold text-white transition hover:opacity-85"
              @click="emit('save', task)"
            >
              <Download class="size-3.5" />
              保存到本地
              <span v-if="task.filesize_text" class="font-normal opacity-80">
                {{ task.filesize_text }}
              </span>
            </button>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>
