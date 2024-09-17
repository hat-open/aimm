from hat import aio
from hat import json
from pathlib import Path
import appdirs
import argparse
import asyncio
import contextlib
import logging.config
import sys

from aimm import plugins
from aimm.server import common
import aimm.server.runners

mlog = logging.getLogger("aimm.server.main")
default_conf_path = Path(appdirs.user_data_dir("aimm")) / "server.yaml"


def main():
    aio.init_asyncio()

    args = _create_parser().parse_args()
    conf = json.decode_file(args.conf)
    common.json_schema_repo.validate("aimm://server/main.yaml#", conf)

    logging.config.dictConfig(conf["log"])
    plugins.initialize(conf["plugins"])
    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main(conf))


async def async_main(conf):
    runner = aimm.server.runners.MainRunner(conf)
    try:
        await runner.wait_closing()
    finally:
        await aio.uncancellable(runner.async_close())


def _create_parser():
    parser = argparse.ArgumentParser(
        prog="aimm-server", description="Run AIMM server"
    )
    parser.add_argument(
        "--conf",
        metavar="path",
        dest="conf",
        default=default_conf_path,
        type=Path,
        help="configuration defined by aimm://server/main.yaml# "
        "(default $XDG_CONFIG_HOME/aimm/server.yaml)",
    )
    return parser


if __name__ == "__main__":
    sys.exit(main())
