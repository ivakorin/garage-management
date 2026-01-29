import {api} from "../boot/axios.ts";
import type {ActuatorType, UpdateActuatorType} from "../../types/actuators.ts";

const fetchActuatorsAPI = async (): Promise<ActuatorType[]> => {
    const response = await api.get("actuators/get/all");
    return response.data;
};

const updateActuatorAPI = async (params: UpdateActuatorType): Promise<ActuatorType> => {
    const response = await api.patch("actuators/update", params);
    return response.data;
};

const switchActuatorAPI = async (params: {
    device_id: string,
    switch: boolean
}): Promise<boolean> => {
    const response = await api.patch(
        `actuators/switch/${encodeURIComponent(params.device_id)}`,
        null,
        {
            params: {
                switch: params.switch
            },
        }
    );
    return response.data;
};


const readActuatorAPI = async (device_id: string): Promise<ActuatorType> => {
    const response = await api.get(`actuators/get/${device_id}`);
    return response.data;
};

export {fetchActuatorsAPI, updateActuatorAPI, readActuatorAPI, switchActuatorAPI};
