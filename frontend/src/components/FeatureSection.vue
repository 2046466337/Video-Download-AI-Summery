<script setup lang="ts">
import { Gauge, Globe, Music4, Smartphone } from 'lucide-vue-next'

const features = [
  {
    icon: Globe,
    title: '1000+ 平台通吃',
    desc: '基于业界最成熟的开源解析引擎，主流视频站、短视频、播客一个链接搞定。',
    tint: 'bg-brand-50 text-brand-600',
  },
  {
    icon: Gauge,
    title: '最高 4K 原画',
    desc: '自动抓取音视频最高码率轨道并无损合并，不再被平台的清晰度限制卡住。',
    tint: 'bg-amber-50 text-amber-600',
  },
  {
    icon: Music4,
    title: '一键提取 MP3',
    desc: '网课、播客、现场音乐只想听不想看？直接输出 192kbps 音频文件。',
    tint: 'bg-violet-50 text-violet-600',
  },
  {
    icon: Smartphone,
    title: '手机电脑通用',
    desc: '纯网页操作，下载由服务端完成，手机浏览器点一下就能存进相册和文件。',
    tint: 'bg-emerald-50 text-emerald-600',
  },
]
</script>

<template>
  <section class="px-1">
    <h2 class="headline text-center text-2xl text-slate-900 sm:text-[28px]">
      为什么值得<span class="text-brand-600">放进收藏夹</span>
    </h2>
    <p class="mt-2 text-center text-sm text-balance text-slate-500">把原本要装客户端、开会员才能做的事，变成粘贴一个链接</p>

    <div class="mt-6 grid gap-3 sm:grid-cols-2">
      <article
        v-for="feature in features"
        :key="feature.title"
        class="card p-5 transition hover:-translate-y-0.5 hover:shadow-lift"
      >
        <span class="grid size-10 place-items-center rounded-[10px]" :class="feature.tint">
          <component :is="feature.icon" class="size-5" />
        </span>
        <h3 class="mt-3.5 text-base font-bold text-slate-900">{{ feature.title }}</h3>
        <p class="mt-1.5 text-sm leading-relaxed text-slate-500">{{ feature.desc }}</p>
      </article>
    </div>
  </section>
</template>
