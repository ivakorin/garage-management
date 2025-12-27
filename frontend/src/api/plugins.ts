import {api} from "../boot/axios.ts";

export const fetchPluginsAPI = async () => {
    const response = await api.get('/plugins/get')
    return response.data
}
