import { mount } from "@vue/test-utils";
import ElementPlus, { ElMessage } from "element-plus";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

import FileTreePanel from "../FileTreePanel.vue";
import type { Device } from "../../stores/devices";

const apiMocks = vi.hoisted(() => ({
  listDeviceFiles: vi.fn(),
  uploadDeviceFile: vi.fn(),
  downloadDeviceFile: vi.fn(),
  deleteDeviceFile: vi.fn(),
  createDeviceDirectory: vi.fn(),
  renameDeviceFile: vi.fn(),
}));

vi.mock("../../api/platform", () => ({
  ...apiMocks,
  getApiErrorMessage: vi.fn((_error: unknown, fallback: string) => fallback),
}));

const device = {
  id: 1,
  device_uuid: "device-1",
  name: "测试设备",
  device_sn: "FILE-TREE-001",
  project_id: 1,
  expected_profile_id: null,
  actual_profile_id: null,
  device_role: null,
  is_test_device: false,
  group: "未分组",
  group_id: null,
  location: "未分配",
  status: "online",
  ssh_port: 10001,
  vnc_port: 10501,
  ssh_user: "root",
  ssh_auth_type: "password",
  ssh_credential_configured: true,
  tags: [],
  cpu: null,
  memory: null,
  disk: null,
  metricRecordedAt: null,
  metricStale: false,
  metricLoadFailed: false,
} satisfies Device;

async function flushAsync() {
  for (let index = 0; index < 6; index += 1) {
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

function fileList(path: string, items: Array<Record<string, unknown>>) {
  return { device_id: 1, path, items };
}

async function mountFileTree() {
  const wrapper = mount(FileTreePanel, {
    props: { device, connected: true },
    global: { plugins: [ElementPlus] },
  });
  await flushAsync();
  return wrapper;
}

describe("FileTreePanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    Reflect.deleteProperty(window, "showSaveFilePicker");
    apiMocks.uploadDeviceFile.mockResolvedValue({ remote_path: "uploads/new.txt", status: "uploaded" });
    apiMocks.downloadDeviceFile.mockResolvedValue(new Blob(["report"]));
  });

  it("reloads and reopens the upload directory after upload", async () => {
    apiMocks.listDeviceFiles.mockImplementation(async (_deviceId: number, path: string) => {
      if (path === ".") {
        return fileList(".", [
          { name: "uploads", path: "uploads", type: "directory", size: 0, modified_at: null },
        ]);
      }
      return fileList(path, []);
    });
    const wrapper = await mountFileTree();

    await wrapper.find(".tree-node").trigger("click");
    await waitUntil(() => expect(apiMocks.listDeviceFiles).toHaveBeenCalledWith(1, "uploads"));

    const originalCreateElement = document.createElement.bind(document);
    let uploadInput: HTMLInputElement | null = null;
    const createElementSpy = vi.spyOn(document, "createElement").mockImplementation((tagName, options) => {
      const element = originalCreateElement(tagName, options);
      if (tagName.toLowerCase() === "input") {
        uploadInput = element as HTMLInputElement;
        vi.spyOn(uploadInput, "click").mockImplementation(() => undefined);
      }
      return element;
    });

    const uploadButton = wrapper.findAll("button").find((button) => button.text().includes("上传"));
    await uploadButton?.trigger("click");
    expect(uploadInput).not.toBeNull();
    const input = uploadInput as unknown as HTMLInputElement;
    Object.defineProperty(input, "files", {
      value: [new File(["new"], "new.txt", { type: "text/plain" })],
      configurable: true,
    });
    input.dispatchEvent(new Event("change"));

    await waitUntil(() => expect(apiMocks.uploadDeviceFile).toHaveBeenCalledWith(1, "uploads/new.txt", expect.any(File)));
    await waitUntil(() => {
      const uploadDirectoryLoads = apiMocks.listDeviceFiles.mock.calls.filter((call) => call[1] === "uploads");
      expect(uploadDirectoryLoads.length).toBeGreaterThanOrEqual(2);
    });
    expect(wrapper.find(".current-path").text()).toBe("uploads");
    createElementSpy.mockRestore();
  });

  it("lets the user choose a download location", async () => {
    apiMocks.listDeviceFiles.mockResolvedValue(
      fileList(".", [{ name: "report.txt", path: "report.txt", type: "file", size: 6, modified_at: null }]),
    );
    const write = vi.fn().mockResolvedValue(undefined);
    const close = vi.fn().mockResolvedValue(undefined);
    const showSaveFilePicker = vi.fn().mockResolvedValue({
      createWritable: vi.fn().mockResolvedValue({ write, close }),
    });
    Object.defineProperty(window, "showSaveFilePicker", { value: showSaveFilePicker, configurable: true });
    const success = vi.spyOn(ElMessage, "success").mockImplementation(() => ({ close: vi.fn() }) as never);
    const wrapper = await mountFileTree();

    await wrapper.find(".tree-node").trigger("dblclick");

    await waitUntil(() => expect(showSaveFilePicker).toHaveBeenCalledWith({ suggestedName: "report.txt" }));
    expect(write).toHaveBeenCalledWith(expect.any(Blob));
    expect(close).toHaveBeenCalled();
    await waitUntil(() => expect(success).toHaveBeenCalledWith("report.txt 已保存到所选位置"));
  });

  it("points to browser download history when a location picker is unavailable", async () => {
    apiMocks.listDeviceFiles.mockResolvedValue(
      fileList(".", [{ name: "report.txt", path: "report.txt", type: "file", size: 6, modified_at: null }]),
    );
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    Object.defineProperty(window.URL, "createObjectURL", {
      value: vi.fn(() => "blob:report"),
      configurable: true,
    });
    Object.defineProperty(window.URL, "revokeObjectURL", {
      value: vi.fn(),
      configurable: true,
    });
    const success = vi.spyOn(ElMessage, "success").mockImplementation(() => ({ close: vi.fn() }) as never);
    const wrapper = await mountFileTree();

    await wrapper.find(".tree-node").trigger("dblclick");

    await waitUntil(() => expect(click).toHaveBeenCalled());
    expect(success).toHaveBeenCalledWith("report.txt 已交给浏览器下载，请在浏览器下载记录中查看保存位置");
  });
});
