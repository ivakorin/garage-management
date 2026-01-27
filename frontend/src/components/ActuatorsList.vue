<script setup lang="ts">
import {ref} from "vue";
import {fetchActuatorsAPI, updateActuatorAPI} from "../api/actuators";
import type {ActuatorType} from "../../types/actuators.ts";
import type {Widget} from "../composables/useDraggableWidgets.ts";
import {PhPencil} from "@phosphor-icons/vue";
import FormattedPluginName from "./FormattedPluginName.vue";
import EditActuator from "../dialogs/EditActuator.vue";


// Состояние
const actuators = ref<ActuatorType[]>([]);
const showModal = ref<boolean>(false);
const isContentLoaded = ref<boolean>(false);
const currentItem = ref<ActuatorType | null>(null);


// Загрузка данных
const loadActuators = async () => {
  try {
    actuators.value = await fetchActuatorsAPI();
    isContentLoaded.value = true;
  } catch (error) {
    console.error("Failed to load actuators:", error);
  }
};

defineProps<{ isEditing: boolean }>();


// Эмиттер для добавления в дашборд
const emit = defineEmits<{
  (e: "add-widget", actuator: Widget): void;
}>();

const addToDashboard = (actuator: ActuatorType) => {
  const widget: Widget = {
    id: actuator.id,
    device_id: actuator.device_id,
    type: "actuator",
    name: actuator.name,
    description: actuator.description,
    x: 0,
    y: 0,
    width: 200,
    height: 200,
  };
  emit("add-widget", widget);
};

const editItem = (item: ActuatorType) => {
  currentItem.value = item;
  showModal.value = true;
};

const onUpdate = async (updatedItem: ActuatorType) => {
  try {
    const updated = await updateActuatorAPI(updatedItem);
    const index = actuators.value.findIndex((i) => i.id === updated.id);
    if (index !== -1) {
      actuators.value[index] = updated;
    }
  } catch (error) {
    console.error("Failed to update actuator:", error);
  }
};

loadActuators();
</script>

<template>
  <div class="actuator-list">
    <n-grid
        v-for="actuator in actuators"
        :key="actuator.id"
        class="actuator-item"
        :cols="1"
    >
      <n-grid-item>
        <n-p>
          <n-button quaternary @click="editItem(actuator)" v-if="isEditing">
            <template #icon>
              <n-icon size="20">
                <PhPencil/>
              </n-icon>
            </template>
            <strong class="truncate">
              <formatted-plugin-name :name="actuator.name"/>
            </strong>
          </n-button>
          <strong class="truncate" v-else>
            <formatted-plugin-name :name="actuator.name"/>
          </strong>
        </n-p>
        <n-p class="last-updated">
          Last updated: {{ new Date(actuator.updated_at).toLocaleString() }}
        </n-p>
      </n-grid-item>
      <n-grid-item>
        <n-button
            size="tiny"
            @click="addToDashboard(actuator)"
            type="primary"
            v-if="isEditing"
        >
          Add
        </n-button>
      </n-grid-item>
    </n-grid>
  </div>
  <edit-actuator
      v-if="currentItem"
      v-model:show="showModal"
      :initial-data="currentItem"
      @update="onUpdate"
      @close="showModal = false"
  />
</template>

<style scoped>
.actuator-list {
  padding: 16px;
}

.actuator-item {
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

.last-updated {
  color: #666;
  font-size: 0.8em;
  margin-top: 4px;
}
</style>
