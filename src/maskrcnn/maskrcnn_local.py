import logging.config
import os
import fire


def run(scheduler_address, config_file, filepath, output_path):
    logging.config.fileConfig(os.getenv("LOG_CONFIG", "logging.ini"))
    from maskrcnn import dask_pipeline

    dask_pipeline.start(config_file, filepath, output_path, scheduler_address)


if __name__ == "__main__":
    fire.Fire(run)
