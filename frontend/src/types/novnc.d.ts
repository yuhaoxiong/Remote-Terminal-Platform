declare module "@novnc/novnc" {
  export default class RFB {
    constructor(target: HTMLElement, url: string, options?: Record<string, unknown>);
    disconnect(): void;
    addEventListener(type: string, callback: (event: Event) => void): void;
  }
}
