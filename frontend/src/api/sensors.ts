import {api} from "../boot/axios.ts";
import type {SensorsType, UpdateSensorType} from "../../types/sensors.ts";

const deleteSensorAPI = async (device_id: string) => {
    const response = await api.delete(`sensors/delete/${device_id}`)
    return response.data
}

const fetchDevicesAPI = async () => {
    const response = await api.get('sensors/get/all')
    return response.data
}


const updateDeviceAPI = async (params: UpdateSensorType) => {
    const response = await api.patch('sensors/update', params)
    return response.data
}

const readDeviceAPI = async (device_id: string): Promise<SensorsType> => {
    const response = await api.get(`sensors/get/${device_id}`)
    return response.data
}


const fetchSensorHistoryAPI = async (device_id: string) => {
    const response = await api.get(`sensors/get/history/${device_id}`)
    return response.data
}

export {
    updateDeviceAPI,
    fetchDevicesAPI,
    readDeviceAPI,
    fetchSensorHistoryAPI,
    deleteSensorAPI
}