<script setup lang="ts">
import {computed, onMounted, ref} from 'vue'
import {
  NButton,
  NIcon,
  NLayout,
  NLayoutHeader,
  NLayoutSider,
  NTabPane,
  NTabs
} from 'naive-ui'
import {PhFloppyDisk, PhLayout, PhPencil} from '@phosphor-icons/vue'
import {useDraggableWidgets} from '../composables/useDraggableWidgets'
import WidgetCard from './WidgetCard.vue'
import PluginList from "./PluginList.vue";
import DeviceList from "./DeviceList.vue";

// Режимы
const isEditing = ref(false)
const isSiderVisible = ref(false)
const activeTab = ref('devices')

// Виджеты
const {widgets, addWidget, saveLayout, initLayout} = useDraggableWidgets()

// Вычисляемое свойство ширины основной области
const mainContentWidth = computed(() =>
    isSiderVisible.value ? 'calc(100% - 240px)' : '100%')

// Действия с виджетами (без изменений)
const removeWidget = (id: string | number) => {
  if (!isEditing.value) return
  const index = widgets.value.findIndex(w => w.id === id)
  if (index !== -1) widgets.value.splice(index, 1)
}

const updateWidgetPosition = (update: { index: number; x: number; y: number }) => {
  if (!isEditing.value) return
  if (update.index < 0 || update.index >= widgets.value.length) {
    console.warn(`Widget index ${update.index} is out of bounds`)
    return
  }
  const widget = widgets.value[update.index]
  if (!widget) {
    console.error(`Widget at index ${update.index} not found`)
    return
  }
  widget.x = update.x
  widget.y = update.y
}

const updateWidgetSize = (update: { index: number; width: number; height: number }) => {
  if (!isEditing.value) return

  if (update.index < 0 || update.index >= widgets.value.length) {
    console.warn(`Widget index ${update.index} is out of bounds`)
    return
  }

  const widget = widgets.value[update.index]
  if (!widget) {
    console.error(`Widget at index ${update.index} not found`)
    return
  }

  widget.width = update.width
  widget.height = update.height
}
const toggleEditMode = () => {
  isEditing.value = !isEditing.value
  if (!isEditing.value) saveLayout()
}
const toggleSiderVisibility = () => {
  isSiderVisible.value = !isSiderVisible.value
}

onMounted(() => {
  initLayout()
})
</script>

<template>
  <n-layout has-sider>
    <n-layout-header class="header">
      <div class="header-container">
        <div class="header-left">
          <n-button
              text
              :focusable="false"
              @click="toggleSiderVisibility"
              class="sider-toggle-btn"
          >
            <n-icon size="24">
              <PhLayout/>
            </n-icon>
          </n-button>
          <n-tooltip trigger="hover" v-if="!isEditing">
            <template #trigger>
              <n-button
                  text
                  :focusable="false"
                  @click="toggleEditMode"
                  class="edit-icon"
              >
                <n-icon size="20">
                  <PhPencil/>
                </n-icon>
              </n-button>
            </template>
            Switch layout to edit mode
          </n-tooltip>
          <n-button
              v-else
              class="edit-icon"
              text
              @click="toggleEditMode"
          >
            <n-icon size="20">
              <PhFloppyDisk/>
            </n-icon>
          </n-button>
        </div>
        <div class="logo">
          <n-space>
            <n-image
                width="30"
                src="/icon_path.svg"
            />
            <h1>Garage Management</h1>
          </n-space>
        </div>
      </div>
    </n-layout-header>
    <n-layout-sider
        v-show="isSiderVisible"
        bordered
        position="static"
        class="left-sider"
        collapse-mode="width"
    >
      <n-tabs
          v-model:value="activeTab"
          type="line"
          tab-position="right"
          vertical
      >
        <n-tab-pane name="plugins" tab="Plugins">
          <plugin-list @add-widget="addWidget" :is-editing="isEditing"/>
        </n-tab-pane>
        <n-tab-pane name="devices" tab="Devices">
          <device-list @add-widget="addWidget" :is-editing="isEditing"/>
        </n-tab-pane>
      </n-tabs>

    </n-layout-sider>
    <n-layout
        :style="{ width: mainContentWidth }"
        class="main-content"
    >
      <div class="dashboard-grid" :class="{ 'edit-mode': isEditing }">
        <div class="widgets-container">
          <widget-card
              v-for="(widget, index) in widgets"
              :key="widget.id"
              :data="widget"
              :index="index"
              :editable="isEditing"
              @update-position="updateWidgetPosition"
              @update-size="updateWidgetSize"
              @remove="removeWidget(widget.id)"
          />
        </div>
      </div>
    </n-layout>
  </n-layout>
</template>
<style scoped>
.header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 64px;
  background-color: #18a058;
  color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  /* Убираем flex из header, переносим в контейнер */
}

