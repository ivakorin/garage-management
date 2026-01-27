<!-- EditSensor.vue -->
<script setup lang="ts">
import {ref, watch} from 'vue';
import {useMessage} from 'naive-ui';
import type {SensorsType} from '../../types/sensors';
import {updateDeviceAPI} from '../api/sensors';
import BaseDeviceModal from './BaseDeviceModal.vue';
import CommonDeviceForm from './CommonDeviceForm.vue';
import type {ActuatorType} from "../../types/actuators.ts";


const props = defineProps<{ show: boolean; initialData: SensorsType | ActuatorType }>();
const emit = defineEmits<{
  (e: 'update', data: SensorsType): void;
  (e: 'close'): void
}>();

const editedData = ref({...props.initialData});
const isLoading = ref(false);
const message = useMessage();

watch(() => props.initialData, (newVal) => {
  editedData.value = {...newVal};
});

const save = async () => {
  isLoading.value = true;
  try {
    const response = await updateDeviceAPI(editedData.value);
    emit('update', response);
    message.success(`Device ${response.name} updated`);
  } catch (err) {
    message.error('Failed to update device');
  } finally {
    isLoading.value = false;
  }
};
</script>

<template>
  <base-device-modal
      :show="props.show"
      title="Редактирование сенсора"
      :is-loading="isLoading"
      @update="save"
      @close="emit('close')"
  >
    <common-device-form :model="editedData"/>
  </base-device-modal>
</template>
