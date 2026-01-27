<script setup lang="ts">
import {NFormItem, NInputNumber, NSwitch} from 'naive-ui';
import type {ActuatorType} from '../../types/actuators';

const props = defineProps<{ model: ActuatorType }>();
</script>

<template>
  <div style="display: flex; flex-wrap: wrap; gap: 16px; margin-top: 16px;">
    <n-form-item
        label="Pin"
        style="flex: 1 1 120px; min-width: 120px;"
    >
      <n-input-number
          v-model:value="props.model.pin"
          :min="0"
          :max="999"
          placeholder="GPIO"
          size="small"
      />
    </n-form-item>
    <n-form-item
        label="Inverted"
        style="flex: 1 1 100px; min-width: 100px;"
    >
      <n-switch v-model:value="props.model.inverted">
        <template #checked>Yes</template>
        <template #unchecked>No</template>
      </n-switch>
    </n-form-item>
    <n-form-item
        label="Active"
        style="flex: 1 1 110px; min-width: 110px;"
    >
      <n-switch v-model:value="props.model.is_active">
        <template #checked>On</template>
        <template #unchecked>Off</template>
      </n-switch>
    </n-form-item>
  </div>
</template>
