import { ApiError, type Http } from "../api/http";
import { isServerMessage, type ServerMessage, type Tap } from "./conversation";

export interface LatestRoom {
  room: { room_id: string; created_at: string } | null;
  messages: ServerMessage[];
  turn?: { message_id: string; status: string | null } | null;
  server_time: string;
}

export interface NewMessage {
  room_id: string;
  message_id: string;
  text: string;
  input?: Tap;
}

export function createChatApi(http: Http) {
  return {
    async latestRoom(): Promise<LatestRoom> {
      return (await http.request("GET", "/messages/rooms/latest")) as LatestRoom;
    },

    async send(message: NewMessage): Promise<ServerMessage> {
      const body = await http.request("POST", "/messages", message);
      const stored = (body as { message?: unknown }).message;
      if (!isServerMessage(stored)) throw new ApiError(502);
      return stored;
    },
  };
}
