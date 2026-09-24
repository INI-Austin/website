"""Where the BIDS derivatives live.

The dataset is mounted locally and is not part of this repository, so its
root and the subject to render are configuration rather than constants. Set
both before running anything here that reads MRI:

    export INI_BIDS_ROOT=/path/to/dataset
    export INI_BIDS_SUBJECT=sub-01

Scripts that work from the `work/*.npz` caches need neither.
"""
import os


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(
            f"{name} is not set. The BIDS derivatives are not in this "
            "repository; point it at your local copy of the dataset. "
            "See render/README.md."
        )
    return value


def subject() -> str:
    """The BIDS subject label, e.g. sub-01."""
    return _require("INI_BIDS_SUBJECT")


def derivatives(pipeline: str, folder: str = "anat") -> str:
    """The <root>/derivatives/<pipeline>/<subject>/<folder> directory."""
    return f"{_require('INI_BIDS_ROOT')}/derivatives/{pipeline}/{subject()}/{folder}"
