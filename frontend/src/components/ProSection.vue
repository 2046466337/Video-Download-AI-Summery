<script setup lang="ts">
import { ArrowRight, Check, Sparkles } from 'lucide-vue-next'

const freePoints = ['720P 以内清晰度', '单条链接逐个下载', 'MP3 音频提取', '每日有限次数']

const proPoints = [
  '4K / 原画无损下载，不限次数',
  '批量粘贴多条链接，整个合集一起下',
  'AI 一键总结视频要点，省掉通勤时间',
  '字幕提取与翻译，输出 SRT 文件',
  '优先下载队列，高峰期不排队',
]
</script>

<template>
  <section id="pro" class="scroll-mt-20 px-1">
    <div
      class="overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-brand-700 p-6 text-white shadow-lift sm:p-9"
    >
      <div class="grid gap-8 lg:grid-cols-[1fr_1.1fr] lg:items-center">
        <div>
          <span
            class="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-xs font-medium"
          >
            <Sparkles class="size-3.5" />
            Pro 会员
          </span>
          <h2 class="headline mt-4 text-[26px] leading-tight sm:text-[32px]">
            把省下来的时间，<br />还给更值得的事
          </h2>
          <p class="mt-3 max-w-md text-sm leading-relaxed text-white/70">
            一次订阅，解锁 4K 原画、批量下载和 AI 视频总结。一个月的价格，不到一杯咖啡。
          </p>

          <div class="mt-6 flex items-end gap-2">
            <span class="headline text-[40px] leading-none">¥19</span>
            <span class="pb-1 text-sm text-white/60">/ 月</span>
            <span class="mb-1 ml-1 rounded-full bg-amber-400/90 px-2 py-0.5 text-[11px] font-semibold text-slate-900">
              首月 ¥9
            </span>
          </div>

          <button
            type="button"
            class="mt-5 inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-900 transition hover:bg-white/90"
          >
            加入 Pro 等候名单
            <ArrowRight class="size-4" />
          </button>
          <p class="mt-2.5 text-xs text-white/50">支付能力开发中，现在加入可享上线首发价</p>
        </div>

        <div class="grid gap-3 sm:grid-cols-2 lg:gap-4">
          <div class="rounded-xl bg-white/5 p-4 ring-1 ring-white/10">
            <p class="text-xs font-semibold tracking-wide text-white/50">免费版</p>
            <ul class="mt-3 space-y-2">
              <li
                v-for="point in freePoints"
                :key="point"
                class="flex items-start gap-2 text-[13px] text-white/60"
              >
                <Check class="mt-0.5 size-3.5 shrink-0 text-white/35" />
                <span>{{ point }}</span>
              </li>
            </ul>
          </div>

          <div class="rounded-xl bg-white/12 p-4 ring-1 ring-white/25">
            <p class="text-xs font-semibold tracking-wide text-amber-300">Pro 版</p>
            <ul class="mt-3 space-y-2">
              <li
                v-for="point in proPoints"
                :key="point"
                class="flex items-start gap-2 text-[13px] text-white"
              >
                <Check class="mt-0.5 size-3.5 shrink-0 text-amber-300" />
                <span>{{ point }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
