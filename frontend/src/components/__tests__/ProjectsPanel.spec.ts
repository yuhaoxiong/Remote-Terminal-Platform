import { mount, type VueWrapper } from "@vue/test-utils";
import ElementPlus, { ElMessageBox } from "element-plus";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

import ProjectsPanel from "../ProjectsPanel.vue";

const mountedWrappers: VueWrapper[] = [];

const apiMocks = vi.hoisted(() => ({
  listProjects: vi.fn(),
  listFunctions: vi.fn(),
  listHardwareProfiles: vi.fn(),
  listProjectFunctions: vi.fn(),
  listFunctionReleases: vi.fn(),
  listFunctionVariants: vi.fn(),
  listDevices: vi.fn(),
  createProject: vi.fn(),
  updateProject: vi.fn(),
  createFunction: vi.fn(),
  createFunctionRelease: vi.fn(),
  createFunctionVariant: vi.fn(),
  uploadFunctionArtifact: vi.fn(),
  createDeploymentPlan: vi.fn(),
  confirmDeploymentPlan: vi.fn(),
  executeDeploymentExecution: vi.fn(),
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

function mountProjectsPanel(): VueWrapper {
  const wrapper = mount(ProjectsPanel, { attachTo: document.body, global: { plugins: [ElementPlus] } });
  mountedWrappers.push(wrapper);
  return wrapper;
}

beforeEach(() => {
  apiMocks.listProjects.mockResolvedValue({ total: 0, items: [] });
  apiMocks.listFunctions.mockResolvedValue({ total: 0, items: [] });
  apiMocks.listHardwareProfiles.mockResolvedValue({ total: 2, items: [] });
  apiMocks.listProjectFunctions.mockResolvedValue({ total: 0, items: [] });
  apiMocks.listFunctionReleases.mockResolvedValue({ total: 0, items: [] });
  apiMocks.listFunctionVariants.mockResolvedValue({ total: 0, items: [] });
  apiMocks.listDevices.mockResolvedValue({ total: 0, items: [] });
});

afterEach(() => {
  mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  document.body.innerHTML = "";
  vi.clearAllMocks();
});

describe("ProjectsPanel lifecycle management", () => {

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
    const wrapper = mountProjectsPanel();
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
    const wrapper = mountProjectsPanel();
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

  it("uploads a standard package for a draft release and hardware profile", async () => {
    const edgeFunction = {
      id: 2, code: "outside-rubbish-bag", name: "桶外垃圾袋识别", description: null, status: "active",
      created_at: "2026-07-17T00:00:00Z", updated_at: "2026-07-17T00:00:00Z",
    };
    const release = {
      id: 3, function_id: 2, version: "0.1.0", status: "draft", manifest_json: null, release_notes: null,
      published_at: null, created_by: 1, created_at: "2026-07-17T00:00:00Z", updated_at: "2026-07-17T00:00:00Z",
    };
    const profile = {
      id: 4, code: "rk3588-8g-debian11", name: "RK3588 8G / Debian 11", soc: "RK3588",
      memory_mb: 8192, os_version: "Debian 11", rknn_version: null, active: true,
    };
    apiMocks.listFunctions.mockResolvedValue({ total: 1, items: [edgeFunction] });
    apiMocks.listFunctionReleases.mockResolvedValue({ total: 1, items: [release] });
    apiMocks.listHardwareProfiles.mockResolvedValue({ total: 1, items: [profile] });
    apiMocks.uploadFunctionArtifact.mockResolvedValue({
      id: 5, release_id: 3, hardware_profile_id: 4, artifact_uri: "artifacts/releases/3/profiles/4/package.tar.gz",
      artifact_sha256: "a".repeat(64), artifact_size: 1024, signature: null, key_id: null, status: "draft",
      created_at: "2026-07-17T00:00:00Z", updated_at: "2026-07-17T00:00:00Z",
    });
    const wrapper = mountProjectsPanel();
    await flushAsync();

    await wrapper.find('[data-testid="open-artifact-upload-3"]').trigger("click");
    await flushAsync();
    const profileSelect = document.body.querySelector<HTMLElement>('[data-testid="artifact-profile"]');
    if (!profileSelect) throw new Error("Missing artifact profile select");
    profileSelect.click();
    await flushAsync();
    const option = Array.from(document.body.querySelectorAll<HTMLElement>(".el-select-dropdown__item"))
      .find((item) => item.textContent?.includes("RK3588 8G"));
    if (!option) throw new Error("Missing hardware profile option");
    option.click();
    const file = new File(["package"], "outside-rubbish-bag.tar.gz", { type: "application/gzip" });
    const input = document.body.querySelector<HTMLInputElement>('[data-testid="artifact-file"]');
    if (!input) throw new Error("Missing artifact file input");
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
    clickTeleported('[data-testid="artifact-upload"]');
    await flushAsync();

    expect(apiMocks.uploadFunctionArtifact).toHaveBeenCalledWith(2, 3, 4, file);
  });
});

describe("ProjectsPanel deployment planning", () => {
  it("previews a frozen single-device deployment plan before confirmation", async () => {
    const project = {
      id: 1, code: "site-a", name: "现场 A", description: null, status: "active",
      created_at: "2026-07-17T00:00:00Z", updated_at: "2026-07-17T00:00:00Z",
    };
    const device = {
      id: 8, device_uuid: "00000000-0000-0000-0000-000000000008", name: "边缘设备 8", device_sn: "EDGE-008",
      project_id: 1, expected_profile_id: 1, actual_profile_id: 1, device_role: null, is_test_device: true,
      initialization_status: "ready", vnc_status: "ready", bootstrap_generation: 1, initialized_at: "2026-07-17T00:00:00Z",
      location: null, hardware_model: null, ssh_port: 10008, vnc_port: 10508, ssh_user: "edge",
      ssh_auth_type: "password", ssh_credential_configured: true, local_ip: null, os_version: "debian11",
      description: null, tags: [], group_id: null, status: "online", last_seen: "2026-07-17T00:00:00Z",
      created_at: "2026-07-17T00:00:00Z", updated_at: "2026-07-17T00:00:00Z",
    };
    apiMocks.listProjects.mockResolvedValue({ total: 1, items: [project] });
    apiMocks.listDevices.mockResolvedValue({ total: 1, items: [device] });
    apiMocks.createDeploymentPlan.mockResolvedValue({
      id: 11, project_id: 1, status: "ready", snapshot_hash: "a".repeat(64), expires_at: "2026-07-18T00:00:00Z",
      stale_reason: null, created_by: 1, confirmed_by: null, confirmed_at: null,
      created_at: "2026-07-17T00:00:00Z", updated_at: "2026-07-17T00:00:00Z",
      items: [{
        id: 12, plan_id: 11, device_id: 8, function_id: 2, release_id: 3, variant_id: 4,
        config_snapshot: {}, config_hash: "b".repeat(64), artifact_sha256: "c".repeat(64),
        preflight_json: { ready: true }, status: "ready", created_at: "2026-07-17T00:00:00Z",
      }],
    });
    apiMocks.confirmDeploymentPlan.mockResolvedValue({
      id: 13, execution_id: "execution-0001", plan_id: 11, status: "pending", started_at: null, finished_at: null,
      created_by: 1, created_at: "2026-07-17T00:00:00Z", updated_at: "2026-07-17T00:00:00Z", items: [],
    });
    apiMocks.executeDeploymentExecution.mockResolvedValue({
      id: 13, execution_id: "execution-0001", plan_id: 11, status: "completed",
      started_at: "2026-07-17T00:01:00Z", finished_at: "2026-07-17T00:02:00Z",
      created_by: 1, created_at: "2026-07-17T00:00:00Z", updated_at: "2026-07-17T00:02:00Z",
      items: [{
        id: 14, deployment_execution_id: 13, plan_item_id: 12, status: "success", attempt_count: 1,
        result_json: { status: "succeeded" }, error_message: null,
        started_at: "2026-07-17T00:01:00Z", finished_at: "2026-07-17T00:02:00Z",
        created_at: "2026-07-17T00:00:00Z", updated_at: "2026-07-17T00:02:00Z",
      }],
    });
    const confirmation = vi.spyOn(ElMessageBox, "confirm").mockResolvedValue("confirm" as never);
    const wrapper = mountProjectsPanel();
    await flushAsync();

    await wrapper.find('[data-testid="open-deployment-plan-1"]').trigger("click");
    await flushAsync();
    const deviceSelect = document.body.querySelector<HTMLElement>('[data-testid="deployment-device"]');
    if (!deviceSelect) throw new Error("Missing deployment device select");
    deviceSelect.click();
    await flushAsync();
    const option = Array.from(document.body.querySelectorAll<HTMLElement>(".el-select-dropdown__item"))
      .find((item) => item.textContent?.includes("EDGE-008"));
    if (!option) throw new Error("Missing deployment device option");
    option.click();
    clickTeleported('[data-testid="deployment-plan-preview"]');
    await flushAsync();

    expect(apiMocks.listDevices).toHaveBeenCalledWith({ project_id: 1 });
    expect(apiMocks.createDeploymentPlan).toHaveBeenCalledWith(1, [8]);
    expect(document.body.textContent).toContain("预检通过");
    expect(document.body.textContent).toContain("aaaaaaaaaaaa");

    clickTeleported('[data-testid="deployment-plan-confirm"]');
    await flushAsync();
    expect(confirmation).toHaveBeenCalledWith(
      "确认执行计划 #11？确认后将生成唯一执行 ID。",
      "人工确认部署",
      expect.objectContaining({ confirmButtonText: "确认部署" }),
    );
    expect(apiMocks.confirmDeploymentPlan).toHaveBeenCalledWith(11);
    expect(document.body.textContent).toContain("execution-0001");

    clickTeleported('[data-testid="deployment-execution-start"]');
    await flushAsync();
    expect(apiMocks.executeDeploymentExecution).toHaveBeenCalledWith("execution-0001");
    expect(document.body.textContent).toContain("completed");
    expect(document.body.textContent).toContain("success");
  });
});
