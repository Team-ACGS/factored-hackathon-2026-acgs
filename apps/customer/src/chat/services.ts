import { http } from "../api/session";
import { createChatApi } from "./api";

export { clock } from "../api/session";
export const api = createChatApi(http);
