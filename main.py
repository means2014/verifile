import logging


from enum import StrEnum
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


class ExistingBehavior(StrEnum):
    ERROR = 'error'
    REPLACE = 'replace'
    SKIP = 'skip'


class FileCheckBehavior(StrEnum):
    HASH = 'hash'
    METADATA = 'metadata'
    SIZE_ONLY = 'size_only'
    SKIP = 'skip'


def _do_copy(src: Path, dest: Path) -> bool:
    raise NotImplementedError


def copy_file(
    src: str | Path,
    dest: str | Path, *,
    check_mode: FileCheckBehavior = FileCheckBehavior.SIZE_ONLY,
    existing_mode: ExistingBehavior = ExistingBehavior.REPLACE,
    follow_symlinks: bool = True,
    max_retries: int = 5,
    preserve_metadata: bool = False,
    retry_delay: int = 15,
    _current_try: int = 0,
    _src_fingerprint: Any = None,
    **kwargs
) -> None | Path:
    src = Path(src)
    dest = Path(dest)
    if not src.is_file():
        raise FileNotFoundError(f'Source file {str(src)} not found.')
    if check_mode == FileCheckBehavior.METADATA and not preserve_metadata:
        wrn_msg = 'Cannot check metadata if not preserved.'\
                  f'\n\t{check_mode = }'\
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
    _src_fingerprint = get_file_fingerprint(src, check_mode, _src_fingerprint)
    tmp = Path(dest.name + '.tmp')
    res = _do_copy(src, tmp, **kwargs)
    if not result:
        raise NotImplementedError
    dest_fingerprint = get_file_fingerprint(tmp, check_mode)
    if _src_fingerprint == dest_fingerprint:
        dest.unlink(missing_ok = True)
        tmp.rename(dest)
        return dest
    tmp.unlink()
    if _current_try == max_retries:
        err_msg = f'After {max_retries} attempts, file {src} could not be copied'/
                  f' to {dest}.'
        logger.error(err_msg)
        return None
    time.sleep(retry_delay)
    return copy_file(
        src, dest, check_mode = check_mode, existing_mode = existing_mode,
        follow_symlinks = follow_symlinks, max_retries = max_retries,
        preserve_metadata = preserve_metadata, retry_delay = retry_delay,
        _current_try = _current_try + 1, _src_fingerprint = _src_fingerprint,
        **kwargs
    )


def get_file_fingerprint(
    file: str|Path,
    mode: FileCheckBehavior,
    _precalculated: Any = None
) -> int | str | tuple[int, int] |  None:
    if _precalculated is not None:
        return _precalculated
    file = Path(file)
    match mode:
        case FileCheckBehavior.HASH:
            return get_file_hash(file)
        case FileCheckBehavior.METADATA:
            stat = file.stat()
            return int(stat.st_size), int(stat.st_mtime_ns)
        case FileCheckBehavior.SIZE_ONLY:
            return int(file.stat().st_size)
        case FileCheckBehavior.SKIP:
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
    check_mode: FileCheckBehavior = FileCheckBehavior.SIZE_ONLY,
    existing_mode: ExistingBehavior = ExistingBehavior.REPLACE,
    follow_symlinks: bool = True,
    max_retries: int = 5,
    preserve_metadata: bool = False,
    retry_delay: int = 15,
    **kwargs
)  -> Path:
    res = copy_file(src, dest,
        check_mode = check_mode,
        existing_mode = existing_mode,
        follow_symlinks = follow_symlinks,
        max_retries = max_retries,
        preserve_metadata = preserve_metadata,
        retry_delay = retry_delay,
        **kwargs
    )
    if isinstance(res, Path) and res.is_file():
        src.unlink()
        return dest
    logger.warning('Move was unsuccessful')
    return None


def main():
    print("Hello from verified-copy!")


if __name__ == "__main__":
    main()
