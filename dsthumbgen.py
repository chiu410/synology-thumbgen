import sys
import os
import re
import argparse
import errno
import logging
import time
from PIL import Image
from multiprocessing import cpu_count
from multiprocessing import Pool
from multiprocessing import Value


class State(object):
    def __init__(self):
        self.counter = Value("i", 0)
        self.start_ticks = Value("d", time.perf_counter())

    def increment(self, n=1):
        with self.counter.get_lock():
            self.counter.value = n

    @property
    def value(self):
        return self.counter.value

    @property
    def start(self):
        return self.start_ticks.value


def init(args):
    global state
    state = args


def main():
    args = parse_args()
    state = State()

    files = find_files(args.directory)

    cores = cpu_count()
    with Pool(processes=cores, initializer=init, initargs=(state,)) as pool:
        for i in pool.imap_unordered(process_file, files, chunksize=10):
            pass

    print("{0} files processed in total.".format(state.value))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create thumbnails for Synology Photo Station."
    )
    parser.add_argument(
        "--directory",
        required=True,
        help="Directory to generate thumbnails for. "
        "Subdirectories will always be processed.",
    )

    return parser.parse_args()


def find_files(dir):
    # Image extensions to look for when creating the thumbnails
    valid_exts = ("jpeg", "jpg", "bmp", "gif")
    valid_exts_re = "|".join(map((lambda ext: ".*\\.{0}$".format(ext)), valid_exts))

    for root, dirs, files in os.walk(dir):
        for name in files:
            if re.match(valid_exts_re, name, re.IGNORECASE) and not name.startswith(
                "SYNOPHOTO_THUMB"
            ):
                yield os.path.join(root, name)


def print_progress():
    global state
    state.increment(1)
    processed = state.value
    if processed % 10 == 0:
        print(
            "{0} files processed so far, averaging {1:.2f} files per second.".format(
                processed, float(processed) / (float(time.process_time() - state.start))
            )
        )


def process_file(file_path):
    print(file_path)

    (dir, filename) = os.path.split(file_path)
    thumb_dir = os.path.join(dir, "eaDir_tmp", filename)
    ensure_directory_exists(thumb_dir)

    create_thumbnails(file_path, thumb_dir)

    print_progress()


def ensure_directory_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise


def create_thumbnails(source_path, dest_dir):
    im = Image.open(source_path)

    to_generate = (
        ("SYNOPHOTO_THUMB_XL.jpg", 1280),
        ("SYNOPHOTO_THUMB_B.jpg", 640),
        ("SYNOPHOTO_THUMB_M.jpg", 320),
        ("SYNOPHOTO_THUMB_PREVIEW.jpg", 160),
        ("SYNOPHOTO_THUMB_S.jpg", 120),
    )

    im_read = 0

    for thumb in to_generate:
        thumb_filename = os.path.join(dest_dir, thumb[0])
        if os.path.exists(thumb_filename):
            continue

        if im_read == 0:
            try:
                im = Image.open(source_path)
            except:
                logging.exception("Error in opening image %s. Skipping over it.", source_path)
                return
            logging.debug("Reading: %s", source_path)
            im_read = 1
        logging.debug("Generating: %s", thumb_filename)
        try:
            im.thumbnail((thumb[1], thumb[1]), Image.ANTIALIAS)
        except:
            logging.exception("Thumbnails generation failure on: %s.", source_path)
        im.save(thumb_filename)


if __name__ == "__main__":
    sys.exit(main())
