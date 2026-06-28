export {};

declare global {
  interface Window {
    ws?: WebSocket;
    ytpGenerateNotifications?: (count?: number) => number;
  }
}
