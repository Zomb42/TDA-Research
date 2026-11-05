#!/usr/bin/env python3
"""Check staged files and HEAD history against the repository's 5 MiB policy."""
import subprocess
import sys

LIMIT = 5 * 1024 * 1024


def git(*args, input=None):
    return subprocess.check_output(["git", *args], input=input)


def main():
    # The index catches newly staged payloads; history catches files deleted only
    # in a later commit, which still have to be transferred when pushing.
    index = {}
    for record in git("ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        metadata, path = record.split(b"\t", 1)
        mode, oid, stage = metadata.split()
        if mode != b"160000":  # Submodule commits belong to another repository.
            index.setdefault(oid, path)
    history = {}
    for record in git("rev-list", "--objects", "HEAD").splitlines():
        oid, _, path = record.partition(b" ")
        history.setdefault(oid, path)
    objects = {**history, **index}
    sizes = git("cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)",
                input=b"\n".join(objects) + b"\n")
    oversized = []
    for line in sizes.splitlines():
        oid, kind, size = line.split()
        if kind == b"blob" and int(size) > LIMIT:
            oversized.append((int(size), objects[oid].decode(errors="replace")))
    if oversized:
        for size, path in sorted(oversized, reverse=True):
            print(f"{size / 1024**2:.2f} MiB: {path}")
        print("Keep these payloads local and remove them from unpushed history.")
        return 1
    print("PASS: staged files and HEAD history contain no blobs over 5 MiB.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
