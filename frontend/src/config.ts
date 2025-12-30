const DEFAULT_API_URL = 'http://127.0.0.1:8000/api/v1';
const DEFAULT_WS_URL = 'ws://127.0.0.1:8000/api/v1/ws';

// @ts-ignore
export const config = {
    GM__API__URL:
        import.meta.env.VITE_GM__API__URL ||
        window._env?.API_URL ||
        DEFAULT_API_URL,

    GM__WS__URL:
        import.meta.env.VITE_GM__WS__URL ||
        window._env?.WS_URL ||
        DEFAULT_WS_URL
};
