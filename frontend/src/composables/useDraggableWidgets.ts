import {ref} from 'vue'
import {fetchLayoutAPI, saveLayoutAPI} from '../api/dashboard'

export interface Widget {
    id: number
    device_id: string
    type: 'plugin' | 'sensor' | 'actuator'
    name: string
    description?: string
    x: number
    y: number
    width: number
    height: number
    data?: Record<string, any>
}

export function useDraggableWidgets() {
    const widgets = ref<Widget[]>([])

    const initLayout = async () => {
        try {
            const saved = await fetchLayoutAPI()
            widgets.value = Array.isArray(saved) ? saved : []
        } catch (error) {
            console.error('Failed to load layout:', error)
            widgets.value = []
        }
    }


    // Add new widget (from sidebar)
    const addWidget = (widgetData: Omit<Widget, 'x' | 'y' | 'width' | 'height'>) => {
        const newWidget: Widget = {
            ...widgetData,
            x: 950 + Math.random() * 100,
            y: 20 + Math.random() * 100,
            width: 200,
            height: 150
        }
        widgets.value.push(newWidget)
    }

    // Remove widget
    const removeWidget = (id: number) => {
        widgets.value = widgets.value.filter(w => w.id !== id)
    }

    // Save current layout to backend
    const saveLayout = async () => {
        console.log(widgets.value)
        try {
            await saveLayoutAPI(widgets.value)
            // Optional: show success notification
        } catch (error) {
            console.error('Failed to save layout:', error)
            // Optional: show error notification
        }
    }

    return {
        widgets,
        addWidget,
        removeWidget,
        saveLayout,
        initLayout
    }
}
