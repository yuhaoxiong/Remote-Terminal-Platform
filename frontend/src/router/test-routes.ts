import { APP_ROUTES } from "./routes";

// 测试路由配置与生产路由共享同一份 route meta；mountApp() 使用 createMemoryHistory 保证 jsdom 兼容性。
export const TEST_ROUTES = APP_ROUTES;
