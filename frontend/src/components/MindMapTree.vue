<script setup lang="ts">
import type { MindMapNode } from '../types'

defineOptions({ name: 'MindMapTree' })

defineProps<{ node: MindMapNode }>()
</script>

<template>
  <div class="mindmap-node">
    <div class="flex items-start gap-1.5">
      <span class="mt-[7px] size-1.5 shrink-0 rounded-full bg-brand-400" />
      <span class="text-sm leading-snug text-slate-700">{{ node.topic }}</span>
    </div>
    <div v-if="node.children?.length" class="mt-1 ml-1 border-l border-slate-200 pl-3">
      <MindMapTree v-for="(child, index) in node.children" :key="index" :node="child" />
    </div>
  </div>
</template>
