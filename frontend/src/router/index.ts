import {createRouter, createWebHistory} from 'vue-router';
import MainPage from "../pages/MainPage.vue";

const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: '/',
            name: 'home',
            component: MainPage,
        }
    ]
});

export default router;
