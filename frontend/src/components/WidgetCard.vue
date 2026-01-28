<script setup lang="ts">
import {computed, onMounted, onUnmounted, ref, watch} from 'vue'
import type {Widget} from '../composables/useDraggableWidgets'
import FormattedPluginName from './FormattedPluginName.vue'
import {
  PhCheckCircle,
  PhClockClockwise,
  PhMinusCircle,
  PhPencil,
  PhPower
} from '@phosphor-icons/vue'
import EditSensor from '../dialogs/EditSensor.vue'
import {readDeviceAPI} from '../api/sensors.ts'
import type {SensorDataReadType, SensorsType} from '../../types/sensors.ts'
import {SensorWebSocket} from '../ws/webSocket.ts'
import SensorHistoryChart from "../dialogs/SensorHistoryChart.vue"
import unitSymbolsJson from '../misc/measure_units/units.json';
import type {ActuatorType, SensorDataType} from "../../types/actuators.ts";
import {readActuatorAPI, updateActuatorAPI} from "../api/actuators.ts";

onMounted(() => {
  unitSymbols.value = unitSymbolsJson;
});


interface Props {
  data: Widget
  index: number
  editable: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update-position', update: { index: number; x: number; y: number }): void
  (e: 'update-size', update: { index: number; width: number; height: number }): void
  (e: 'remove', id: number): void
}>()

const GRID_SIZE = 20
const roundToGrid = (value: number): number => {
  return Math.round(value / GRID_SIZE) * GRID_SIZE
}

const isDragging = ref(false)
const offsetX = ref(0)
const offsetY = ref(0)
const isResizing = ref(false)
const resizeEdge = ref<'' | 'se' | 'e' | 's'>('')
const startWidth = ref(0)
const startHeight = ref(0)

const sensorData = ref<SensorDataReadType | SensorDataType | null>(null)

const contentLoading = ref<boolean>(true)
const currentItem = ref<SensorsType | ActuatorType | null>(null)
const showModal = ref<boolean>(false)
const showDetails = ref<boolean>(false)
const showHistory = ref<boolean>(false)

let ws: SensorWebSocket | null = null
const unitSymbols = ref<Record<string, string>>({})
const actuatorState = ref<boolean>(false)
onMounted(async () => {

  unitSymbols.value = unitSymbolsJson;

  try {
    currentItem.value = await loadItem()
    contentLoading.value = false
  } catch (error) {
    console.error('Failed to load item:', error)
  }
})

const displayedUnit = computed((): string => {
  const unitKey = sensorData.value?.unit
  if (!unitKey) return ''
  return unitSymbols.value[unitKey] || unitKey
})

const loadItem = async (): Promise<SensorsType | ActuatorType> => {
  let response: SensorsType | ActuatorType;

  if (props.data.type === 'sensor') {
    response = await readDeviceAPI(props.data.device_id);
    sensorData.value = {
      device_id: response.device_id,
      data: response.details,
      timestamp: response.updated_at,
      value: response.value,
      unit: response.details.unit,
      online: response.online
    }
    currentItem.value = response;
    currentItem.value.type = 'sensors'
  } else if (props.data.type === 'actuator') {
    response = await readActuatorAPI(props.data.device_id);
    sensorData.value = {
      device_id: response.device_id,
      timestamp: response.updated_at,
      value: Number(response.is_active),
      unit: "boolean",
      online: response.is_active
    } satisfies SensorDataType
    currentItem.value = response;
    currentItem.value.online = response.is_active
    currentItem.value.type = 'actuators'
    actuatorState.value = response.is_active
  } else {
    throw new Error(`Unsupported device type: ${props.data.type}`);
  }
  // Инициализация WebSocket
  ws = new SensorWebSocket();
  ws.connect();
  ws.subscribe(response.device_id);

  // Подписка на обновления
  ws.onSensorUpdate(response.device_id, (data) => {
    sensorData.value = data;
  });

  // Проверка подписок через 3 секунды
  setTimeout(() => ws?.getSubscriptions(), 3000);

  return response;
};


const onUpdate = () => loadItem()
const editItem = () => showModal.value = true
const toggleDetails = () => {
  showDetails.value = true
}
const handleRemove = () => props.editable && emit('remove', props.data.id)

const onMousedown = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (
      target.classList.contains('details-btn') ||
      target.classList.contains('resize-handle')
  ) {
    return
  }

  if (!props.editable) return

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

  newWidth = roundToGrid(newWidth)
  newHeight = roundToGrid(newHeight)
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

const openHistory = () => {
  showHistory.value = true
}

