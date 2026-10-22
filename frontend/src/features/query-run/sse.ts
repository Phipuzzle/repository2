import type { SSEEvent } from "./types";

export interface ParsedSSEFrame {
  event: string;
  data: string;
  id: string | null;
}

export function parseSSEFrame(block: string): ParsedSSEFrame | null {
  let event = "message";
  let id: string | null = null;
  const data: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (!line || line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    const field = separator === -1 ? line : line.slice(0, separator);
    const rawValue = separator === -1 ? "" : line.slice(separator + 1);
    const value = rawValue.startsWith(" ") ? rawValue.slice(1) : rawValue;
    if (field === "event") event = value;
    if (field === "id") id = value;
    if (field === "data") data.push(value);
  }
  if (data.length === 0) return null;
  return { event, data: data.join("\n"), id };
}

export async function* readSSEFrames(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<ParsedSSEFrame> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const frame = parseSSEFrame(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        if (frame) yield frame;
        boundary = buffer.indexOf("\n\n");
      }
    }
    buffer += decoder.decode();
    const frame = parseSSEFrame(buffer.trim());
    if (frame) yield frame;
  } finally {
    reader.releaseLock();
  }
}

export function parseEventPayload(frame: ParsedSSEFrame): SSEEvent {
  const value = JSON.parse(frame.data) as Partial<SSEEvent>;
  const id = frame.id ? Number(frame.id) : value.id;
  if (
    typeof id !== "number" ||
    typeof value.type !== "string" ||
    typeof value.timestamp !== "string" ||
    typeof value.message !== "string"
  ) {
    throw new Error(
      "SSE event payload does not match the query event contract",
    );
  }
  return {
    id,
    type: value.type as SSEEvent["type"],
    timestamp: value.timestamp,
    message: value.message,
    data: value.data,
  };
}
