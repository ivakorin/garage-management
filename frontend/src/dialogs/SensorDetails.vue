<script setup lang="ts">
import {defineProps, ref, watch} from 'vue'

interface SensorData {
  device_id: string
  data: Record<string, number>
  timestamp: string
  value: number
  unit: string
}

interface Props {
  sensorData: SensorData | null
  visible: boolean
}

const props = defineProps<Props>()

const isOpen = ref(false)

// Синхронизируем локальное состояние с пропсом visible
watch(
    () => props.visible,
    (newValue) => {
      isOpen.value = newValue
    }
)

const closeModal = () => {
  isOpen.value = false
  // Эмиттим событие для родительского компонента
  emit('update:visible', false)
}

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()
</script>

<template>
  <n-modal
      v-model:show="isOpen"
      preset="card"
      title="Sensor Details"
      :bordered="false"
      :mask-closable="true"
      :close-on-esc="true"
      :style="{ width: '600px' }"
      @after-leave="closeModal"
  >
    <n-space vertical :size="12">
      <!-- Последнее обновление -->
      <n-card title="Last Update">
        {{
          sensorData?.timestamp ? new Date(sensorData.timestamp).toLocaleString() : '—'
        }}
      </n-card>

      <!-- Основные данные -->
      <n-card title="Main Data">
        <n-descriptions :column="1" size="medium">
          <n-descriptions-item label="Value">
            {{ sensorData?.value?.toFixed(2) || '—' }}
          </n-descriptions-item>
          <n-descriptions-item label="Unit">
            {{ sensorData?.unit || '—' }}
          </n-descriptions-item>
          <n-descriptions-item label="Device ID">
            {{ sensorData?.device_id || '—' }}
          </n-descriptions-item>
        </n-descriptions>
      </n-card>

      <!-- Все данные сенсора в виде списка -->
      <n-card title="Sensor Data">
        <n-list>
          <n-list-item
              v-for="(value, key) in Object.entries(sensorData?.data || {})"
              :key="`${key}-${sensorData?.timestamp}`"
          >
            <template #prefix>{{ key }}:</template>
            {{ Number.isFinite(value) ? value.toFixed(2) : value }}
          </n-list-item>
        </n-list>
      </n-card>
    </n-space>

    <!-- Кнопка закрытия -->
    <div style="margin-top: 16px; text-align: right;">
      <n-button @click="closeModal">Close</n-button>
    </div>
  </n-modal>
</template>

<style scoped>
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
