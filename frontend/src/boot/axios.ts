import axios, {type AxiosInstance} from 'axios';
import {config} from "../config";

declare module '@vue/runtime-core' {
    interface ComponentCustomProperties {
        $axios: AxiosInstance;
    }
}
const BaseUrl = config.GM__API__URL;
const api = axios.create({baseURL: BaseUrl, withCredentials: false});
// api.interceptors.request.use(
//   (config) => {
//     const token = localStorage.getItem('access_token');
//     if (token) {
//       config.headers.Authorization = `Bearer ${token}`;
//     }
//     return config;
//   },
//   (error) => {
//     return Promise.reject(error);
//   },
// );
// api.interceptors.response.use(
//   (response) => response,
//   async (error) => {
//     if (error.response?.status === 401) {
//       localStorage.clear();
//       window.location.href = '/';
//     }
//     return Promise.reject(error);
//   },
// );

export {api};
