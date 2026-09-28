/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_USER_POOL_ID: string;
  readonly VITE_USER_POOL_CLIENT_ID: string;
  readonly VITE_REALTIME_HTTP_URL: string;
  readonly VITE_REALTIME_NAMESPACE: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
