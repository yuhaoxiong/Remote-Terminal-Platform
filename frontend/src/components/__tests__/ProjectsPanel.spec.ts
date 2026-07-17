import { mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

import ProjectsPanel from "../ProjectsPanel.vue";

const apiMocks = vi.hoisted(() => ({
  listProjects: vi.fn(),
  listFunctions: vi.fn(),
  listHardwareProfiles: vi.fn(),
  listProjectFunctions: vi.fn(),
  listFunctionReleases: vi.fn(),
  createProject: vi.fn(),
  updateProject: vi.fn(),
  createFunction: vi.fn(),
  createFunctionRelease: vi.fn(),
  createFunctionVariant: vi.fn(),
  publishFunctionRelease: vi.fn(),
  setProjectFunction: vi.fn(),
  markProjectFunctionPendingUninstall: vi.fn(),
}));

vi.mock("../../api/platform", () => ({
  ...apiMocks,
  getApiErrorMessage: vi.fn((_error: unknown, fallback: string) => fallback),
}));

async function flushAsync() {
  for (let index = 0; index < 5; index += 1) {
    await nextTick();
    await Promise.resolve();
  }
}

async function setTeleportedInput(selector: string, value: string) {
  const host = document.body.querySelector<HTMLElement>(selector);
  const input = host instanceof HTMLInputElement ? host : host?.querySelector<HTMLInputElement>("input");
  if (!input) throw new Error(`Missing teleported input: ${selector}`);
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await flushAsync();
}

function clickTeleported(selector: string) {
  const button = document.body.querySelector<HTMLElement>(selector);
  if (!button) throw new Error(`Missing teleported element: ${selector}`);
  button.click();
}

describe("ProjectsPanel", () => {
  beforeEach(() => {
    apiMocks.listProjects.mockResolvedValue({ total: 0, items: [] });
    apiMocks.listFunctions.mockResolvedValue({ total: 0, items: [] });
    apiMocks.listHardwareProfiles.mockResolvedValue({ total: 2, items: [] });
    apiMocks.listProjectFunctions.mockResolvedValue({ total: 0, items: [] });
    apiMocks.listFunctionReleases.mockResolvedValue({ total: 0, items: [] });
  });

  afterEach(() => {
    document.body.innerHTML = "";
    vi.clearAllMocks();
  });

  it("loads formal projects, functions, profiles, and assignments", async () => {
    apiMocks.listProjects.mockResolvedValue({
      total: 1,
      items: [{
        id: 1,
        code: "site-a",
        name: "现场 A",
        description: null,
        status: "active",
        created_at: "2026-07-17T00:00:00Z",
        updated_at: "2026-07-17T00:00:00Z",
      }],
    });
    const wrapper = mount(ProjectsPanel, { attachTo: document.body, global: { plugins: [ElementPlus] } });
    await flushAsync();

    expect(apiMocks.listProjects).toHaveBeenCalledOnce();
    expect(apiMocks.listFunctions).toHaveBeenCalledOnce();
    expect(apiMocks.listHardwareProfiles).toHaveBeenCalledOnce();
    expect(apiMocks.listProjectFunctions).toHaveBeenCalledWith(1);
    expect(wrapper.text()).toContain("现场 A");
    expect(wrapper.text()).toContain("site-a");
  });

  it("creates projects and functions with Chinese names without requiring technical codes", async () => {
    apiMocks.createProject.mockResolvedValue({
      id: 1, code: "project-abcd1234", name: "桶外识别项目", description: null, status: "active",
      created_at: "2026-07-17T00:00:00Z", updated_at: "2026-07-17T00:00:00Z",
    });
    apiMocks.createFunction.mockResolvedValue({
      id: 2, code: "function-abcd1234", name: "桶外垃圾袋识别", description: null, status: "active",
      created_at: "2026-07-17T00:00:00Z", updated_at: "2026-07-17T00:00:00Z",
    });
    const wrapper = mount(ProjectsPanel, { attachTo: document.body, global: { plugins: [ElementPlus] } });
    await flushAsync();

    await wrapper.find('[data-testid="open-project-create"]').trigger("click");
    await flushAsync();
    await setTeleportedInput('[data-testid="project-name"]', "桶外识别项目");
    clickTeleported('[data-testid="project-create"]');
    await flushAsync();
    expect(apiMocks.createProject).toHaveBeenCalledWith({ name: "桶外识别项目" });

    await wrapper.find('[data-testid="open-function-create"]').trigger("click");
    await flushAsync();
    await setTeleportedInput('[data-testid="function-name"]', "桶外垃圾袋识别");
    clickTeleported('[data-testid="function-create"]');
    await flushAsync();
    expect(apiMocks.createFunction).toHaveBeenCalledWith({ name: "桶外垃圾袋识别" });
  });
});
