<script setup lang="ts">
import { ref, onMounted } from 'vue';
import * as echarts from 'echarts';
import {useI18n} from "vue-i18n";  // Исправленный импорт

const chartRef = ref<HTMLElement | null>(null);
const {t} =  useI18n();

onMounted(() => {
  if (!chartRef.value) return;
  const chart = echarts.init(chartRef.value);
  chart.setOption({
    title: { text: t('welcome') },
    xAxis: { type: 'category', data: ['A', 'B', 'C'] },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: [10, 20, 30] }]
  });
});
</script>

<template>
  <n-button>{{$t('hello')}}</n-button>
  <div ref="chartRef" style="width: 100%; height: 400px;"></div>
</template>
