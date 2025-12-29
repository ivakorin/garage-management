class SensorWebSocket {
    private url: string;
    private socket: WebSocket | null = null;
    private messageHandlers: Map<string, (data: any) => void> = new Map();
    private isConnected: boolean = false;
    private reconnectDelay: number = 1000;
    private _pendingSubscriptions: Set<string> | null = null;

    constructor(url: string = "ws://127.0.0.1:8000/api/v1/ws") {
        this.url = url;
    }

    async connect(): Promise<void> {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            return;
        }

        this.socket = new WebSocket(this.url);

        this.socket.onopen = () => {
            this.isConnected = true;
            this._resubscribeAll();
        };

        this.socket.onmessage = (event: MessageEvent) => {
            try {
                const data = JSON.parse(event.data as string);
                this._handleMessage(data);
            } catch (error) {
                console.error("Failed to parse message:", error, event.data);
            }
        };

        this.socket.onclose = () => {
            this.isConnected = false;
            setTimeout(() => this.connect(), this.reconnectDelay);
        };

        this.socket.onerror = (err: Event) => {
            console.error("WebSocket error:", err);
        };
    }

    subscribe(sensorId: string): void {
        if (!this.isConnected || !this.socket) {
            console.warn("WebSocket not ready. Will subscribe after connection.");
            if (!this._pendingSubscriptions) {
                this._pendingSubscriptions = new Set();
            }
            this._pendingSubscriptions.add(sensorId);
            return;
        }

        const message = JSON.stringify({
            action: "subscribe",
            sensor_id: sensorId
        });
        this.socket.send(message);
    }

    unsubscribe(sensorId: string): void {
        if (this.isConnected && this.socket && this.socket.readyState === WebSocket.OPEN) {
            const message = JSON.stringify({
                action: "unsubscribe",
                sensor_id: sensorId
            });
            this.socket.send(message);
        } else {
            console.warn("Cannot unsubscribe: WebSocket is not open");
        }
    }

    getSubscriptions(): void {
        if (this.isConnected && this.socket && this.socket.readyState === WebSocket.OPEN) {
            const message = JSON.stringify({action: "get_subscriptions"});
            this.socket.send(message);
        } else {
            console.warn("Cannot get subscriptions: WebSocket is not open");
        }
    }

    onSensorUpdate(sensorId: string, callback: (data: any) => void): void {
        if (typeof callback !== 'function') {
            console.error("Callback must be a function");
            return;
        }
        this.messageHandlers.set(sensorId, callback);
    }

    private _handleMessage(data: any): void {
        if (data.status) {
            return;
        }
        if (data.error) {
            console.error(`Error: ${data.error}`);
            return;
        }
        if (data.subscriptions) {
            return;
        }

        const sensorId = data.device_id;
        if (!sensorId) {
            console.warn("Received message without device_id:", data);
            return;
        }

        const handler = this.messageHandlers.get(sensorId);
        if (handler) {
            handler(data);
        } else {
            console.log(`No handler for sensor: ${sensorId}`, data);
        }
    }

    disconnect(): void {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.close();
        }
    }

    private _resubscribeAll(): void {
        if (this._pendingSubscriptions) {
            for (const sensorId of this._pendingSubscriptions) {
                this.subscribe(sensorId);
            }
            this._pendingSubscriptions.clear();
        }
    }
}


export {SensorWebSocket}