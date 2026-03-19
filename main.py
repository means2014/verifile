import logging
import os


from dataclasses import dataclass
from enum import auto
from enum import StrEnum
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


class CopyFailedError(Exception):
    pass


class ExistingBehavior(StrEnum):
    ERROR = auto()
    REPLACE = auto()
    SKIP = auto()


class VerificationMode(StrEnum):
    HASH = auto()
    METADATA = auto()
    SIZE_ONLY = auto()
    SKIP = auto()


def _do_copy(
    src: Path,
    dest: Path, *,
    preserve_metadata: bool = False,
    **kwargs
) -> bool:
    try:
        res = src.copy(dest, preserve_metadata = preserve_metadata)
    except Exception as e:
        logger.exception(e)
        return False
    return True


def _log_scandir_err(err: OSError) -> None:
    logger.Exception(err)


def copy_file(
    src: str | Path,
    dest: str | Path, *,
    always_hash_after_failure: bool = True
    existing_mode: ExistingBehavior = ExistingBehavior.REPLACE,
    follow_symlinks: bool = True,
    preserve_metadata: bool = False,
    retry_count_maximum: int = 3,
    retry_delay: bool = True,
    retry_delay_backoff: float = 1.5,
    retry_delay_maximum: int = 30,
    verification_mode: VerificationMode = VerificationMode.SIZE_ONLY,
    _current_try: int = 0,
    _src_fingerprint: Any = None,
    **kwargs
) -> None | Path:
    src = Path(src)
    dest = Path(dest)
    if not src.is_file():
        raise FileNotFoundError(f'Source file {str(src)} not found.')
    if verification_mode == VerificationMode.METADATA and not preserve_metadata:
        wrn_msg = 'Cannot check metadata if not preserved.'\
                  f'\n\t{verification_mode = }'\
                  f'\n\t{preserve_metadata = }'\
                  '\nReverting preserve_metadata to size_only.\n'
        logger.warning()
    if dest.is_file():
        match existing_mode:
            case ExistingBehavior.ERROR:
                err_msg = f''
                raise FileExistsError(err_msg)
            case ExistingBehavior.REPLACE:
                pass
            case ExistingBehavior.SKIP:
                return None
            case _:
                err_msg = f'Unrecognized existing_mode: {mode}'
                raise ValueError(err_msg)
    if not follow_symlinks and src.is_symlink():
        dest.unlink(missing_ok = True)
        dest.symlink_to(src.resolve())
        return dest
    src = src.resolve()
    _src_fingerprint = get_file_fingerprint(src, verification_mode, _src_fingerprint)
    if dest.is_file() and _src_fingerprint == get_file_fingerprint(dest, verification_mode):
        logger.debug(f'Skipping file {dest}, already matches.')
        return dest
    tmp = Path(dest.name + '.tmp')
    res = _do_copy(src, tmp, preserve_metadata = preserve_metadata, **kwargs)
    if not result:
        raise NotImplementedError
    dest_fingerprint = get_file_fingerprint(tmp, verification_mode)
    if _src_fingerprint == dest_fingerprint:
        dest.unlink(missing_ok = True)
        tmp.rename(dest)
        return dest
    tmp.unlink()
    if _current_try == max_retries:
        err_msg = f'After {max_retries} attempts, file {src} could not be copied'/
                  f' to {dest}.'
        logger.error(err_msg)
        raise CopyFailedError(err_msg)
    time.sleep(retry_delay)
    # upgrade verification_mode to hash on failure
    if always_hash_after_failure:
        verification_mode = 'hash'
        _src_fingerprint = get_file_fingerprint(src, verification_mode, _src_fingerprint)
    return copy_file(
        src, dest, verification_mode = verification_mode, existing_mode = existing_mode,
        follow_symlinks = follow_symlinks, max_retries = max_retries,
        preserve_metadata = preserve_metadata, retry_delay = retry_delay,
        _current_try = _current_try + 1, _src_fingerprint = _src_fingerprint,
        **kwargs
    )


def copy_tree(
    src: str | Path,
    dest: str | Path, *,
    exclude: str | Path | list[str, Path],
    parallel: int = min(32, (os.process_cpu_count() or 1) + 4),
    stop_after_n_failures: int = 1,
    **kwargs
) -> None | Path:
    src = Path(src)
    dest = Path(dest)
    if not src.is_dir():
        err_msg = f'Source must be a directory: {src}'
        raise ValueError(err_msg)
    dest.mkdir(exist_ok = True, parents = True)
    failures = 0
    for root, dirs, files in Path(src).walk(on_error = _log_scandir_err):
        rel_root = root.relative_to(src)
        target_root = dest / rel_root
        target_root.mkdir(exist_ok = True, parents = True)
        for d in dirs:
            (target_root / d).mkdir(exist_ok = True)
        for name in files:
            src_file = root / name
            dest_file = target_root / name
            res = None
            while res = None and retries < total_max_retries:
                try:
                    res = copy_file(src_file, dest_file, **kwargs)
                except CopyFailedError:
                    failures += 1
                    if failures == stop_after_n_failures:
                        err_msg = f'Failed to copy directory {src} to {dir}'
                        logger.error(err_msg)
                        return None
        return dest


def get_file_fingerprint(
    file: str|Path,
    mode: VerificationMode,
    _precalculated: Any = None
) -> int | str | tuple[int, int] |  None:
    if _precalculated is not None:
        return _precalculated
    file = Path(file)
    match mode:
        case VerificationMode.HASH:
            return get_file_hash(file)
        case VerificationMode.METADATA:
            stat = file.stat()
            return int(stat.st_size), int(stat.st_mtime_ns)
        case VerificationMode.SIZE_ONLY:
            return int(file.stat().st_size)
        case VerificationMode.SKIP:
            return None
        case _:
            err_msg = f'Unrecognized check_file mode: {mode}'
            raise ValueError(err_msg)


def get_file_hash(file: str | Path, algorithm: str = 'md5') -> str:
    with open(Path(file), 'rb') as f:
        digest = hashlib.file_digest(f, algorithm)
    return digest.hexdigest()


def move_file(
    src: str | Path,
    dest: str | Path, *,
    **kwargs
)  -> Path:
    res = copy_file(src, dest, **kwargs)
    if isinstance(res, Path) and res.is_file():
        src.unlink()
        return res
    logger.warning(f'Move {src} to {dest} was unsuccessful')
    return None


def main():
    print("Hello from verified-copy!")


if __name__ == "__main__":
    main()
