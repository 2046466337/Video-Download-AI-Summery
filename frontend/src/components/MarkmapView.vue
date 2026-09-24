<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Transformer } from 'markmap-lib'
import { Markmap } from 'markmap-view'
import { ChevronDown, Download, Maximize2, Minimize2 } from 'lucide-vue-next'
import { downloadText } from '../utils/download'

const props = defineProps<{ markdown: string }>()

const rootRef = ref<HTMLDivElement | null>(null)
const svgRef = ref<SVGSVGElement | null>(null)

const transformer = new Transformer()
let mm: Markmap | null = null

const isFullscreen = ref(false)
const menuOpen = ref(false)

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

async function toggleFullscreen() {
  try {
    if (document.fullscreenElement) {
      await document.exitFullscreen()
    } else {
      await rootRef.value?.requestFullscreen()
    }
  } catch {
    // 部分环境（如受限 webview）不支持全屏，静默忽略
  }
}

function onFullscreenChange() {
  isFullscreen.value = document.fullscreenElement === rootRef.value
  // 全屏过渡结束后自适应，让思维导图铺满整个屏幕
  window.setTimeout(() => mm?.fit(), 200)
}

/** 导出 SVG 内嵌的缩放 / 拖拽脚本：在浏览器打开后可用滚轮缩放、拖拽平移查看。 */
const ZOOM_PAN_SCRIPT = `(function () {
  var svg = document.documentElement;
  var g = document.getElementById('viewport');
  if (!g) return;
  var tx = 0, ty = 0, s = 1;
  var MIN = 0.05, MAX = 50;
  function apply() {
    g.setAttribute('transform', 'translate(' + tx + ' ' + ty + ') scale(' + s + ')');
  }
  function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }
  function toUser(cx, cy) {
    var ctm = svg.getScreenCTM();
    if (!ctm || typeof ctm.inverse !== 'function') return { x: 0, y: 0 };
    var p = new DOMPoint(cx, cy).matrixTransform(ctm.inverse());
    return { x: p.x, y: p.y };
  }
  svg.addEventListener('wheel', function (e) {
    e.preventDefault();
    var dy = e.deltaY;
    if (e.deltaMode === 1) dy = dy * 33;
    else if (e.deltaMode === 2) dy = dy * 100;
    var k = Math.pow(1.15, -dy / 100);
    var ns = clamp(s * k, MIN, MAX);
    if (ns === s) return;
    var p = toUser(e.clientX, e.clientY);
    tx = p.x - (p.x - tx) / s * ns;
    ty = p.y - (p.y - ty) / s * ns;
    s = ns;
    apply();
  }, { passive: false });
  var dragging = false, start = { x: 0, y: 0 }, startTx = 0, startTy = 0;
  svg.addEventListener('pointerdown', function (e) {
    dragging = true;
    start = toUser(e.clientX, e.clientY);
    startTx = tx;
    startTy = ty;
    try { svg.setPointerCapture(e.pointerId); } catch (err) {}
    svg.style.cursor = 'grabbing';
  });
  svg.addEventListener('pointermove', function (e) {
    if (!dragging) return;
    var p = toUser(e.clientX, e.clientY);
    tx = startTx + (p.x - start.x);
    ty = startTy + (p.y - start.y);
    apply();
  });
  function end() { dragging = false; svg.style.cursor = 'grab'; }
  svg.addEventListener('pointerup', end);
  svg.addEventListener('pointercancel', end);
  svg.style.cursor = 'grab';
})();`

