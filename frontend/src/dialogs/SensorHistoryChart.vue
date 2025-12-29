<script setup lang="ts">
import {onMounted, ref, watch} from 'vue'
import {NButton, NModal} from 'naive-ui'
import ECharts from 'vue-echarts'
import 'echarts'
import type {EChartsOption} from 'echarts'
import {fetchSensorHistoryAPI} from '../api/devices.ts'
import type {SensorDataReadType} from "../../types/sensors.ts";

const props = defineProps<{
  deviceId: string
  deviceName: string
  modelValue: boolean
  sensorValue: SensorDataReadType | null
}>()

const emit = defineEmits(['update:modelValue'])

const loading = ref(true)
const historyData = ref<{
  timestamp: Date
  value: number
  unit: string
}[]>([])

let chartOption = ref<EChartsOption>({})

onMounted(() => {
  fetchData()
})

// НОВЫЙ: следим за изменениями sensorValue от родителя
watch(
    () => props.sensorValue,
    (newValue) => {
      if (newValue && newValue.device_id === props.deviceId) {
        const newEntry = {
          timestamp: new Date(newValue.timestamp),
          value: newValue.value,
          unit: newValue.unit
        }
        // Добавляем новую точку в историю
        historyData.value.push(newEntry)
        // Сортируем по времени
        historyData.value.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
        // Обновляем график
        updateChartOption()
      }
    },
    {deep: true}
)


async function fetchData() {
  loading.value = true
  try {
    const response = await fetchSensorHistoryAPI(props.deviceId)
    historyData.value = response.map((item: any) => ({
      timestamp: new Date(item.timestamp),
      value: item.value,
      unit: item.unit
    }))
    updateChartOption()
  } catch (error) {
    console.error('Failed to load history:', error)
  } finally {
    loading.value = false
  }
}


function updateChartOption() {
  const sampleUnit = historyData.value[0]?.unit || 'unknown'
  const isBoolean = sampleUnit === 'boolean'

  // Вычисляем min и max из historyData
  const values = historyData.value.map(d => d.value)
  let minValue = Math.min(...values)
  let maxValue = Math.max(...values)

  // Добавляем небольшой отступ (5% от диапазона)
  const padding = (maxValue - minValue) * 0.05
  minValue -= padding
  maxValue += padding

  let yAxisConfig: any = {
    type: 'value',
    name: `Value (${sampleUnit})`,
    splitLine: {show: true},
    min: minValue.toFixed(2),
    max: maxValue.toFixed(2)
  }

  if (isBoolean) {
    yAxisConfig = {
      ...yAxisConfig,
      min: 0,
      max: 1,
      interval: 1,
      axisLabel: {
        formatter: (value: number) => value === 1 ? 'On' : 'Off'
      }
    }
  }

  chartOption.value = {
    title: {text: props.deviceName, left: 'center'},
    backgroundColor: '#ffffff',
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const data = params[0]
        return `${new Date(data.name).toLocaleString()}<br/>` +
            `Value: ${data.value} ${sampleUnit}`
      }
    },
    xAxis: {
      type: 'time',
      name: 'Time',
      splitLine: {show: false}
    },
    yAxis: yAxisConfig,
    series: [
      {
        name: 'Sensor Data',
        type: 'line',
        data: historyData.value.map(d => [d.timestamp, d.value]),
        lineStyle: {width: 2},
        itemStyle: {symbol: 'circle', symbolSize: 6},
        smooth: true
      }
    ],
    grid: {left: '10%', right: '5%', bottom: '15%', top: '20%'},
    legend: {data: ['Sensor Data']}
  }
}


function closeModal() {
  emit('update:modelValue', false)
}
</script>

<template>
  <n-modal
      :show="props.modelValue"
      :mask-closable="true"
      :close-on-esc="true"
  >
    <n-card
        :style="{ width: '800px', 'max-width': '90vw'}"
    >
      <div
          v-if="loading"
          style="
          display: flex;
          justify-content: center;
          align-items: center;
          height: 300px;
        "
      >
        Loading data...
      </div>

      <ECharts
          v-else
          :option="chartOption"
          :style="{ width: '100%', height: '400px' }"
      />

      <div style="margin-top: 24px; text-align: right;">
        <n-button @click="closeModal">Close</n-button>
      </div>
    </n-card>
  </n-modal>
</template>

<style scoped>
</style>
