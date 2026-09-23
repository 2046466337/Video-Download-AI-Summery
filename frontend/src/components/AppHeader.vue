<script setup lang="ts">
import { Download, Sparkles } from 'lucide-vue-next'
</script>

<template>
  <header class="sticky top-0 z-50 border-b border-black/5 bg-white/90 backdrop-blur-md">
    <div class="mx-auto flex h-16 max-w-5xl items-center justify-between px-4 sm:px-6">
      <a href="#top" class="flex items-center gap-2.5">
        <span
          class="grid size-9 place-items-center rounded-[10px] bg-gradient-to-br from-brand-400 to-brand-700 shadow-lift"
        >
          <Download class="size-5 text-white" :stroke-width="2.4" />
        </span>
        <span class="headline text-[17px] text-slate-900">万能视频下载</span>
      </a>

      <div class="flex items-center gap-3">
        <span class="hidden items-center gap-1.5 text-xs font-medium text-slate-500 sm:inline-flex">
          <span class="size-1.5 rounded-full bg-emerald-500"></span>
          已支持 1000+ 平台
        </span>
        <a
          href="#pro"
          class="inline-flex min-h-11 items-center gap-1.5 rounded-full bg-brand-500 px-4 py-2 text-xs font-semibold text-white transition hover:opacity-85"
        >
          <Sparkles class="size-3.5" />
          升级 Pro
        </a>
      </div>
    </div>
  </header>
</template>