.header-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 16px;
  width: 100%;
  height: 100%;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px; /* Расстояние между кнопками */
}

.logo {
  display: flex;
  align-items: center;
  padding-right: 2%;
}

.logo h1 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

/* Кнопки в шапке */
.sider-toggle-btn,
.edit-icon {
  color: white;
  opacity: 0.9;
  transition: opacity 0.2s, transform 0.2s;
  padding: 8px;
  border-radius: 4px;
}

.sider-toggle-btn:hover,
.sider-toggle-btn:active,
.edit-icon:hover,
.edit-icon:active {
  opacity: 1;
  color: white;
  transform: scale(1.05);
}

/* Адаптация для мобильных */
@media (max-width: 768px) {
  .header-container {
    padding: 0 12px;
  }

  .logo h1 {
    font-size: 1.3rem;
  }

  .header-left {
    gap: 8px;
  }
}

/* Сайдбар */
.left-sider {
  background-color: #ffffff;
  border-right: 1px solid #e0e0e0;
  box-shadow: 2px 0 4px rgba(0, 0, 0, 0.05);
  padding-top: 64px;
  height: calc(100vh - 64px);
  //overflow-y: auto;
  //width: 200px;
  transition: width 0.3s ease-in-out;
}

/* Основная область контента */
.main-content {
  position: relative;
  margin-left: 0;
  height: calc(100vh - 64px);
  overflow: auto;
  background-color: #f8f9fa;
  transition: margin-left 0.3s ease-in-out;
}


/* Сетка dashboard */
.dashboard-grid {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.dashboard-grid.edit-mode {
  height: calc(100vh - 60px);
}

/* Контейнер виджетов */
.widgets-container {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 90vh;
  overflow: auto;
  background-color: #ffffff;
  transition: background-size 0.3s ease;
}

/* Сетка в режиме редактирования */
.dashboard-grid.edit-mode .widgets-container {
  background-image: linear-gradient(
      to right,
      transparent 0,
      transparent calc(var(--grid-size) - 1px),
      rgba(0, 0, 0, 0.1) 0
  ),
  linear-gradient(
      to bottom,
      transparent 0,
      transparent calc(var(--grid-size) - 1px),
      rgba(0, 0, 0, 0.1) 0
  );
  background-size: var(--grid-size) var(--grid-size);
  background-position: 0 0;
  --grid-size: 20px;
  box-sizing: border-box;
}

/* Виджеты */
:deep(.widget:not(.editable)) {
  cursor: default !important;
  //pointer-events: none;
  opacity: 0.95;
  filter: saturate(0.8) brightness(0.98);
  transition: opacity 0.3s ease, filter 0.3s ease, box-shadow 0.2s ease;
}

:deep(.widget.editable) {
  cursor: grab;
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}

:deep(.widget.editable:hover) {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: translateY(-2px);
}

/* Элементы управления виджетом */
:deep(.widget.editable .resize-handles) {
  display: block;
}

:deep(.widget:not(.editable) .resize-handles) {
  display: none !important;
}

:deep(.widget.editable .remove-btn) {
  opacity: 1;
  pointer-events: auto;
}

:deep(.widget:not(.editable) .remove-btn) {
  display: none !important;
}

/* Панель управления */
.controls {
  position: fixed;
  bottom: 16px;
  right: 16px;
  display: flex;
  gap: 8px;
  align-items: center;
  z-index: 1000;
}

/* Вертикальные вкладки */
.vertical-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
}

:deep(.n-tabs-tab) {
  font-size: 14px;
  padding: 12px 16px !important;
  border-right: 3px solid transparent;
  transition: all 0.3s ease;
  color: #444;
  display: flex;
  align-items: center;
}

:deep(.n-tabs-tab.n-tabs-tab--active) {
  border-right-color: #18a058;
  background-color: #f0f8ff;
  font-weight: 500;
  color: #18a058;
}

:deep(.n-tabs-pane-content) {
  overflow-x: hidden;
  overflow-y: auto;
  height: 100%;
  padding: 0 !important;
}

/* Адаптивность для мобильных */
@media (max-width: 768px) {
  .header {
    padding: 0 12px;
    height: 56px;
  }

  .logo h1 {
    font-size: 1.3rem;
  }

  .left-sider {
    width: 200px;
  }

  .main-content-with-sider {
    margin-left: 200px;
  }

  .controls {
    flex-direction: column-reverse;
    align-items: flex-end;
    bottom: 12px;
    right: 12px;
  }

  .dashboard-grid.edit-mode {
    padding-bottom: 90px;
  }
}


/* Плавное скрытие без удаления из DOM */
.left-sider[aria-hidden="true"] {
  width: 0;
  opacity: 0;
  pointer-events: none;
}

/* Для мобильных устройств */
@media (max-width: 768px) {
  .left-sider {
    width: 200px;
  }

  .left-sider[aria-hidden="true"] {
    width: 0;
  }
}

</style>

