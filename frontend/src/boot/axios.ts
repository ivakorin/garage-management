import axios, {type AxiosInstance} from 'axios';

declare module '@vue/runtime-core' {
    interface ComponentCustomProperties {
        $axios: AxiosInstance;
    }
}
const BaseUrl = 'http://127.0.0.1:8000/api/v1';
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