onUnmounted(() => {
  if (ws) {
    ws.disconnect()
    ws = null
  }
  document.removeEventListener('mousemove', onMousemove)
  document.removeEventListener('mouseup', onMouseup)
  document.removeEventListener('mousemove', onResizeMousemove)
  document.removeEventListener('mouseup', onResizeMouseup)
})
const statusActive = computed(() => {
  if (currentItem.value) {
    if (currentItem.value.type === 'sensors') {
      return currentItem.value.online
    } else if (currentItem.value.type === 'actuators') {
      return currentItem.value.is_active
    }
  }
  return false
})
const switchActuator = async () => {
  if (currentItem.value) {
    await updateActuatorAPI({
      device_id: currentItem.value.device_id,
      is_active: actuatorState.value
    })
    currentItem.value.is_active = actuatorState.value
  }
}
watch(actuatorState, () => {
  switchActuator()
})

const statusColor = computed(() => statusActive.value ? 'green' : 'red')
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
    <div v-if="contentLoading" class="skeleton-overlay">
      <n-skeleton height="100%" width="100%" :sharp="false"/>
    </div>
    <div v-else-if="currentItem" class="widget-content-wrapper">

      <div class="widget-header">
        <h4
            class="widget-title"
            v-if="currentItem.type === 'sensors' || currentItem.type === 'actuators'"
        >
          <n-icon :size="16" :color="statusColor">
            <PhCheckCircle v-if="statusActive"/>
            <PhMinusCircle v-else/>
          </n-icon>
          <n-button
              v-if="editable"
              quaternary
              @click="editItem"
          >
            <template #icon>
              <n-icon size="20">
                <PhPencil/>
              </n-icon>
            </template>
            <strong class="truncate">
              <formatted-plugin-name :name="currentItem.name"/>
            </strong>
          </n-button>

          <formatted-plugin-name
              v-else
              :name="currentItem.name"
          />
          <span
              class="status-icon"
              :class="currentItem.online ? 'online' : 'offline'"
              v-if="currentItem.name"
          >
          </span>
        </h4>
        <button
            v-if="editable"
            class="remove-btn"
            @click="handleRemove">
          ×
        </button>
      </div>


      <div class="widget-content">
        <div v-if="sensorData?.timestamp"
             style="font-size: smaller; text-align: left; width: 100%">
          <n-icon :component="PhClockClockwise"/>
          {{ new Date(sensorData.timestamp).toLocaleString() }}
        </div>
        <div class="main-display" v-if="currentItem.type==='sensors'">
          <div class="value">
            {{
              (typeof sensorData?.value === 'number' && !isNaN(sensorData.value))
                  ? sensorData.value.toFixed(2)
                  : (typeof sensorData?.value === 'string')
                      ? sensorData.value
                      : '—'
            }}
          </div>
          <div v-if="displayedUnit" class="unit">{{
              (typeof sensorData?.value === 'number' && !isNaN(sensorData.value)) ? displayedUnit : ''
            }}
          </div>
        </div>
        <div class="main-display" v-if="currentItem.type==='actuators'">
          <n-switch v-model:value="actuatorState">
            <template #icon>
              <n-icon
                  :component="PhPower"
                  :color="actuatorState ?'green': 'red'"
                  size="large"
              />
            </template>
            <template #checked>
              On
            </template>
            <template #unchecked>
              Off
            </template>
          </n-switch>
        </div>
        <n-space>
          <n-button
              @click="toggleDetails"
              type="info"
              size="tiny"
          >
            Details
          </n-button>
          <n-button
              type="primary"
              size="tiny"
              @click="openHistory"
          >
            History
          </n-button>
        </n-space>
        <n-modal
            v-model:show="showDetails"
            preset="card"
            title="Sensor Details"
            :bordered="false"
            :mask-closable="true"
            :close-on-esc="true"
            :style="{ width: '600px' }"
        >
          <n-space vertical :size="12">
            <n-card title="Main Data">
              <n-descriptions
                  :column="1"
                  size="medium"
              >
                <n-descriptions-item label="Device ID">
                  {{ sensorData?.device_id || '—' }}
                </n-descriptions-item>
                <n-descriptions-item label="Value">
                  <template v-if="currentItem.type==='sensors'">
                    {{
                      (typeof sensorData?.value === 'number' && !isNaN(sensorData.value))
                          ? sensorData.value.toFixed(2)
                          : (typeof sensorData?.value === 'string')
                              ? sensorData.value
                              : '—'
                    }}
                  </template>
                  <template v-if="currentItem.type === 'actuators'">
                    <n-icon :component="PhPower" size="20"
                            :color="currentItem.is_active ?'green': 'red'"/>
                  </template>
                </n-descriptions-item>
                <n-descriptions-item label="Unit">
                  {{ sensorData?.unit || '—' }}
                </n-descriptions-item>
              </n-descriptions>
            </n-card>
            <n-card title="Last Update">
              {{
                sensorData?.timestamp ? new Date(sensorData.timestamp).toLocaleString() : '—'
              }}
            </n-card>
            <n-card title="Sensor Data" v-if="currentItem.type==='sensors'">
              <n-list>
                <n-list-item
                    v-for="(value, key) in Object.entries(sensorData?.data || {})"
                    :key="`${key}-${sensorData?.timestamp}`"
                >
                  {{
                    value[0] == 'unit' ? `Measure unit: ${value[1]}` : `Sensor: ${value[0]}, value: ${value[1]}`
                  }}
                </n-list-item>
              </n-list>
            </n-card>
          </n-space>
          <div style="margin-top: 16px; text-align: right;">
            <n-button @click="showDetails = false">Close</n-button>
          </div>
        </n-modal>
        <sensor-history-chart
            :device-id="currentItem?.device_id || ''"
            v-model="showHistory"
            :device-name="currentItem?.name || ''"
            :sensor-value="sensorData"
            @close="showHistory = false"
        />
      </div>
      <template v-if="editable">
        <div
            class="resize-handle se"
            @mousedown.prevent="onResizeMousedown('se')"
        />
        <div
            class="resize-handle e"
            @mousedown.prevent="onResizeMousedown('e')"
        />
        <div
            class="resize-handle s"
            @mousedown.prevent="onResizeMousedown('s')"
        />
      </template>
    </div>
    <edit-sensor
        v-if="currentItem"
        v-model:show="showModal"
        :initial-data="currentItem"
        @update="onUpdate"
        @close="showModal = false"
        :type="currentItem.type"
    />
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
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif;
}

