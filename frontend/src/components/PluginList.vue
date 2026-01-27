<script setup lang="ts">
import {ref} from 'vue'
import {fetchPluginsAPI} from '../api/plugins'
import type {PluginsType} from "../../types/plugins.ts";
import FormattedPluginName from "./FormattedPluginName.vue";
import type {Widget} from "../composables/useDraggableWidgets.ts";
import {api} from "../boot/axios.ts";
import {PhArrowsClockwise} from "@phosphor-icons/vue";
import {useMessage} from "naive-ui";

const message = useMessage()

const plugins = ref<PluginsType[]>([])
const loadPlugins = async () => {
  try {
    plugins.value = await fetchPluginsAPI()
  } catch (error) {
    console.error('Failed to load plugins:', error)
  }
}

defineProps<{ isEditing: boolean }>()

const emit = defineEmits<{
  (e: 'add-widget', plugin: Widget): void
}>()
const addToDashboard = (plugin: PluginsType) => {
  const widget: Widget = {
    id: plugin.id,
    device_id: plugin.device_id,
    type: 'plugin',
    name: plugin.class_name,
    x: 0,
    y: 0,
    height: 200,
    width: 200
  }
  emit('add-widget', widget)
}

const updatePlugin = (id: number, is_running: boolean) => {
  const params = {
    id: id,
    is_running: is_running
  }
  api.patch('plugins/update/', params).then(response => {
    const index = plugins.value.findIndex(plugin => plugin.id === id)
    plugins.value[index] = response.data
  })
}

const ReloadPlugins = () => {
  api.post('plugins/reload').then(response => {
        plugins.value = []
        loadPlugins()
        message.success(response.data.message)
      }
  )
}

loadPlugins()
</script>

<template>
  <div class="plugin-list">
    <div>
      <n-tooltip trigger="hover">
        <template #trigger>
          <n-button tertiary circle type="primary" @click="ReloadPlugins">
            <template #icon>
              <n-icon>
                <PhArrowsClockwise/>
              </n-icon>
            </template>
          </n-button>
        </template>
        Reload plugins
      </n-tooltip>
    </div>
    <n-grid
        v-for="plugin in plugins"
        :key="plugin.id"
        class="plugin-item"
        :cols="1"
    >
      <n-grid-item>
        <div>
          <strong>
            <formatted-plugin-name :name="plugin.class_name"/>
          </strong>
          <p> Added: {{ new Date(plugin.created_at).toLocaleDateString() }}</p>
        </div>
      </n-grid-item>
      <n-grid-item>
        <template v-if="plugin.is_running">
          <n-space>
            <n-button
                size="tiny"
                @click="addToDashboard(plugin)"
                type="info"
                v-if="isEditing"
            >
              Add
            </n-button>
            <n-button
                size="tiny"
                type="error"
                @click="updatePlugin(plugin.id, false)"
            >
              Deactivate
            </n-button>
          </n-space>
        </template>
        <template v-else>
          <n-button
              type="primary"
              size="tiny"
              @click="updatePlugin(plugin.id, true)"
          >
            Activate
          </n-button>
        </template>
      </n-grid-item>
    </n-grid>
  </div>
</template>

<style scoped>
.plugin-list {
  padding: 16px;
}

.plugin-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid #eee;
}
</style>
