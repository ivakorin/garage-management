export type ActuatorType = {
    device_id: string;
    name: string;
    description: string;
    pin: number;
    inverted: boolean;
    is_active: boolean;
    id: number;
    created_at: string; // ISO-строка
    updated_at: string;  // ISO-строка
};

export type UpdateActuatorType = Partial<Omit<ActuatorType, "id" | "device_id" | "created_at" | "updated_at">>;
