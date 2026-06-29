import { mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

import RemotePanel from "../RemotePanel.vue";
import * as platformApi from "../../api/platform";
import { useDevicesStore, type Device } from "../../stores/devices";

const remoteMocks = vi.hoisted(() => {
  class FakeTerminal {
    cols = 88;
    rows = 24;
    output = "";
    dataCallbacks: Array<(data: string) => void> = [];
    disposed = false;

    loadAddon() {}

    open() {}

    focus() {}

    write(data: string) {
      this.output += data;
    }

    writeln(data: string) {
      this.output += `${data}\n`;
    }

    onData(callback: (data: string) => void) {
      this.dataCallbacks.push(callback);
      return { dispose: vi.fn() };
    }

    emitData(data: string) {
      for (const callback of this.dataCallbacks) {
        callback(data);
      }
    }

    dispose() {
      this.disposed = true;
    }
  }

  class FakeFitAddon {
    disposed = false;

    fit() {}

    dispose() {
      this.disposed = true;
    }
  }

  class FakeRfb {
    listeners: Record<string, Array<(event: Event) => void>> = {};
    disconnected = false;
    sentCredentials: Array<{ password: string }> = [];

    constructor(
      public target: HTMLElement,
      public url: string,
      public options: Record<string, unknown>,
    ) {}

    addEventListener(type: string, callback: (event: Event) => void) {
      this.listeners[type] ??= [];
      this.listeners[type].push(callback);
    }

    emit(type: string, detail: Record<string, unknown> = {}) {
      for (const callback of this.listeners[type] ?? []) {
        callback(new CustomEvent(type, { detail }));
      }
    }

    sendCredentials(credentials: { password: string }) {
      this.sentCredentials.push(credentials);
    }

    disconnect() {
      this.disconnected = true;
      this.emit("disconnect", { clean: true });
    }
  }

  return {
    terminalInstances: [] as FakeTerminal[],
    rfbInstances: [] as FakeRfb[],
    FakeTerminal,
    FakeFitAddon,
    FakeRfb,
  };
});

vi.mock("@xterm/xterm", () => ({
  Terminal: class extends remoteMocks.FakeTerminal {
    constructor() {
      super();
      remoteMocks.terminalInstances.push(this);
    }
  },
}));

vi.mock("@xterm/addon-fit", () => ({
  FitAddon: remoteMocks.FakeFitAddon,
}));

vi.mock("@novnc/novnc", () => ({
  default: class extends remoteMocks.FakeRfb {
    constructor(target: HTMLElement, url: string, options: Record<string, unknown>) {
      super(target, url, options);
      remoteMocks.rfbInstances.push(this);
    }
  },
}));

vi.mock("../../api/platform", () => ({
  buildApiWebSocketUrl: vi.fn((path: string, token: string) => `ws://test${path}?token=${token}`),
  getAccessToken: vi.fn(() => "access-token"),
  openSshSession: vi.fn(),
  openVncSession: vi.fn(),
}));

const api = vi.mocked(platformApi);
const mockWebSockets: MockWebSocket[] = [];

class MockResizeObserver {
  observe = vi.fn();
  disconnect = vi.fn();
}

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  sent: string[] = [];
  closed = false;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  constructor(public url: string) {
    mockWebSockets.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  open() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  receive(payload: unknown) {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(payload) }));
  }

  close() {
    this.closed = true;
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent("close"));
  }
}

async function flushAsync() {
  for (let index = 0; index < 4; index += 1) {
    await nextTick();
    await Promise.resolve();
  }
}

async function waitUntil(assertion: () => void) {
  let lastError: unknown;
  for (let index = 0; index < 20; index += 1) {
    try {
      assertion();
      return;
    } catch (error) {
      lastError = error;
      await flushAsync();
    }
  }
  throw lastError;
}

async function mountRemotePanel() {
  const pinia = createPinia();
  setActivePinia(pinia);
  const devicesStore = useDevicesStore();
  devicesStore.devices = [remoteDevice()];

  const wrapper = mount(RemotePanel, {
    global: {
      plugins: [ElementPlus, pinia],
    },
  });
  await flushAsync();
  return wrapper;
}

