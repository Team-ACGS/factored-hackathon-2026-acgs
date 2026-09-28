import { events } from "aws-amplify/data";

import { config } from "../config";
import { isServerMessage, type ServerMessage } from "./conversation";

export async function subscribeToRooms(
  customerId: string,
  onMessage: (message: ServerMessage) => void,
  onError: () => void,
): Promise<() => void> {
  const channel = await events.connect(`/${config.realtimeNamespace}/${customerId}/*`);
  const subscription = channel.subscribe({
    next: (data: { event?: unknown }) => {
      if (isServerMessage(data.event)) onMessage(data.event);
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
