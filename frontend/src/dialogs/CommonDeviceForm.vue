<script setup lang="ts">
import {defineProps} from 'vue';
import {NForm, NFormItem, NInput} from 'naive-ui';

const props = defineProps<{
  model: { name: string; description: string };
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