function remoteDevice(overrides: Partial<Device> = {}): Device {
  return {
    id: 1,
    name: "装配边缘终端 01",
    device_sn: "SN-EDGE-001",
    project_id: "工厂-a",
    group: "产线一",
    group_id: 1,
    location: "北京",
    tags: ["生产"],
    status: "online",
    ssh_port: 10000,
    vnc_port: 10500,
    ssh_user: "root",
    ssh_auth_type: "password",
    ssh_credential_configured: true,
    cpu: null,
    memory: null,
    disk: null,
    metricRecordedAt: null,
    metricStale: false,
    metricLoadFailed: false,
    ...overrides,
  };
}

describe("RemotePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockWebSockets.length = 0;
    remoteMocks.terminalInstances.length = 0;
    remoteMocks.rfbInstances.length = 0;
    vi.stubGlobal("WebSocket", MockWebSocket);
    vi.stubGlobal("ResizeObserver", MockResizeObserver);
    api.openSshSession.mockResolvedValue({
      device_id: 1,
      session_type: "ssh",
      status: "ready",
      remote_port: 10000,
      websocket_url: "/api/ws/devices/1/ssh",
      proxy_url: null,
    });
    api.openVncSession.mockResolvedValue({
      device_id: 1,
      session_type: "vnc",
      status: "ready",
      remote_port: 10500,
      websocket_url: "/api/ws/devices/1/vnc",
      proxy_url: null,
    });
  });

  it("opens SSH, streams terminal data, and closes the socket on disconnect", async () => {
    const wrapper = await mountRemotePanel();

    await wrapper.find('[data-testid="select-remote-device-1"]').trigger("click");
    await wrapper.find('[data-testid="open-ssh-1"]').trigger("click");
    await flushAsync();

    expect(api.openSshSession).toHaveBeenCalledWith(1);
    await waitUntil(() => expect(mockWebSockets).toHaveLength(1));
    expect(mockWebSockets[0].url).toBe("ws://test/api/ws/devices/1/ssh?token=access-token");

    mockWebSockets[0].open();
    await flushAsync();
    expect(wrapper.text()).toContain("SSH 已连接 装配边缘终端 01");

    mockWebSockets[0].receive({ type: "stdout", message: "shell-ready\n" });
    await flushAsync();
    remoteMocks.terminalInstances[0].emitData("whoami\n");
    await flushAsync();

    expect(remoteMocks.terminalInstances[0].output).toContain("shell-ready");
    expect(wrapper.find('[data-testid="ssh-transcript"]').text()).toContain("shell-ready");
    expect(mockWebSockets[0].sent).toContain(JSON.stringify({ type: "input", data: "whoami\n" }));

    await wrapper.find('[data-testid="disconnect-ssh-1"]').trigger("click");
    await flushAsync();

    expect(mockWebSockets[0].closed).toBe(true);
    expect(remoteMocks.terminalInstances[0].disposed).toBe(true);
    expect(wrapper.text()).toContain("SSH 已断开");
  });

  it("shows SSH session creation failures without leaving the remote workspace", async () => {
    api.openSshSession.mockRejectedValueOnce(new Error("远程代理或后端服务暂不可达"));
    const wrapper = await mountRemotePanel();

    await wrapper.find('[data-testid="select-remote-device-1"]').trigger("click");
    await wrapper.find('[data-testid="open-ssh-1"]').trigger("click");
    await flushAsync();

    expect(api.openSshSession).toHaveBeenCalledWith(1);
    expect(wrapper.text()).toContain("远程代理或后端服务暂不可达");
    expect(wrapper.find('[data-testid="select-remote-device-1"]').exists()).toBe(true);
  });

  it("consumes a cross-route SSH request from the devices store", async () => {
    const wrapper = await mountRemotePanel();
    const devicesStore = useDevicesStore();

    devicesStore.requestRemoteSession(remoteDevice(), "ssh");
    await waitUntil(() => expect(api.openSshSession).toHaveBeenCalledWith(1));
    await waitUntil(() => expect(mockWebSockets).toHaveLength(1));

    expect(wrapper.find('[data-testid="select-remote-device-1"]').classes()).toContain("is-selected");
    expect(devicesStore.remoteSessionRequest).toBeNull();
  });

  it("opens VNC, handles disconnect, and disconnects clients on unmount", async () => {
    const wrapper = await mountRemotePanel();

    await wrapper.find('[data-testid="select-remote-device-1"]').trigger("click");
    await wrapper.find('[data-testid="open-vnc-1"]').trigger("click");
    await flushAsync();

    expect(api.openVncSession).toHaveBeenCalledWith(1);
    await waitUntil(() => expect(remoteMocks.rfbInstances).toHaveLength(1));
    expect(remoteMocks.rfbInstances[0].url).toBe("ws://test/api/ws/devices/1/vnc?token=access-token");

    remoteMocks.rfbInstances[0].emit("connect");
    await flushAsync();
    expect(wrapper.text()).toContain("VNC 已连接 装配边缘终端 01");

    await wrapper.find('[data-testid="disconnect-vnc-1"]').trigger("click");
    await flushAsync();
    expect(remoteMocks.rfbInstances[0].disconnected).toBe(true);
    expect(wrapper.text()).toContain("VNC 已断开");

    await wrapper.find('[data-testid="open-vnc-1"]').trigger("click");
    await flushAsync();
    const secondClient = remoteMocks.rfbInstances[1];
    wrapper.unmount();

    expect(secondClient.disconnected).toBe(true);
  });

  it("passes the optional VNC password to noVNC", async () => {
    const wrapper = await mountRemotePanel();

    await wrapper.find('[data-testid="select-remote-device-1"]').trigger("click");
    await wrapper.find('[data-testid="vnc-password"]').setValue("vnc-pass");
    await wrapper.find('[data-testid="open-vnc-1"]').trigger("click");
    await flushAsync();

    await waitUntil(() => expect(remoteMocks.rfbInstances).toHaveLength(1));
    expect(remoteMocks.rfbInstances[0].options).toEqual({ credentials: { password: "vnc-pass" } });
  });

  it("does not leave VNC loading when the handshake closes before connecting", async () => {
    const wrapper = await mountRemotePanel();

    await wrapper.find('[data-testid="select-remote-device-1"]').trigger("click");
    await wrapper.find('[data-testid="open-vnc-1"]').trigger("click");
    await flushAsync();
    await waitUntil(() => expect(remoteMocks.rfbInstances).toHaveLength(1));

    remoteMocks.rfbInstances[0].emit("disconnect", { clean: false });
    await flushAsync();

    expect(wrapper.text()).toContain("VNC 连接中断，请检查 VNC 服务、端口和密码");
  });

  it("shows a password prompt state when noVNC asks for credentials", async () => {
    const wrapper = await mountRemotePanel();

    await wrapper.find('[data-testid="select-remote-device-1"]').trigger("click");
    await wrapper.find('[data-testid="open-vnc-1"]').trigger("click");
    await flushAsync();
    await waitUntil(() => expect(remoteMocks.rfbInstances).toHaveLength(1));

    remoteMocks.rfbInstances[0].emit("credentialsrequired", { types: ["password"] });
    await flushAsync();

    expect(remoteMocks.rfbInstances[0].disconnected).toBe(true);
    expect(wrapper.text()).toContain("VNC 需要密码，请输入 VNC 密码后重试");
  });

  it("closes active SSH sockets when the panel unmounts", async () => {
    const wrapper = await mountRemotePanel();

    await wrapper.find('[data-testid="select-remote-device-1"]').trigger("click");
    await wrapper.find('[data-testid="open-ssh-1"]').trigger("click");
    await flushAsync();
    await waitUntil(() => expect(mockWebSockets).toHaveLength(1));
    mockWebSockets[0].open();
    await flushAsync();
    wrapper.unmount();

    expect(mockWebSockets[0].closed).toBe(true);
    expect(remoteMocks.terminalInstances[0].disposed).toBe(true);
  });
});
