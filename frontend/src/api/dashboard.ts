import type {Widget} from "../composables/useDraggableWidgets.ts";
import {api} from "../boot/axios.ts";

export const fetchLayoutAPI = async (): Promise<Widget[]> => {
    const response = await api.get('layouts/get')
    return response.data.layout
}

export const saveLayoutAPI = async (layout: Widget[]): Promise<void> => {
    await api.patch('layouts/save', {layout})
}
