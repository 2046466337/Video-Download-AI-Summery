<script setup lang="ts">
import { Loader2, Lock, Mail, X } from 'lucide-vue-next'
import { ref } from 'vue'
import { useAuth } from '../composables/useAuth'

const { showAuthModal, loading, error, login, register, closeAuth, clearError } = useAuth()

const mode = ref<'login' | 'register'>('login')
const email = ref('')
const password = ref('')

function switchMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  email.value = ''
  password.value = ''
  clearError()
}

async function submit() {
  const ok =
    mode.value === 'login'
      ? await login(email.value, password.value)
      : await register(email.value, password.value)
  if (ok) {
    email.value = ''
    password.value = ''
  }
}
</script>

<template>
  <div
    v-if="showAuthModal"
    class="fixed inset-0 z-[60] flex items-center justify-center p-4"
  >
    <div class="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" @click="closeAuth"></div>

    <div
      class="animate-rise relative w-full max-w-sm rounded-2xl bg-white p-6 shadow-lift"
      role="dialog"
      aria-modal="true"
    >
      <button
        type="button"
        class="absolute right-4 top-4 grid size-8 place-items-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
        aria-label="关闭"
        @click="closeAuth"
      >
        <X class="size-4" />
      </button>

      <h2 class="headline text-xl text-slate-900">
        {{ mode === 'login' ? '登录' : '注册' }}
      </h2>
      <p class="mt-1 text-xs text-slate-400">
        {{ mode === 'login' ? '登录后购买 Pro 会员' : '注册一个账号，用于绑定会员' }}
      </p>

      <form class="mt-5 space-y-3" @submit.prevent="submit">
        <label class="block">
          <span class="text-xs font-medium text-slate-500">邮箱</span>
          <div
            class="mt-1 flex items-center gap-2 rounded-xl border border-black/10 bg-white px-3 py-2.5 transition focus-within:border-brand-500/50 focus-within:ring-2 focus-within:ring-brand-500/15"
          >
            <Mail class="size-4 shrink-0 text-slate-400" />
            <input
              v-model="email"
              type="email"
              required
              autocomplete="email"
              placeholder="you@example.com"
              class="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400"
            />
          </div>
        </label>

        <label class="block">
          <span class="text-xs font-medium text-slate-500">密码</span>
          <div
            class="mt-1 flex items-center gap-2 rounded-xl border border-black/10 bg-white px-3 py-2.5 transition focus-within:border-brand-500/50 focus-within:ring-2 focus-within:ring-brand-500/15"
          >
            <Lock class="size-4 shrink-0 text-slate-400" />
            <input
              v-model="password"
              type="password"
              required
              :minlength="mode === 'register' ? 8 : 1"
              autocomplete="current-password"
              placeholder="至少 8 位"
              class="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400"
            />
          </div>
        </label>

        <p v-if="error" role="alert" class="text-xs text-rose-500">{{ error }}</p>

        <button
          type="submit"
          :disabled="loading"
          class="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-full bg-brand-500 px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Loader2 v-if="loading" class="size-4 animate-spin" />
          {{ mode === 'login' ? '登录' : '注册并登录' }}
        </button>
      </form>

      <p class="mt-4 text-center text-xs text-slate-400">
        {{ mode === 'login' ? '还没有账号？' : '已有账号？' }}
        <button
          type="button"
          class="font-medium text-brand-600 hover:underline"
          @click="switchMode"
        >
          {{ mode === 'login' ? '立即注册' : '去登录' }}
        </button>
      </p>
    </div>
  </div>
</template>
