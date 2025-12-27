<script setup lang="ts">


import {api} from "../boot/axios.ts";
import Dashboard from "../components/Dashboard.vue";

const GetPlugins = () => {
  api.get('/plugins/get')
      .then(response => {
        console.log(response)
      })
}

</script>

<template>
  <dashboard/>
</template>

<style scoped>

</style>