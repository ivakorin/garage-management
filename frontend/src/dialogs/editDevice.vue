<script setup lang="ts">
import {ref, watch} from 'vue'
import {NButton, NCard, NForm, NFormItem, NInput, NModal, useMessage} from 'naive-ui'
import type {SensorsType} from "../../types/sensors.ts";
import {updateDeviceAPI} from "../api/devices.ts";
import type {Widget} from "../composables/useDraggableWidgets.ts";

const props = defineProps<{
  show: boolean
  initialData: SensorsType | Widget
}>()

const emit = defineEmits<{
  (e: 'update', data: SensorsType): void
  (e: 'close'): void
}>()

const editedData = ref({...props.initialData})
const message = useMessage()

watch(
    () => props.initialData,
    (newVal) => {
      editedData.value = {...newVal}
    }
)
const close = () => {
  emit('close')
}
const confirm = () => {
  updateDeviceAPI(editedData.value).then(response => {
    emit('update', response)
    message.success(`Device ${response.name} have been updated`)
    close()
  })
}
</script>

<template>
  <n-modal v-model:show="props.show" @close="close">
    <n-card
        style="width: 600px; max-width: 90vw;"
        title="Редактирование элемента"
        :bordered="false"
        role="dialog"
        closeable
        @close="close"
    >
      <n-form label-width="120px">
        <n-form-item label="Name">
          <n-input
              v-model:value="editedData.name"
              placeholder="Enter sensor name"
          />
        </n-form-item>

        <n-form-item label="Description">
          <n-input
              v-model:value="editedData.description"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 4 }"
              placeholder="Enter description"
          />
        </n-form-item>
      </n-form>

      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <n-button @click="close" size="tiny">Cancel</n-button>
          <n-button type="primary" @click="confirm" size="tiny">Save</n-button>
        </div>
      </template>
    </n-card>
  </n-modal>
</template>
