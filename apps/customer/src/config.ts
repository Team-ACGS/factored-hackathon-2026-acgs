function required(name: keyof ImportMetaEnv): string {
  const value: unknown = import.meta.env[name];
  if (typeof value !== "string" || !value) {
    throw new Error(`${name} is not set`);
  }
  return value;
}

const userPoolId = required("VITE_USER_POOL_ID");

export const config = {
  apiUrl: required("VITE_API_URL").replace(/\/$/, ""),
  region: userPoolId.split("_")[0] ?? "us-east-1",
  userPoolId,
  userPoolClientId: required("VITE_USER_POOL_CLIENT_ID"),
  realtimeHttpUrl: required("VITE_REALTIME_HTTP_URL"),
  realtimeNamespace: required("VITE_REALTIME_NAMESPACE"),
};
