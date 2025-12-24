import { createRouter, createWebHistory } from 'vue-router';
import Chart from "../components/Chart.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: Chart
    }
  ]
});

export default router;
