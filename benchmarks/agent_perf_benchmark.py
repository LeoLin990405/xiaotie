import asyncio
import json
import time
from pathlib import Path

from xiaotie.events import EventBroker, EventType, MessageDeltaEvent
from xiaotie.proxy.storage import CapturedRequest, RequestStorage


async def benchmark_event_publish(total_events: int = 20000) -> dict:
    broker = EventBroker(buffer_size=4096)
    queue = await broker.subscribe([EventType.MESSAGE_DELTA])
    events = [MessageDeltaEvent(content=str(i)) for i in range(total_events)]

    start_single = time.perf_counter()
    for event in events:
        await broker.publish(event)
    single_cost = time.perf_counter() - start_single
    while not queue.empty():
        queue.get_nowait()

    start_batch = time.perf_counter()
    await broker.publish_batch(events)
    batch_cost = time.perf_counter() - start_batch

    return {
        "single_publish_seconds": round(single_cost, 6),
        "batch_publish_seconds": round(batch_cost, 6),
        "events": total_events,
        "single_events_per_sec": round(total_events / single_cost, 2),
        "batch_events_per_sec": round(total_events / batch_cost, 2),
        "speedup": round(single_cost / batch_cost, 2) if batch_cost > 0 else None,
    }


def benchmark_storage(total_entries: int = 200000, max_entries: int = 10000) -> dict:
    storage = RequestStorage(max_entries=max_entries)
    start = time.perf_counter()
    for i in range(total_entries):
        storage.add(
            CapturedRequest(
                url=f"https://example.com/{i}",
                host="example.com",
                path=f"/{i}",
                status_code=200,
                response_size=128,
                duration_ms=10.0,
            )
        )
    cost = time.perf_counter() - start
    return {
        "insert_seconds": round(cost, 6),
        "insert_per_sec": round(total_entries / cost, 2),
        "total_entries": total_entries,
        "retained_entries": storage.count,
        "max_entries": max_entries,
    }


async def main():
    out_dir = Path("benchmarks/results")
    out_dir.mkdir(parents=True, exist_ok=True)

    event_result = await benchmark_event_publish()
    storage_result = benchmark_storage()
    summary = {
        "timestamp": int(time.time()),
        "event_benchmark": event_result,
        "storage_benchmark": storage_result,
    }

    out_file = out_dir / "latest.json"
    out_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
