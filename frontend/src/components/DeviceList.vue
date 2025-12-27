<script setup lang="ts">
import {ref} from 'vue'
import {fetchDevicesAPI} from '../api/devices'
import type {SensorsType} from "../../types/sensors.ts";

// Состояние
const devices = ref<SensorsType[]>([])

// Загрузка данных
const loadDevices = async () => {
  try {
    devices.value = await fetchDevicesAPI()
  } catch (error) {
    console.error('Failed to load devices:', error)
  }
}

// Эмиттер для добавления в дашборд
const emit = defineEmits<{
  (e: 'add-widget', device: SensorsType): void
}>()

const addToDashboard = (device: SensorsType) => {
  emit('add-widget', device)
}
loadDevices()
</script>

<template>
  <div class="device-list">
    <h3>Devices</h3>
    <div
        v-for="device in devices"
        :key="device.id"
        class="device-item"
    >
      <div>
        <strong>{{ device.name }}</strong>
        <p>Last seen: {{ new Date(device.timestamp).toLocaleString() }}</p>
      </div>
      <n-button size="small" @click="addToDashboard(device)" type="primary">
        Add to Dashboard
      </n-button>
    </div>
  </div>
</template>

<style scoped>
.device-list {
  padding: 16px;
}

.device-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid #eee;
}
</style>
