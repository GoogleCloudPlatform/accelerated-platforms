import asyncio
import time
import logging

async def my_async_function(name, delay):
    """Simulates a long-running asynchronous task."""
    logging.info(f"Task {name}: Starting")
    await asyncio.sleep(delay)  # Non-blocking delay
    logging.info(f"Task {name}: Completed")
    return f"Task {name} finished"

async def main():
    """Demonstrates concurrent vs. sequential execution."""

    # Asynchronous (Concurrent) Execution
    start_time_async = time.time()
    logging.info("Starting asynchronous tasks")

    task1 = asyncio.create_task(my_async_function("A", 2))
    task2 = asyncio.create_task(my_async_function("B", 1))
    task3 = asyncio.create_task(my_async_function("C", 3))

    results_async = await asyncio.gather(task1, task2, task3)  # Await concurrently

    end_time_async = time.time()
    logging.info(f"Asynchronous tasks completed in {end_time_async - start_time_async:.2f} seconds")
    logging.info(f"Asynchronous Results: {results_async}")



    # Synchronous (Sequential) Execution
    start_time_sync = time.time()
    logging.info("Starting synchronous tasks")

    results_sync = []
    results_sync.append(await my_async_function("A", 2)) # Await makes this sequential.  Each call completes before the next.
    results_sync.append(await my_async_function("B", 1))
    results_sync.append(await my_async_function("C", 3))

    end_time_sync = time.time()
    logging.info(f"Synchronous tasks completed in {end_time_sync - start_time_sync:.2f} seconds")
    logging.info(f"Synchronous Results: {results_sync}")



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    asyncio.run(main())
