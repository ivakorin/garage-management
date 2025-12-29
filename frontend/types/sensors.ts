type SensorsType = {
    device_id: string
    name: string
    description?: string,
    id: number,
    created_at: string,
    updated_at: string
    timestamp: string
    type: "sensors"
    unit: string
}

type UpdateSensorType = {
    "device_id": string,
    "name"?: string,
    "description"?: string,
    "id": number,
}

type SensorDataReadType = {
    device_id: string
    data: Record<string, number>
    timestamp: string
    value: number
    unit: string
}

export type {SensorsType, UpdateSensorType, SensorDataReadType}