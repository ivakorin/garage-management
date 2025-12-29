<script setup lang="ts">
import {onMounted, ref, watch} from 'vue'
import {NButton, NModal} from 'naive-ui'
import ECharts from 'vue-echarts'
import 'echarts'
import type {EChartsOption} from 'echarts'
import {fetchSensorHistoryAPI} from '../api/devices.ts'
import type {SensorDataReadType} from '../../types/sensors.ts'

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
const isDetailed = ref(false)
let chartOption = ref<EChartsOption>({})

onMounted(() => {
  fetchData()
})

watch(
    () => props.sensorValue,
    (newValue) => {
      if (newValue && newValue.device_id === props.deviceId) {
        const newEntry = {
          timestamp: new Date(newValue.timestamp),
          value: Number(newValue.value),
          unit: newValue.unit
        }
        historyData.value.push(newEntry)
        historyData.value.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
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
      value: Number(item.value),
      unit: item.unit
    }))
    updateChartOption()
  } catch (error) {
    console.error('Failed to load history:', error)
  } finally {
    loading.value = false
  }
}

function filterLast12Hours(data: { timestamp: Date; value: number }[]): {
  timestamp: Date;
  value: number
}[] {
  const now = new Date()
  const cutoff = new Date(now.getTime() - 12 * 60 * 60 * 1000) // 12 часов назад
  return data.filter(item => item.timestamp >= cutoff)
}

function groupByHour(
    data: { timestamp: Date; value: number }[],
    isBoolean: boolean
): { timestamp: Date; value: number }[] {
  const grouped = new Map<string, { values: number[]; timestamps: Date[] }>()

  data.forEach(item => {
    const key = item.timestamp.toISOString().slice(0, 13)
    if (!grouped.has(key)) grouped.set(key, {values: [], timestamps: []})
    grouped.get(key)!.values.push(item.value)
    grouped.get(key)!.timestamps.push(item.timestamp)
  })

  return Array.from(grouped.entries()).map(([key, {values, timestamps}]) => {
    let aggregatedValue: number
    if (isBoolean) {
      // Для boolean: берём последнее значение за час
      aggregatedValue = values[values.length - 1]
    } else {
      // Для числовых: среднее
      aggregatedValue = values.reduce((a, b) => a + b, 0) / values.length
    }
    return {
      timestamp: new Date(`${key}:00:00.000Z`),
      value: aggregatedValue
    }
  })
}

function groupByMinute(data: { timestamp: Date; value: number }[]): {
  timestamp: Date;
  value: number
}[] {
  return data.map(item => ({...item}))
}

function updateChartOption() {
  setTimeout(() => {
    const sampleUnit = historyData.value[0]?.unit || 'unknown'
    const isBoolean = sampleUnit === 'boolean'

    // Фильтруем и группируем в зависимости от режима
    let processedData: { timestamp: Date; value: number }[]
    if (isDetailed.value) {
      // В детализированном режиме — все данные
      processedData = groupByMinute(historyData.value)
    } else {
      // По умолчанию — последние 12 часов, сгруппированные по часам
      const last12h = filterLast12Hours(historyData.value)
      processedData = groupByHour(last12h, isBoolean)
    }

    const values = processedData.map(d => d.value).filter(v => !isNaN(v))
    if (values.length === 0) return // Защищаемся от пустых данных


    let minValue = Math.min(...values)
    let maxValue = Math.max(...values)

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
          const value = isBoolean
              ? (data.value === 1 ? 'On' : 'Off')
              : typeof data.value === 'number' ? data.value.toFixed(2) : data.value
          return `${new Date(data.name).toLocaleString()}<br/>` +
              `Value: ${value} ${sampleUnit}`
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
          data: processedData.map(d => [d.timestamp, d.value]),
          lineStyle: {width: 2},
          itemStyle: {symbol: 'circle', symbolSize: 6},
          smooth: true
        }
      ],
      grid: {left: '10%', right: '5%', bottom: '15%', top: '20%'},
      legend: {data: ['Sensor Data']}
    }
  }, 0)
}

function toggleDetailMode() {
  isDetailed.value = !isDetailed.value
  updateChartOption()
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
        :style="{ width: '800px', 'max-width': '90vw' }"
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

      <div style="margin-top: 24px; display: flex; justify-content: space-between;">
        <n-button @click="toggleDetailMode">
          {{ !isDetailed ? 'Show All Data' : 'Show Last 12h' }}
        </n-button>
        <n-button @click="closeModal">Close</n-button>
      </div>
    </n-card>
  </n-modal>
</template>

<style scoped>
</style>
