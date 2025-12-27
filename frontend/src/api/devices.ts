import {api} from "../boot/axios.ts";

export const fetchDevicesAPI = async () => {
    const response = await api.get('sensors/get')
    return response.data
}
