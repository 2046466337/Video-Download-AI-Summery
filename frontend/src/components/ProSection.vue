<script setup lang="ts">
import { ArrowRight, Check, CreditCard, Loader2, Sparkles } from 'lucide-vue-next'
import { useAuth } from '../composables/useAuth'
import { useMembership } from '../composables/useMembership'

const { isLoggedIn, openAuth } = useAuth()
const { membership, isPro, checkingOut, error, showMockPay, purchase, confirmMockPay, cancelMockPay } =
  useMembership()

const freePoints = ['720P 以内清晰度', '单条链接逐个下载', 'MP3 音频提取', '每日有限次数']

const proPoints = [
  '4K / 原画无损下载，不限次数',
  '批量粘贴多条链接，整个合集一起下',
  'AI 一键总结视频要点，省掉通勤时间',
  '字幕提取与翻译，输出 SRT 文件',
  '优先下载队列，高峰期不排队',
]

function onBuy() {
  if (!isLoggedIn.value) {
    openAuth()
    return
  }
  purchase()
}
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
            一次购买，解锁 4K 原画、批量下载和 AI 视频总结。一个月的价格，不到一杯咖啡。
          </p>

          <div class="mt-6 flex items-end gap-2">
            <span class="headline text-[40px] leading-none">¥9.9</span>
            <span class="pb-1 text-sm text-white/60">/ 30 天</span>
            <span
              v-if="isPro"
              class="mb-1 ml-1 rounded-full bg-emerald-400/90 px-2 py-0.5 text-[11px] font-semibold text-slate-900"
            >
              已开通
            </span>
          </div>

          <button
            type="button"
            class="mt-5 inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-900 transition hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-60"
            :disabled="checkingOut"
            @click="onBuy"
          >
            <Loader2 v-if="checkingOut" class="size-4 animate-spin" />
            <CreditCard v-else class="size-4" />
            {{ isPro ? '续费' : '立即开通 Pro' }}
            <ArrowRight v-if="!checkingOut" class="size-4" />
          </button>
          <p v-if="isPro" class="mt-2.5 text-xs text-emerald-300">
            会员有效期至 {{ membership.expires_text }}，到期后可手动续费
          </p>
          <p v-else class="mt-2.5 text-xs text-white/50">
            一次性支付 ¥9.9，解锁 30 天会员，到期手动续费
          </p>
          <p v-if="error" class="mt-2 text-xs text-rose-300">{{ error }}</p>
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

    <!-- mock 支付弹窗：离线模拟 Stripe 支付页 -->
    <div
      v-if="showMockPay"
      class="fixed inset-0 z-[60] flex items-center justify-center p-4"
    >
      <div class="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" @click="cancelMockPay"></div>
      <div
        class="animate-rise relative w-full max-w-sm rounded-2xl bg-white p-6 shadow-lift"
        role="dialog"
        aria-modal="true"
      >
        <p class="text-xs font-medium uppercase tracking-wide text-slate-400">模拟支付（mock）</p>
        <div class="mt-3 flex items-end gap-2">
          <span class="headline text-[40px] leading-none text-slate-900">¥9.9</span>
          <span class="pb-1 text-sm text-slate-500">/ 30 天 Pro 会员</span>
        </div>
        <p class="mt-3 text-xs leading-relaxed text-slate-500">
          这是本地 mock 支付页面，用于在无外网、无 Stripe 账号时跑通完整购买流程。
          点击「确认支付」即可开通会员（不产生真实扣款）。
        </p>

        <div class="mt-5 flex gap-3">
          <button
            type="button"
            class="inline-flex min-h-11 flex-1 items-center justify-center rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            @click="cancelMockPay"
          >
            取消
          </button>
          <button
            type="button"
            class="inline-flex min-h-11 flex-1 items-center justify-center rounded-full bg-brand-500 px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
            @click="confirmMockPay"
          >
            确认支付 ¥9.9
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
