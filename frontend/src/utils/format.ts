/**
 * 通用格式化工具。
 *
 * 收敛此前散落在 App.vue 与各业务组件中的重复实现:
 * - formatTime: 原先有 7 处几乎相同的拷贝(仅空值占位文案不同)
 * - formatSize: 文件大小展示
 * 统一时间与字节大小的展示逻辑,作为后续 App.vue 拆分的共享底座。
 */

/**
 * 将 ISO 时间字符串格式化为 "YYYY-MM-DD HH:mm"。
 *
 * @param value ISO 时间字符串,或 null / undefined / 空串
 * @param fallback value 为空时返回的占位文案。各调用方约定不同
 *   (如 "暂无" / "未上报" / "-"),默认空串以兼容 App.vue 的原有行为。
 */
export function formatTime(value: string | null | undefined, fallback = ""): string {
  return value ? value.replace("T", " ").slice(0, 16) : fallback;
}

/**
 * 将字节数格式化为带单位的可读字符串(B / KB / MB)。
 */
export function formatSize(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

/**
 * 按逗号分隔字符串为标签数组。
 */
export function parseTags(value: string): string[] {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}
