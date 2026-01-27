<!-- EditActuator.vue -->
<script setup lang="ts">
import type {ActuatorType} from '../../types/actuators';
import BaseDeviceModal from './BaseDeviceModal.vue';
import CommonDeviceForm from './CommonDeviceForm.vue';
import ActuatorSpecificForm from './ActuatorSpecificForm.vue';

const props = defineProps<{ show: boolean; initialData: ActuatorType }>();
const emit = defineEmits<{
  (e: 'update', data: ActuatorType): void;
  (e: 'close'): void
}>();

const save = () => {
  emit('update', props.initialData);
  emit('close');
};
</script>

<template>
  <base-device-modal
      :show="props.show"
      title="Edit Actuator"
      @update="save"
      @close="emit('close')"
  >
    <common-device-form :model="props.initialData"/>
    <actuator-specific-form :model="props.initialData"/>
  </base-device-modal>
</template>
