<script setup lang="ts">
import {NForm, NFormItem, NInput} from 'naive-ui';
import type {SensorsType} from "../../types/sensors.ts";
import type {ActuatorType} from "../../types/actuators.ts";

const props = defineProps<{
  model: SensorsType | ActuatorType;
  readonly?: boolean;
}>();
</script>

<template>
  <n-form label-width="120px">
    <n-form-item label="Name">
      <n-input
          v-model:value="props.model.name"
          :placeholder="readonly ? '' : 'Enter name'"
          :readonly="props.readonly"
      />
    </n-form-item>

    <n-form-item label="Description">
      <n-input
          v-model:value="props.model.description"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 4 }"
          :placeholder="readonly ? '' : 'Enter description'"
          :readonly="props.readonly"
      />
    </n-form-item>
  </n-form>
</template>
