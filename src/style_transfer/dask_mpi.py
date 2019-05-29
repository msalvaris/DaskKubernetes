import logging
import math
import os
from threading import Thread

from distributed import Scheduler, Worker
from mpi4py import MPI
from tornado import gen
from tornado.ioloop import IOLoop

logger = logging.getLogger(__name__)


def _start_scheduler():
    logger.info("Starting scheduler...")
    loop = IOLoop.current()
    s = Scheduler(loop=loop)
    s.start("tcp://:6000")  # Listen on TCP port 6000
    logger.info("Scheduler started")
    return s


def _create_worker(scheduler_str, ncores, memory_limit="auto"):
    logger.info("Creating worker...")
    loop = IOLoop.current()
    return Worker(
        "tcp://{}".format(scheduler_str),
        loop=loop,
        ncores=ncores,
        memory_limit=memory_limit,
        reconnect=False,
    )


def _start_worker(worker):
    logger.info("Starting worker...")
    worker.start()  # choose randomly assigned port
    logger.info("Worker started")


def _start_and_monitor_worker(worker):
    logger.info("Starting worker...")
    loop = IOLoop.current()

    @gen.coroutine
    def run():
        yield worker._start()
        while worker.status != 'closed':
            yield gen.sleep(0.2)

    try:
        logger.info("Worker started")
        loop.run_sync(run)
    finally:
        logger.info("Closing worker")

    @gen.coroutine
    def close():
        yield worker._close(timeout=2)

    loop.run_sync(close)
    logger.info("Exiting worker")


def _get_num_nodes():
    return int(os.getenv("AZUREML_NODE_COUNT", 1))


def start(processing_func, cores_per_worker=None, memory_limit="auto"):
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    nprocs = comm.Get_size()
    logger.info("Rank {} of {}".format(rank, nprocs))
    ncpus = os.cpu_count()
    nnodes = _get_num_nodes()
    logger.info(
        "Detected {} processes with {} nodes and {} cpus per node".format(
            nprocs, nnodes, ncpus
        )
    )
    cores_per_worker = (
        cores_per_worker if cores_per_worker else math.floor(ncpus * nnodes / nprocs)
    )
    logger.info("Setting {} cores per worker".format(cores_per_worker))

    scheduler_str = os.getenv("AZ_BATCH_MASTER_NODE", "10.0.0.4:6000")
    if scheduler_str is None:
        raise ValueError(
            "AZ_BATCH_MASTER_NODE environment variable not found. "
            "Can not start Dask Scheduler without master node"
        )

    if rank == 0:  # Master
        loop = IOLoop.current()
        t = Thread(target=loop.start, daemon=True)
        t.start()

        scheduler = _start_scheduler()
        worker = _create_worker(scheduler_str, cores_per_worker, memory_limit=memory_limit)
        _start_worker(worker)
        processing_func(scheduler_str)
        t.join(timeout=10)
        worker_dict = scheduler.retire_workers(close_workers=True)
        logger.debug(worker_dict.result())
        scheduler.stop()
        logger.info("Exiting client and scheduler")
    else:
        worker = _create_worker(scheduler_str, cores_per_worker, memory_limit=memory_limit)
        _start_and_monitor_worker(worker)



