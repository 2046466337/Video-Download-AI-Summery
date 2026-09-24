<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Transformer } from 'markmap-lib'
import { Markmap } from 'markmap-view'

const props = defineProps<{ markdown: string }>()

const svgRef = ref<SVGSVGElement | null>(null)

const transformer = new Transformer()
let mm: Markmap | null = null

function render() {
  if (!svgRef.value) return
  const markdown = props.markdown.trim()
  if (!markdown) return

  let root
  try {
    root = transformer.transform(markdown).root
  } catch {
    return
  }

  if (!mm) {
    mm = Markmap.create(svgRef.value, { autoFit: true, duration: 200 }, root)
  } else {
    mm.setData(root)
    mm.fit()
  }
}

onMounted(render)
watch(() => props.markdown, render)
onBeforeUnmount(() => {
  mm?.destroy()
  mm = null
})
</script>

<template>
  <svg ref="svgRef" class="h-80 w-full" />
</template>
