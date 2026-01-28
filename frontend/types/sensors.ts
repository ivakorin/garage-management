type SensorsType = {
    device_id: string
    name: string
    description?: string,
    id: number,
    created_at: string,
    updated_at: string
    timestamp: string
    value: number | string
    type: "sensors"
    unit: string
    details: Record<string, any>
    online: boolean
}

type UpdateSensorType = {
    "device_id": string,
    "name"?: string,
    "description"?: string,
    "id": number,
}

type SensorDataReadType = {
    device_id: string
    data: Record<string, any>
    timestamp: string
    value: number | string
    unit: string
    online: boolean
}

export type {SensorsType, UpdateSensorType, SensorDataReadType}