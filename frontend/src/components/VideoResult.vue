<script setup lang="ts">
import { Clock, Download, ImageOff, Music4, Sparkles, User } from 'lucide-vue-next'
import type { QualityOption, VideoInfo } from '../types'

defineProps<{ video: VideoInfo }>()
const selected = defineModel<string>('selected', { required: true })
const emit = defineEmits<{ download: []; summarize: [] }>()

const isHighEnd = (option: QualityOption) => (option.height ?? 0) >= 1440
</script>

<template>
  <section class="card animate-rise overflow-hidden">
    <!-- 缩略图 + 时长角标 -->
    <div class="relative aspect-video w-full bg-slate-100">
      <img
        v-if="video.thumbnail"
        :src="video.thumbnail"
        :alt="video.title"
        referrerpolicy="no-referrer"
        loading="lazy"
        class="absolute inset-0 size-full object-cover"
      />
      <div v-else class="absolute inset-0 grid place-items-center text-slate-300">
        <ImageOff class="size-8" />
      </div>
      <span
        v-if="video.duration_text"
        class="absolute right-2 bottom-2 rounded-md bg-black/70 px-1.5 py-0.5 text-[11px] font-medium tabular-nums text-white"
      >
        {{ video.duration_text }}
      </span>
    </div>

    <div class="p-4 sm:p-5">
      <h2 class="line-clamp-2 text-base leading-snug font-bold text-slate-900">
        {{ video.title }}
      </h2>

      <div class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-slate-500">
        <span
          v-if="video.platform"
          class="rounded-full bg-brand-50 px-2 py-0.5 font-medium text-brand-600"
        >
          {{ video.platform }}
        </span>
        <span v-if="video.uploader" class="inline-flex max-w-40 items-center gap-1 truncate">
          <User class="size-3.5 shrink-0" />{{ video.uploader }}
        </span>
        <span v-if="video.duration_text" class="inline-flex items-center gap-1">
          <Clock class="size-3.5" />{{ video.duration_text }}
        </span>
      </div>

      <div class="mt-4 border-t border-slate-100 pt-4">
        <p class="text-xs font-semibold text-slate-400">选择清晰度</p>

        <div class="mt-2.5 grid grid-cols-2 gap-2">
          <button
            v-for="option in video.options"
            :key="option.id"
            type="button"
            class="relative min-h-11 rounded-xl border px-3 py-2.5 text-left transition"
            :class="
              selected === option.id
                ? 'border-brand-500 bg-brand-50/70 ring-1 ring-brand-500/40'
                : 'border-slate-200 bg-white hover:border-brand-300 hover:bg-slate-50'
            "
            @click="selected = option.id"
          >
            <span class="flex items-center gap-1.5">
              <Music4 v-if="option.kind === 'audio'" class="size-3.5 shrink-0 text-slate-400" />
              <span class="truncate text-sm font-semibold text-slate-900">{{ option.label }}</span>
            </span>
            <span class="mt-0.5 block truncate text-xs text-slate-400">
              {{ option.filesize_text || option.note }}
            </span>

            <span
              v-if="option.recommended"
              class="absolute -top-1.5 right-2 rounded-full bg-brand-500 px-1.5 py-px text-[10px] font-semibold text-white"
            >
              推荐
            </span>
            <span
              v-else-if="isHighEnd(option)"
              class="absolute -top-1.5 right-2 rounded-full bg-gradient-to-r from-amber-400 to-orange-500 px-1.5 py-px text-[10px] font-semibold text-white"
            >
              超清
            </span>
          </button>
        </div>

        <div class="mt-4 flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            class="inline-flex w-full items-center justify-center gap-2 rounded-full bg-brand-500 px-6 py-3 text-sm font-semibold text-white shadow-lift transition hover:opacity-90 sm:flex-1"
            @click="emit('download')"
          >
            <Download class="size-4" />
            开始下载
          </button>
          <button
            type="button"
            class="inline-flex w-full items-center justify-center gap-2 rounded-full border border-brand-200 bg-white px-6 py-3 text-sm font-semibold text-brand-600 transition hover:bg-brand-50 sm:flex-1"
            @click="emit('summarize')"
          >
            <Sparkles class="size-4" />
            AI 总结
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
