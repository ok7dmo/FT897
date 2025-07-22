"""Simple CLI utilities for FT-897 clone operations."""

from __future__ import annotations

import argparse

from .clone import FT897Clone
from .memory import parse_image, build_image, export_json, import_json, export_csv, import_csv


def backup(port: str, out_file: str) -> None:
    clone = FT897Clone(port)
    image = clone.recv_image()
    with open(out_file, "wb") as f:
        f.write(image)


def restore(port: str, image_file: str) -> None:
    with open(image_file, "rb") as f:
        image = f.read()
    clone = FT897Clone(port)
    clone.send_image(image)


def export_cmd(image_file: str, dest: str) -> None:
    with open(image_file, "rb") as f:
        image = f.read()
    channels = parse_image(image)
    if dest.lower().endswith(".json"):
        with open(dest, "w", encoding="utf-8") as out:
            export_json(channels, out)
    else:
        with open(dest, "w", newline="", encoding="utf-8") as out:
            export_csv(channels, out)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")

    b = sub.add_parser("backup")
    b.add_argument("port")
    b.add_argument("outfile")

    r = sub.add_parser("restore")
    r.add_argument("port")
    r.add_argument("image")

    e = sub.add_parser("export")
    e.add_argument("image")
    e.add_argument("dest")

    args = parser.parse_args(argv)
    if args.cmd == "backup":
        backup(args.port, args.outfile)
    elif args.cmd == "restore":
        restore(args.port, args.image)
    elif args.cmd == "export":
        export_cmd(args.image, args.dest)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

