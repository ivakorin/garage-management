<script setup lang="ts">
import {onMounted, onUnmounted, ref, watch} from 'vue'
import * as echarts from 'echarts'
import {useMessage} from 'naive-ui'
import {useI18n} from "vue-i18n";

const message = useMessage()
const {t} = useI18n();

const devices = ref({})
const selectedDevice = ref('')
const showModal = ref(false)
const chartRef = ref(null)
let chartInstance = null

const ws = ref<WebSocket | null>(null)
const isConnected = ref<boolean>(false)

const connectWS = async () => {
  ws.value = new WebSocket('ws://127.0.0.1:8000/api/v1/ws') // замените на ваш URL

  ws.value.onopen = () => {
    message.success(t('websocket.connected'))
    sendMessage('test')
  }

  ws.value.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      addDataToDevice(data)
    } catch (e) {
      console.error(t('websocket.parsingError'), e)
    }
  }

  ws.value.onclose = () => {
    message.error(t('websocket.closed'))
  }

  ws.value.onerror = (err) => {
    message.error(t('websocket.wsError') + err.message)
  }
}
const disconnectWS = () => {
  if (ws.value && ws.value.readyState !== WebSocket.CLOSED) {
    ws.value.close()
  }
  isConnected.value = false
  ws.value = null
}

const sendMessage = (data: string | object) => {
  if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
    console.error(t('websocket.notReady'))
    return
  }

  // Если отправляем объект — конвертируем в JSON
  const message = typeof data === 'object'
      ? JSON.stringify(data)
      : data

  ws.value.send(message)
}


onMounted(() => {
  connectWS()
})

onUnmounted(() => {
  disconnectWS()
})

// Добавление данных в хранилище
function addDataToDevice(packet) {
  const {device_id, timestamp, value, data} = packet


  if (!devices.value[device_id]) {
    devices.value[device_id] = []
  }

  // Для бинарных датчиков (leak: true/false) берём 1/0
  const numericValue = value !== null ? value : (data.leak ? 1 : 0)

  devices.value[device_id].push({
    timestamp: new Date(timestamp).getTime(), // для ECharts нужен timestamp в мс
    value: numericValue
  })

  // Ограничиваем историю (например, 100 последних значений)
  if (devices.value[device_id].length > 100) {
    devices.value[device_id].shift()
  }
}

// Показ графика по клику
function showChart(deviceId) {
  selectedDevice.value = deviceId
  showModal.value = true
  drawChart(deviceId)
}

// Рисование графика
function drawChart(deviceId) {
  if (!chartRef.value) return

  // Очищаем предыдущий график
  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = echarts.init(chartRef.value)

  const seriesData = devices.value[deviceId].map(item => [
    item.timestamp,
    item.value
  ])

  const option = {
    title: {
      text: `Данные датчика: ${deviceId}`
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const date = new Date(params[0].value[0])
        return `${date.toLocaleString()}<br/>Значение: ${params[0].value[1]}`
      }
    },
    xAxis: {
      type: 'time',
      name: 'Время'
    },
    yAxis: {
      type: 'value',
      name: 'Значение'
    },
    series: [
      {
        name: 'Значение',
        type: 'line',
        data: seriesData,
        smooth: true,
        symbol: 'none'
      }
    ],
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    }
  }

  chartInstance.setOption(option)

  // Обновление при изменении данных
  watch(
      () => devices.value[deviceId],
      () => {
        const newData = devices.value[deviceId].map(item => [item.timestamp, item.value])
        chartInstance.setOption({series: [{data: newData}]})
      }
  )
}
</script>
<template>
  <n-message-provider>
    <n-space vertical>
      <n-card title="Устройства">
        <n-button
            v-for="device in Object.keys(devices)"
            :key="device"
            type="primary"
            quaternary
            @click="showChart(device)"
            style="margin: 5px"
        >
          {{ device }}
        </n-button>
      </n-card>

      <!-- ПЕРЕДАЁМ title ПРЯМО В n-modal -->
      <n-modal
          v-model:show="showModal"
          :title="`График: ${selectedDevice}`"
          style="width: 80vw; max-width: 1000px; height: 60vh;"
      >
        <div ref="chartRef" style="width: 100%; height: 100%;"></div>
      </n-modal>
    </n-space>
  </n-message-provider>
</template>


<style scoped>
.n-card {
  margin-bottom: 16px;
}

/* Явные стили для модального окна */
.n-modal {
  z-index: 1000 !important; /* Выше стандартных элементов */
}

.n-modal__content {
  position: relative !important;
  max-width: 100% !important;
  height: 60vh !important;
}
</style>

