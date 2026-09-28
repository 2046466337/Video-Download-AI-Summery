<script setup lang="ts">
import { Download, LogOut, Sparkles, UserRound } from 'lucide-vue-next'
import { useAuth } from '../composables/useAuth'
import { useMembership } from '../composables/useMembership'

const { isLoggedIn, user, openAuth, logout } = useAuth()
const { isPro } = useMembership()
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

        <template v-if="isLoggedIn">
          <a
            v-if="isPro"
            href="#pro"
            class="inline-flex items-center gap-1 rounded-full bg-amber-400/15 px-2.5 py-1 text-xs font-semibold text-amber-600 transition hover:opacity-85"
            title="查看会员权益"
          >
            <Sparkles class="size-3.5" />
            Pro 会员
          </a>
          <a
            v-else
            href="#pro"
            class="inline-flex min-h-11 items-center gap-1.5 rounded-full bg-brand-500 px-4 py-2 text-xs font-semibold text-white transition hover:opacity-85"
          >
            <Sparkles class="size-3.5" />
            升级 Pro
          </a>

          <span class="hidden max-w-[10rem] truncate text-xs text-slate-500 sm:inline-flex sm:items-center sm:gap-1">
            <UserRound class="size-3.5" />
            {{ user?.email }}
          </span>
          <button
            type="button"
            class="inline-flex size-9 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
            aria-label="退出登录"
            @click="logout"
          >
            <LogOut class="size-4" />
          </button>
        </template>

        <button
          v-else
          type="button"
          class="inline-flex min-h-11 items-center gap-1.5 rounded-full border border-black/10 bg-white px-4 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
          @click="openAuth"
        >
          <UserRound class="size-3.5" />
          登录
        </button>
      </div>
    </div>
  </header>
</template>
