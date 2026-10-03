import { events } from "aws-amplify/data";

import { config } from "../config";
import { isServerMessage, isStatusEvent, type ServerMessage, type StatusEvent } from "./conversation";

export interface RoomListener {
  onMessage: (message: ServerMessage) => void;
  onStatus: (event: StatusEvent) => void;
  onError: () => void;
}

export async function subscribeToRooms(customerId: string, listener: RoomListener): Promise<() => void> {
  const { onMessage, onStatus, onError } = listener;
  const channel = await events.connect(`/${config.realtimeNamespace}/${customerId}/*`);
  const subscription = channel.subscribe({
    next: (data: { event?: unknown }) => {
      if (isServerMessage(data.event)) onMessage(data.event);
      else if (isStatusEvent(data.event)) onStatus(data.event);
    },
    error: onError,
  });
  try {
    await subscription.ready;
  } catch (error) {
    channel.close();
    throw error;
  }
  return () => channel.close();
}
