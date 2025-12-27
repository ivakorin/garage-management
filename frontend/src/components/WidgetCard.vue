<script setup lang="ts">
import {defineEmits, defineProps, onUnmounted, ref} from 'vue'
import type {Widget} from '../composables/useDraggableWidgets'
import FormattedPluginName from "./FormattedPluginName.vue"

// Пропсы
interface Props {
  data: Widget
  index: number // нужен для обновления в родительском массиве
  editable: boolean // флаг режима редактирования
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update-position', update: { index: number; x: number; y: number }): void
  (e: 'update-size', update: { index: number; width: number; height: number }): void
  (e: 'remove', id: string): void
}>()

// Размер ячейки сетки (в пикселях)
const GRID_SIZE = 20

// Функция округления значения до ближайшего кратного GRID_SIZE
const roundToGrid = (value: number): number => {
  return Math.round(value / GRID_SIZE) * GRID_SIZE
}

// Состояние перетаскивания
const isDragging = ref(false)
const offsetX = ref(0)
const offsetY = ref(0)

// Состояние изменения размера
const isResizing = ref(false)
const resizeEdge = ref<'' | 'se' | 'e' | 's'>('') // юго-восточный, восточный, южный
const startWidth = ref(0)
const startHeight = ref(0)

// Обработчики drag (только если editable=true)
const onMousedown = (e: MouseEvent) => {
  if (!props.editable) return
  if (e.target instanceof HTMLElement && e.target.classList.contains('resize-handle')) return

  isDragging.value = true
  offsetX.value = e.clientX - props.data.x
  offsetY.value = e.clientY - props.data.y

  document.addEventListener('mousemove', onMousemove)
  document.addEventListener('mouseup', onMouseup)
}

const onMousemove = (e: MouseEvent) => {
  if (!isDragging.value || !props.editable) return

  const newX = roundToGrid(e.clientX - offsetX.value)
  const newY = roundToGrid(e.clientY - offsetY.value)

  emit('update-position', {index: props.index, x: newX, y: newY})
}

const onMouseup = () => {
  isDragging.value = false
  document.removeEventListener('mousemove', onMousemove)
  document.removeEventListener('mouseup', onMouseup)
}

// Обработчики resize (только если editable=true)
const onResizeMousedown = (edge: 'se' | 'e' | 's') => {
  if (!props.editable) return

  isResizing.value = true
  resizeEdge.value = edge
  startWidth.value = props.data.width
  startHeight.value = props.data.height


  document.addEventListener('mousemove', onResizeMousemove)
  document.addEventListener('mouseup', onResizeMouseup)
}

const onResizeMousemove = (e: MouseEvent) => {
  if (!isResizing.value || !props.editable) return

  let newWidth = startWidth.value
  let newHeight = startHeight.value

  switch (resizeEdge.value) {
    case 'se':
      newWidth = e.clientX - props.data.x
      newHeight = e.clientY - props.data.y
      break
    case 'e':
      newWidth = e.clientX - props.data.x
      break
    case 's':
      newHeight = e.clientY - props.data.y
      break
  }

  // Округляем размеры до сетки
  newWidth = roundToGrid(newWidth)
  newHeight = roundToGrid(newHeight)

  // Минимум — одна ячейка сетки
  newWidth = Math.max(newWidth, GRID_SIZE)
  newHeight = Math.max(newHeight, GRID_SIZE)

  emit('update-size', {index: props.index, width: newWidth, height: newHeight})
}

const onResizeMouseup = () => {
  isResizing.value = false
  resizeEdge.value = ''
  document.removeEventListener('mousemove', onResizeMousemove)
  document.removeEventListener('mouseup', onResizeMouseup)
}

// Очистка событий при уничтожении
onUnmounted(() => {
  document.removeEventListener('mousemove', onMousemove)
  document.removeEventListener('mouseup', onMouseup)
  document.removeEventListener('mousemove', onResizeMousemove)
  document.removeEventListener('mouseup', onResizeMouseup)
})

// Хелпер удаления (только если editable=true)
const handleRemove = () => {
  if (props.editable) {
    emit('remove', props.data.id)
  }
}
</script>

<template>
  <div
      class="widget"
      :class="{ 'editable': editable }"
      :style="{
        left: data.x + 'px',
        top: data.y + 'px',
        width: data.width + 'px',
        height: data.height + 'px'
      }"
      @mousedown="onMousedown"
  >
    <!-- Заголовок и кнопка удаления -->
    <div class="widget-header">
      <h4 class="widget-title">
        <formatted-plugin-name :name="data.name"/>
      </h4>
      <button
          v-if="editable"
          class="remove-btn"
          @click="handleRemove"
      >
        ×
      </button>
    </div>

    <!-- Контент виджета -->
    <div class="widget-content">
      <p><strong>Type:</strong> {{ data.type }}</p>
      <p><strong>ID:</strong> {{ data.id }}</p>
    </div>

    <!-- Ручки изменения размера (только если editable=true) -->
    <template v-if="editable">
      <!-- Юго-восточный угол -->
      <div
          class="resize-handle se"
          @mousedown.prevent="onResizeMousedown('se')"
      />
      <!-- Восточный край -->
      <div
          class="resize-handle e"
          @mousedown.prevent="onResizeMousedown('e')"
      />
      <!-- Южный край -->
      <div
          class="resize-handle s"
          @mousedown.prevent="onResizeMousedown('s')"
      />
    </template>
  </div>
</template>
<style scoped>
.widget {
  position: absolute;
  background-color: #ffffff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  overflow: hidden;
  user-select: none;
  touch-action: none;
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}

/* Режим просмотра — блокируем взаимодействие и визуально приглушаем */
.widget:not(.editable) {
  cursor: default !important;
  pointer-events: none;
  opacity: 0.95;
  filter: saturate(0.8) brightness(0.98);
}

/* Активное состояние при перетаскивании (только в режиме редактирования) */
.widget.editable:active,
.widget.editable.dragging {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  transform: scale(1.02);
  z-index: 1000; /* Поднимаем над другими при перетаскивании */
}

.widget-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: #f8f9fa;
  border-bottom: 1px solid #e0e0e0;
}

.widget-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.remove-btn {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: #666;
  transition: color 0.2s;
}

.remove-btn:hover {
  color: #d93025;
}

.widget-content {
  padding: 16px;
  color: #555;
  font-size: 13px;
}

/* Ручки изменения размера (видимы только при наведении в режиме редактирования) */
.resize-handle {
  position: absolute;
  background-color: transparent;
  cursor: se-resize;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.widget.editable:hover .resize-handle {
  opacity: 1;
}

/* Юго‑восточный угол (диагональное изменение) */
.resize-handle.se {
  width: 12px;
  height: 12px;
  bottom: -6px;
  right: -6px;
  cursor: se-resize;
  background-color: #18a058;
  border-radius: 50%;
  z-index: 1100;
}

/* Восточный край (изменение по горизонтали) */
.resize-handle.e {
  width: 6px;
  height: calc(100% - 12px);
  top: 6px;
  right: -3px;
  cursor: e-resize;
  background-color: #18a058;
  z-index: 1100;
}

/* Южный край (изменение по вертикали) */
.resize-handle.s {
  height: 6px;
  width: calc(100% - 12px);
  bottom: -3px;
  left: 6px;
  cursor: s-resize;
  background-color: #18a058;
  z-index: 1100;
}

/* Эффект наведения на виджет (только в режиме редактирования) */
.widget.editable:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

/* Дополнительно: слегка затемняем виджеты в режиме редактирования, чтобы сетка была лучше видна */
.widget.editable {
  filter: brightness(0.98);
}
</style>

