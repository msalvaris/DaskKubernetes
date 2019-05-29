import logging
import os
from threading import Thread
from time import sleep
from timeit import default_timer

import dask
import numpy as np
from dask.distributed import as_completed, Client
from toolz import curry

from style_transfer import CountdownTimer, FileReader, save_image, load_image
from style_transfer.model import stylize_batch, load_model, clean_gpu_mem

logger = logging.getLogger(__name__)


def stack(chunk):
    return np.stack(chunk)


def chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i : i + n]


def write(filenames, img_array, output_folder):
    for filepath, img in zip(filenames, img_array):
        filename = os.path.split(filepath)[-1]
        outpath = os.path.join(output_folder, filename)
        save_image(outpath, img)
    return len(filenames)


@curry
def process_batch(client, style_model, output_path, batch):
    remote_batch_f = client.scatter(batch)
    img_array_f = client.map(load_image, remote_batch_f)
    stacked_array_f = client.submit(stack, img_array_f)
    styled_array_f = client.submit(stylize_batch, style_model, stacked_array_f)
    return client.submit(write, batch, styled_array_f, output_path)


def style_images(
    processing_func, file_reader, batch_size=4, sleep_period=0.1, patience=60
):
    patience_timer = CountdownTimer(duration=patience)
    all_res = []
    while True:
        new_files = file_reader.new_files()
        if len(new_files) > 0:
            patience_timer.reset()
            new_res = list(map(processing_func, chunks(list(new_files), batch_size)))
            all_res.extend(new_res)

        for res in all_res:
            if res.done():
                all_res.remove(res)
        logger.debug("Batches remaining {}".format(len(all_res)))

        if patience_timer.is_expired() and len(all_res) == 0:
            logger.info("Finished processing images")
            break

        sleep(sleep_period)


def _distribute_model_to_workers(client, model_dir, style):
    logger.info("Loading model...")
    start = default_timer()
    style_model = client.submit(load_model, model_dir, style, cuda=True)
    dask.distributed.wait(style_model)
    client.replicate(style_model)
    logger.info(
        "Model replicated on workers | took {} seconds".format(default_timer() - start)
    )
    return style_model


def run_style_transfer_pipeline(
    client, model_dir, style, filepath, output_path, patience=60, batch_size=4
):
    logger.info("Running style transfer with {}".format(style))

    style_model = _distribute_model_to_workers(client, model_dir, style)

    filepath = os.path.join(filepath, "*.jpg")
    logger.info("Reading files from {}".format(filepath))
    file_reader = FileReader(filepath)

    logger.info("Writing files to {}".format(output_path))
    processing_func = process_batch(client, style_model, output_path)

    load_thread = Thread(
        target=style_images,
        args=(processing_func, file_reader),
        kwargs={"patience": patience, "batch_size": batch_size},
    )
    start = default_timer()
    load_thread.start()
    load_thread.join()
    logger.info("Finished processing images in {}".format(default_timer() - start))

    # Delete model and clear GPU memory
    logger.info("Clearing model from GPU")
    del style_model
    client.run(clean_gpu_mem)


@curry
def start(
    model_dir,
    style,
    filepath,
    output_path,
    scheduler_address,
    patience=60,
    batch_size=4,
):
    client = Client(scheduler_address)
    run_style_transfer_pipeline(
        client,
        model_dir,
        style,
        filepath,
        output_path,
        patience=patience,
        batch_size=batch_size,
    )
    client.close()
