import { useLiveChat } from "../../chat/live";
import { mockChat } from "../switch";
import type { ClaraChat } from "./contract";
import { useMockChat } from "./use-mock-chat";

export const useClaraChat: (customerId: string) => ClaraChat = mockChat ? useMockChat : useLiveChat;
