import logging
import os

import fire


def run(
    model_dir,
    style,
    filepath,
    output_path,
    debug=False,
    cores_per_worker=1,
    memory_limit="auto",
    patience=60,
    batch_size=4,
):
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    from src.style_transfer import dask_mpi
    from src.style_transfer import dask_pipeline

    logger = logging.getLogger(__name__)
    logger.debug(os.environ)

    os.makedirs(output_path, exist_ok=True)



    dask_mpi.start(
        dask_pipeline.start(
            model_dir,
            style,
            filepath,
            output_path,
            patience=patience,
            batch_size=batch_size,
        ),
        cores_per_worker=cores_per_worker,
        memory_limit=memory_limit,
    )


if __name__ == "__main__":
    fire.Fire(run)
