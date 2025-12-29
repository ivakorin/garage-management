<script setup lang="ts">
import {ref} from 'vue'
import {fetchDevicesAPI} from '../api/devices'
import type {SensorsType} from "../../types/sensors.ts";
import type {Widget} from "../composables/useDraggableWidgets.ts";
import {PhPencil} from "@phosphor-icons/vue";
import FormattedPluginName from "./FormattedPluginName.vue";
import EditDevice from "../dialogs/editDevice.vue";

// Состояние
const devices = ref<SensorsType[]>([])
const showModal = ref<boolean>(false)
const isContenLoaded = ref<boolean>(false)
const currentItem = ref<SensorsType | null>(null)

// Загрузка данных
const loadDevices = async () => {
  try {
    devices.value = await fetchDevicesAPI()
    isContenLoaded.value = true
  } catch (error) {
    console.error('Failed to load devices:', error)
  }
}
defineProps<{ isEditing: boolean }>()
// Эмиттер для добавления в дашборд
const emit = defineEmits<{
  (e: 'add-widget', device: Widget): void
}>()

const addToDashboard = (device: SensorsType) => {
  const widget: Widget = {
    id: device.id,
    device_id: device.device_id,
    type: "device",
    name: device.name,
    description: device.description,
    x: 0,
    y: 0,
    width: 200,
    height: 200
  }
  emit('add-widget', widget)
}

const editItem = (item: SensorsType) => {
  currentItem.value = item
  showModal.value = true
}
const onUpdate = (updatedItem: SensorsType) => {
  const index = devices.value.findIndex(i => i.id === updatedItem.id)
  if (index !== -1) {
    devices.value[index] = updatedItem
  }
}

loadDevices()
</script>

<template>
  <div class="device-list">
    <h3>Devices</h3>
    <n-grid
        v-for="device in devices"
        :key="device.id"
        class="device-item"
        :cols="1"
    >
      <n-grid-item>
        <n-p>
          <n-button quaternary @click="editItem(device)" v-if="isEditing">
            <template #icon>
              <n-icon
                  size="20"
              >
                <PhPencil/>
              </n-icon>
            </template>
            <strong class="truncate">
              <formatted-plugin-name :name="device.name"/>
            </strong>
          </n-button>
          <strong class="truncate" v-else>
            <formatted-plugin-name :name="device.name"/>
          </strong>
        </n-p>
        <n-p class="last-seen">Last seen: {{
            new Date(device.timestamp).toLocaleString()
          }}
        </n-p>
      </n-grid-item>
      <n-grid-item>
        <n-button
            size="tiny"
            @click="addToDashboard(device)"
            type="primary"
            v-if="isEditing"
        >
          Add
        </n-button>
      </n-grid-item>
    </n-grid>
  </div>
  <edit-device
      v-if="currentItem"
      v-model:show="showModal"
      :initial-data="currentItem"
      @update="onUpdate"
      @close="showModal = false"
  />

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

.truncate {
  width: 150px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: start;
}


</style>