/** 序列化完整整张思维导图（非可视区域截取）：白色背景、viewBox 适配画布、支持缩放与拖拽。 */
function buildExportSvg(): string {
  if (!mm) return ''
  const svg = mm.svg.node()
  if (!svg) return ''

  const { x1, y1, x2, y2 } = mm.state.rect
  const pad = 16
  const x = x1 - pad
  const y = y1 - pad
  const width = Math.max(x2 - x1 + pad * 2, 1)
  const height = Math.max(y2 - y1 + pad * 2, 1)

  const clone = svg.cloneNode(true) as SVGSVGElement
  const SVG_NS = 'http://www.w3.org/2000/svg'

  // 移除根分组的缩放 transform，回到 state.rect 对应的自然坐标系
  const rootG = clone.querySelector(':scope > g')
  rootG?.removeAttribute('transform')

  // 视口分组：白底 + 内容放入同一分组，供脚本统一做缩放 / 平移
  const viewport = document.createElementNS(SVG_NS, 'g')
  viewport.setAttribute('id', 'viewport')

  // 固定白色背景（随内容一起缩放，始终覆盖整张导图）
  const bg = document.createElementNS(SVG_NS, 'rect')
  bg.setAttribute('x', String(x))
  bg.setAttribute('y', String(y))
  bg.setAttribute('width', String(width))
  bg.setAttribute('height', String(height))
  bg.setAttribute('fill', '#ffffff')
  viewport.appendChild(bg)

  if (rootG) viewport.appendChild(rootG)
  clone.appendChild(viewport)

  clone.setAttribute('xmlns', SVG_NS)
  // 不写死固定宽高：用 viewBox + 100% 让 SVG 自适应画布，矢量任意缩放不失真
  clone.setAttribute('preserveAspectRatio', 'xMidYMid meet')
  clone.setAttribute('viewBox', `${x} ${y} ${width} ${height}`)
  clone.setAttribute('width', '100%')
  clone.setAttribute('height', '100%')
  clone.style.backgroundColor = '#ffffff'

  // 注入缩放 / 拖拽交互脚本
  const script = document.createElementNS(SVG_NS, 'script')
  script.textContent = ZOOM_PAN_SCRIPT
  clone.appendChild(script)

  return new XMLSerializer().serializeToString(clone)
}

function exportSvg() {
  const svg = buildExportSvg()
  menuOpen.value = false
  if (!svg) return
  downloadText('思维导图.svg', svg, 'image/svg+xml')
}

function exportMarkdown() {
  const markdown = props.markdown.trim()
  menuOpen.value = false
  if (!markdown) return
  downloadText('思维导图.md', markdown, 'text/markdown')
}

onMounted(() => {
  render()
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

watch(() => props.markdown, render)

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  mm?.destroy()
  mm = null
})
</script>

<template>
  <div
    ref="rootRef"
    class="mindmap-root flex min-h-0 w-full flex-col overflow-hidden rounded-xl bg-slate-50"
  >
    <!-- 工具栏 -->
    <div class="flex items-center justify-end gap-1 p-1.5">
      <button
        type="button"
        :title="isFullscreen ? '退出全屏' : '全屏展示'"
        class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 transition hover:border-brand-300 hover:bg-slate-50"
        @click="toggleFullscreen"
      >
        <Minimize2 v-if="isFullscreen" class="size-3.5" />
        <Maximize2 v-else class="size-3.5" />
        {{ isFullscreen ? '退出全屏' : '全屏' }}
      </button>

      <div class="relative">
        <button
          type="button"
          title="下载思维导图"
          class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 transition hover:border-brand-300 hover:bg-slate-50"
          @click="menuOpen = !menuOpen"
        >
          <Download class="size-3.5" />
          下载
          <ChevronDown class="size-3.5" :class="menuOpen ? 'rotate-180' : ''" />
        </button>
        <div
          v-if="menuOpen"
          class="card absolute right-0 top-full z-20 mt-1 w-44 p-1 shadow-lift"
        >
          <button
            type="button"
            class="flex w-full items-center rounded-lg px-3 py-2 text-left text-sm text-slate-700 transition hover:bg-slate-50"
            @click="exportSvg"
          >
            SVG 图片 (.svg)
          </button>
          <button
            type="button"
            class="flex w-full items-center rounded-lg px-3 py-2 text-left text-sm text-slate-700 transition hover:bg-slate-50"
            @click="exportMarkdown"
          >
            Markdown (.md)
          </button>
        </div>
      </div>
    </div>

    <!-- 导图区 -->
    <div class="min-h-0 flex-1 px-1 pb-1">
      <svg ref="svgRef" class="h-full w-full"></svg>
    </div>

    <div v-if="menuOpen" class="fixed inset-0 z-10" @click="menuOpen = false"></div>
  </div>
</template>

<style scoped>
.mindmap-root:fullscreen {
  background-color: #fff;
  border-radius: 0;
}
</style>
