type SensorsType = {
    device_id: string
    name: string
    description?: string,
    id: number,
    created_at: string,
    updated_at: string
    timestamp: string
    type: "sensors"
}

type UpdateSensorType = {
    "device_id": string,
    "name"?: string,
    "description"?: string,
    "id": number,
}

export type {SensorsType, UpdateSensorType}