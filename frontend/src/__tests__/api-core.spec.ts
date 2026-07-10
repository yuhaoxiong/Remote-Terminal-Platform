import axios from "axios";
import { describe, expect, it } from "vitest";

import { getApiErrorMessage } from "../api/core";

describe("getApiErrorMessage", () => {
  it("returns FastAPI detail from an Axios response", () => {
    const error = new axios.AxiosError("Request failed", "ERR_BAD_RESPONSE", undefined, undefined, {
      data: { detail: "SSH 认证失败" },
      status: 502,
      statusText: "Bad Gateway",
      headers: {},
      config: { headers: new axios.AxiosHeaders() },
    });

    expect(getApiErrorMessage(error, "加载失败")).toBe("SSH 认证失败");
  });

  it("uses the fallback for unknown errors", () => {
    expect(getApiErrorMessage(new Error("internal"), "加载失败")).toBe("加载失败");
  });
});
