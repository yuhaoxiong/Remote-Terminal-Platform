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
    const wrapper = mount(ProjectsPanel, { global: { plugins: [ElementPlus] } });
    await flushAsync();

    expect(apiMocks.listProjects).toHaveBeenCalledOnce();
    expect(apiMocks.listFunctions).toHaveBeenCalledOnce();
    expect(apiMocks.listHardwareProfiles).toHaveBeenCalledOnce();
    expect(apiMocks.listProjectFunctions).toHaveBeenCalledWith(1);
    expect(wrapper.text()).toContain("现场 A");
    expect(wrapper.text()).toContain("site-a");
  });
});
