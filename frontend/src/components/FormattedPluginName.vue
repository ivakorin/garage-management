<script setup lang="ts">
import {computed} from 'vue'

const props = defineProps<{ name: string }>()

const displayName = computed(() => {
  if (!props.name) return ''

  // 1. Удаляем 'Plugin' в конце
  let cleaned = props.name.replace(/Plugin$/, '')

  // 2. Вставляем пробел перед заглавной буквой, если:
  //    - перед ней строчная буква (aA → a A)
  //    - перед ней цифра (1A → 1 A)
  // Но НЕ если перед ней уже заглавная буква (AB → оставляем как есть)
  cleaned = cleaned.replace(
      /(?<=[a-z0-9])(?=[A-Z][a-z])/g,  // lookbehind: [a-z0-9], lookahead: [A-Z][a-z]
      ' '
  )

  // 3. Дополнительно: разбиваем переходы от букв к цифрам (опционально)
  // cleaned = cleaned.replace(/(?<=[a-zA-Z])(?=\d)/g, ' ')


  return cleaned
})
</script>

<template>
  <span>{{ displayName }}</span>
</template>
