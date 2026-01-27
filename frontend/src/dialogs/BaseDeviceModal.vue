<script setup lang="ts">
import {defineEmits, defineProps} from 'vue';
import {NButton, NCard, NModal} from 'naive-ui';

const props = defineProps<{
  show: boolean;
  title: string;
  isLoading?: boolean;
}>();

const emit = defineEmits<{
  (e: 'update', data: any): void;
  (e: 'close'): void;
}>();

const onSave = () => {
  emit('update');
};

const onCancel = () => {
  emit('close');
};
</script>

<template>
  <n-modal v-model:show="props.show" :mask-closable="false" @close="onCancel">
    <n-card
        :style="{ width: '600px', maxWidth: '90vw' }"
        :title="props.title"
        bordered
        role="dialog"
        closeable
        @close="onCancel"
    >
      <slot/>

      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <n-button @click="onCancel" size="tiny">Cancel</n-button>
          <n-button
              type="primary"
              @click="onSave"
              size="tiny"
              :loading="props.isLoading"
          >
            Save
          </n-button>
        </div>
      </template>
    </n-card>
  </n-modal>
</template>
