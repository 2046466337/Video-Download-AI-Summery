<script setup lang="ts">
const steps = [
  {
    step: '01',
    title: '粘贴任意平台链接',
    tags: '#YouTube · #B站 · #抖音',
    tone: 'from-sky-100 via-blue-50 to-indigo-100',
    scene: 'paste',
  },
  {
    step: '02',
    title: '选清晰度，一键开下',
    tags: '#4K · #1080P · #MP3',
    tone: 'from-amber-100 via-orange-50 to-rose-100',
    scene: 'quality',
  },
  {
    step: '03',
    title: '手机电脑直接保存',
    tags: '#免安装 · #免登录',
    tone: 'from-emerald-100 via-teal-50 to-cyan-100',
    scene: 'save',
  },
]
</script>

<template>
  <section class="px-1">
    <h2 class="headline text-center text-2xl text-slate-900 sm:text-[28px]">
      三步拿走视频，<span class="text-brand-600">不用装任何东西</span>
    </h2>
    <p class="mt-2 text-center text-sm text-slate-500">打开网页就能用，流程故意做成和搜索一样短</p>

    <div class="mt-6 grid gap-3 sm:grid-cols-3">
      <article
        v-for="item in steps"
        :key="item.step"
        class="card overflow-hidden transition hover:-translate-y-0.5 hover:shadow-lift"
      >
        <div
          class="relative isolate h-40 overflow-hidden bg-gradient-to-br px-5 py-4"
          :class="item.tone"
        >
          <span class="headline text-4xl text-slate-900/15">{{ item.step }}</span>

          <div v-if="item.scene === 'paste'" class="pointer-events-none absolute inset-0">
            <div
              class="absolute top-12 right-6 left-6 rounded-full bg-white px-4 py-2.5 text-left text-[11px] text-slate-400 shadow-card"
            >
              https://bilibili.com/video/...
            </div>
            <div
              class="absolute right-8 bottom-5 rounded-full bg-brand-500 px-3 py-1 text-[11px] font-semibold text-white shadow-lift"
            >
              解析
            </div>
          </div>

          <div v-else-if="item.scene === 'quality'" class="pointer-events-none absolute inset-x-6 top-12 grid grid-cols-2 gap-2">
            <div class="rounded-xl bg-white/80 p-2 ring-2 ring-brand-500">
              <p class="text-[11px] font-bold text-slate-900">1080P 高清</p>
              <p class="text-[10px] text-slate-400">推荐</p>
            </div>
            <div class="rounded-xl bg-white/70 p-2">
              <p class="text-[11px] font-bold text-slate-900">仅音频 MP3</p>
              <p class="text-[10px] text-slate-400">听课专用</p>
            </div>
            <div class="rounded-xl bg-white/70 p-2">
              <p class="text-[11px] font-bold text-slate-900">4K 超清</p>
              <p class="text-[10px] text-amber-500">Pro</p>
            </div>
            <div class="rounded-xl bg-white/70 p-2">
              <p class="text-[11px] font-bold text-slate-900">720P</p>
              <p class="text-[10px] text-slate-400">省流量</p>
            </div>
          </div>

          <div v-else class="pointer-events-none absolute inset-0">
            <div
              class="absolute top-10 left-1/2 h-24 w-16 -translate-x-1/2 rounded-[18px] border-[3px] border-slate-800/80 bg-white shadow-card"
            >
              <div class="mx-auto mt-1.5 h-1 w-6 rounded-full bg-slate-300"></div>
              <div class="mx-3 mt-3 h-8 rounded-md bg-brand-100"></div>
              <div class="mx-auto mt-3 h-5 w-10 rounded-full bg-brand-500"></div>
            </div>
          </div>
        </div>

        <div class="p-3">
          <h3 class="text-[15px] font-bold text-slate-900">{{ item.title }}</h3>
          <p class="mt-1 text-xs font-medium text-slate-500">{{ item.tags }}</p>
        </div>
      </article>
    </div>
  </section>
</template>
