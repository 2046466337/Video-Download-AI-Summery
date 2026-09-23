<script setup lang="ts">
import { ClipboardPaste, Link2, Loader2, Search, ShieldCheck, Smartphone, Sparkles, Zap } from 'lucide-vue-next'
import { ref } from 'vue'

const url = defineModel<string>({ required: true })
defineProps<{ parsing: boolean; totalDownloads: number }>()
const emit = defineEmits<{ parse: [] }>()
const pasteHint = ref('')

async function pasteFromClipboard() {
  try {
    const text = (await navigator.clipboard.readText()).trim()
    if (!text) {
      pasteHint.value = '剪贴板是空的'
      return
    }
    url.value = text
    pasteHint.value = ''
  } catch {
    pasteHint.value = '浏览器拦截了剪贴板，请手动粘贴'
  }
}

const platforms = [
  'YouTube',
  '哔哩哔哩',
  '抖音',
  'TikTok',
  'X / Twitter',
  '微博',
  '快手',
  'Instagram',
  'Facebook',
  'Vimeo',
  'Twitch',
  'Reddit',
]
</script>

<template>
  <section class="px-4 pt-12 pb-2 text-center sm:px-6 sm:pt-16">
    <div class="mx-auto max-w-3xl">
      <span
        class="inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-600"
      >
        <Sparkles class="size-3.5" />
        免安装 · 免登录 · 手机也能存
      </span>

      <h1 class="headline mt-5 text-[32px] leading-[1.18] text-slate-900 sm:text-[52px]">
        视频下载，<span class="text-brand-600">粘贴链接就好</span>
      </h1>

      <p class="mx-auto mt-4 max-w-2xl text-sm leading-relaxed text-slate-500 sm:text-base">
        支持 1000+ 主流平台，最高 4K 原画无损保存。<br class="hidden sm:inline" />
        一键提取 MP3，不用装客户端，不用开会员。
      </p>

      <form class="mx-auto mt-8 max-w-2xl" @submit.prevent="emit('parse')">
        <div
          class="flex items-center gap-2 rounded-full bg-white py-2 pr-2 pl-4 shadow-card ring-1 ring-black/5 transition focus-within:ring-2 focus-within:ring-brand-500/35 sm:pl-5"
        >
          <Link2 class="size-4 shrink-0 text-slate-400" />
          <input
            v-model="url"
            type="text"
            inputmode="url"
            autocomplete="off"
            spellcheck="false"
            placeholder="粘贴 YouTube / B站 / 抖音链接"
            class="min-w-0 flex-1 bg-transparent py-2 text-sm text-slate-900 outline-none placeholder:text-slate-400"
          />
          <button
            type="button"
            class="hidden size-9 shrink-0 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-brand-600 sm:inline-flex"
            aria-label="从剪贴板粘贴"
            @click="pasteFromClipboard"
          >
            <ClipboardPaste class="size-4" />
          </button>
          <button
            type="submit"
            :disabled="parsing || !url.trim()"
            class="inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-full bg-brand-500 px-4 py-2 text-sm font-semibold text-white transition hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-40 sm:px-6"
          >
            <Loader2 v-if="parsing" class="size-4 animate-spin" />
            <Search v-else class="size-4" />
            <span>{{ parsing ? '解析中' : '解析' }}</span>
          </button>
        </div>
        <p v-if="pasteHint" class="mt-2 text-xs text-slate-400">{{ pasteHint }}</p>
      </form>

      <div class="mt-5 flex flex-wrap justify-center gap-1.5">
        <span
          v-for="platform in platforms"
          :key="platform"
          class="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-500 ring-1 ring-black/5"
        >
          {{ platform }}
        </span>
      </div>

      <div class="mt-6 flex flex-wrap justify-center gap-x-5 gap-y-2 text-xs text-slate-400">
        <span class="inline-flex items-center gap-1.5"><Zap class="size-3.5" />无需安装客户端</span>
        <span class="inline-flex items-center gap-1.5"><ShieldCheck class="size-3.5" />不登录不留存</span>
        <span class="inline-flex items-center gap-1.5"><Smartphone class="size-3.5" />手机可直接保存</span>
        <span v-if="totalDownloads > 0" class="font-medium text-slate-500">
          已成功下载 {{ totalDownloads.toLocaleString('zh-CN') }} 个视频
        </span>
      </div>
    </div>
  </section>
</template>
