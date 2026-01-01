from concurrent.futures import ThreadPoolExecutor, wait, as_completed

# Init global thread pool - increased for better parallelism across multiple scrapers
tp = ThreadPoolExecutor(max_workers=40)


def run_and_wait(func, iterable):
    #    for i in iterable:
    #        tp.map(func,i)
    #    results = tp.map(func,iterable)
    #    return results
    futures = []
    for item in iterable:
        # Submit each task to the thread pool
        future = tp.submit(func, item)
        futures.append(future)
    # Wait for all tasks to complete
    wait(futures)


def run_and_wait_multi(func, iterable):
    results = tp.map(lambda args: func(*args), iterable)
    return results


def run_pipelined(producer_func, consumer_func, items):
    """Run producer and consumer in pipeline - process results as they arrive.
    Producer can return a single item or list of items to be consumed."""
    futures = [tp.submit(producer_func, item) for item in items]
    consumer_futures = []
    for future in as_completed(futures):
        try:
            results = future.result()
            if results:
                if isinstance(results, list):
                    for result in results:
                        consumer_futures.append(tp.submit(consumer_func, result))
                else:
                    consumer_futures.append(tp.submit(consumer_func, results))
        except Exception:
            pass
    if consumer_futures:
        wait(consumer_futures)


def shutdown_executor():
    tp.shutdown(wait=True)