.widget:not(.editable) {
  cursor: default !important;
  opacity: 0.95;
  filter: saturate(0.8) brightness(0.98);
  /* Убрано pointer-events: none */
}

.widget.editable:active,
.widget.editable.dragging {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  transform: scale(1.02);
  z-index: 1000;
}

.widget-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background-color: #f8f9fa;
  border-bottom: 1px solid #e0e0e0;
  gap: 8px;
}

.widget-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #333;
  display: flex;
  align-items: center;
  gap: 8px;
}

.remove-btn {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: #666;
  width: 24px;
  height: 24px;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  transition: all 0.2s ease;
}

.remove-btn:hover {
  color: #d93025;
  background-color: #ffeeed;
}

.widget-content {
  padding: 16px;
  color: #555;
  font-size: 13px;
  line-height: 1.5;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

/* Главное отображение значения */
.main-display {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 8px;
  margin-bottom: 12px;
}

.value {
  font-size: 36px;
  font-weight: bold;
  color: #2c3e50;
  line-height: 1;
}

.unit {
  font-size: 18px;
  color: #7f8c8d;
  font-weight: 500;
}


/* Ручки изменения размера */
.resize-handle {
  position: absolute;
  background-color: transparent;
  cursor: se-resize;
  opacity: 0;
  transition: opacity 0.2s ease, background-color 0.2s ease;
  border-radius: 50%;
}

.widget.editable:hover .resize-handle {
  opacity: 1;
}

.resize-handle.se {
  width: 12px;
  height: 12px;
  bottom: -6px;
  right: -6px;
  background-color: #18a058;
  z-index: 1100;
}

.resize-handle.e {
  width: 6px;
  height: calc(100% - 12px);
  top: 6px;
  right: -3px;
  background-color: #18a058;
  z-index: 1100;
}

.resize-handle.s {
  height: 6px;
  width: calc(100% - 12px);
  bottom: -3px;
  left: 6px;
  background-color: #18a058;
  z-index: 1100;
}

/* Скелетон загрузки */
.skeleton-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(2px);
  z-index: 1;
  border-radius: inherit;
}

/* Плавное переключение между скелетоном и контентом */
.skeleton-overlay,
.widget-content-wrapper {
  transition: opacity 0.3s ease;
}

.widget[contentLoading="true"] .widget-content-wrapper {
  opacity: 0;
  pointer-events: none;
}

.widget:not([contentLoading="true"]) .skeleton-overlay {
  opacity: 0;
  pointer-events: none;
}

/* Стили для компонентов Naive UI */
:deep(.n-button) {
  min-height: auto;
  padding: 4px 8px;
}

:deep(.n-card) {
  border-radius: 8px;
  box-shadow: none;
}

:deep(.n-card__header) {
  padding: 12px 16px;
  background-color: #f8f9fa;
  border-bottom: 1px solid #e0e0e0;
}

:deep(.n-card__content) {
  padding: 16px;
}

:deep(.n-descriptions) {
  line-height: 1.6;
}

:deep(.n-descriptions-item__label) {
  font-weight: 500;
  color: #555;
}

:deep(.n-list-item) {
  padding: 8px 0;
  border-bottom: 1px solid #eee;
}

:deep(.n-modal-body-wrapper) {
  padding: 16px !important;
}
</style>

