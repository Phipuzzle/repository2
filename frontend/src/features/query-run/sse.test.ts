import { describe, expect, it } from "vitest";

import { parseEventPayload, parseSSEFrame, readSSEFrames } from "./sse";

describe("SSE protocol client", () => {
  it("parses named events, ids and multi-line data", () => {
    expect(
      parseSSEFrame(
        'id: 7\nevent: sql_generated\ndata: {"id":7,\ndata: "type":"sql_generated"}',
      ),
    ).toEqual({
      id: "7",
      event: "sql_generated",
      data: '{"id":7,\n"type":"sql_generated"}',
    });
  });

  it("preserves frames split across transport chunks", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            'id: 1\nevent: submitted\ndata: {"id":1,"type":"submitted","timestamp":"2026-10-22T00:00:00Z","message":"ok"}\n',
          ),
        );
        controller.enqueue(
          encoder.encode(
            '\nid: 2\nevent: run_completed\ndata: {"id":2,"type":"run_completed","timestamp":"2026-10-22T00:00:01Z","message":"done"}\n\n',
          ),
        );
        controller.close();
      },
    });
    const frames = [];
    for await (const frame of readSSEFrames(stream)) frames.push(frame);
    expect(frames.map((frame) => frame.event)).toEqual([
      "submitted",
      "run_completed",
    ]);
    expect(parseEventPayload(frames[1]).type).toBe("run_completed");
  });
});
