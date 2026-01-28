export type ActuatorType = {
    type: "actuators"
    device_id: string;
    name: string;
    description: string;
    pin: number;
    inverted: boolean;
    is_active: boolean;
    id: number;
    created_at: string;
    updated_at: string;
    unit: string
    value: boolean
    timestamp: string
    online?: boolean
};

export type SensorDataType = {
    device_id: string
    timestamp: string
    value: number
    unit: string
    online: boolean
}

export type UpdateActuatorType = Partial<Omit<ActuatorType, "id" | "created_at" | "updated_at">>;
