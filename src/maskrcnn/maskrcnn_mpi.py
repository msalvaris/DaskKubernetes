import logging.config
import logging
import os
import fire


def run(
    config_file,
    filepath,
    output_path,
    cores_per_worker=1,
    memory_limit="auto",
    patience=60,
    batch_size=4,
):
    logging.config.fileConfig(os.getenv("LOG_CONFIG", "logging.ini"))

    from maskrcnn import dask_mpi
    from maskrcnn import dask_pipeline

    logger = logging.getLogger(__name__)
    logger.debug(os.environ)

    os.makedirs(output_path, exist_ok=True)

    dask_mpi.start(
        dask_pipeline.start(
            config_file, filepath, output_path, patience=patience, batch_size=batch_size
        ),
        cores_per_worker=cores_per_worker,
        memory_limit=memory_limit,
    )


if __name__ == "__main__":
    fire.Fire(run)
