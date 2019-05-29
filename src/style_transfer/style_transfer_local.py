import logging

import fire


def run(scheduler_address, model_dir, style, filepath, output_path, debug=False):
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    from src.style_transfer import dask_pipeline

    dask_pipeline.start(model_dir, style, filepath, output_path, scheduler_address)


if __name__ == "__main__":
    fire.Fire(run)
