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
    chunk_size: int = 1024*1024,
    preserve_metadata: bool = False,
    **kwargs
) -> bool:
    try:
        with (
            src.open('rb') as frsc,
            dest.open('wb') as fdest
        ):
            while chunk := fsrc.read(chunk_size):
                fdest.write(chunk)
        if preserve_metadata:
            shutil.copystat(src, dest)
    except Exception as e:
        logger.exception(e)
        return False
    return True


def _is_excluded(rel_path: Path, patterns: list[str]) -> bool:
    rel_str = rel_path.as_posix()
    for pattern in patterns:
        if pattern.endswith('/'):
            pattern += '**'
        if rel_path.match(pattern):
            return True
    return False


def _log_scandir_err(err: OSError) -> None:
    logger.Exception(err)


def _normalize_excludes(exclude: str | Path | list[str | Path] | None) -> list[str]:
    if exclude is None:
        return []
    if isinstance(exclude, (str, Path)):
        exclude = [exclude]
    patterns = []
    for item in exclude:
        if isinstance(item, Path):
            patterns.append(item.as_posix())
        else:
            patterns.append(str(item))
    return patterns


def copy_file(
    src: str | Path,
    dest: str | Path, *,
    always_hash_after_failure: bool = True,
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
    tmp = Path(str(dest) + '.tmp')
    tmp.parent.mkdir(exist_ok = True, parents = True)
    res = _do_copy(src, tmp, preserve_metadata = preserve_metadata, **kwargs)
    if not res:
        err_msg = f'Failed to copy {src} to {dest}'
        raise CopyFailedError(err_msg)
    dest_fingerprint = get_file_fingerprint(tmp, verification_mode)
    if _src_fingerprint == dest_fingerprint:
        dest.unlink(missing_ok = True)
        tmp.rename(dest)
        logger.debug(f'File {src} copied to {dest}.')
        return dest
    tmp.unlink()
    if _current_try == max_retries:
        err_msg = f'After {max_retries} attempts, file {src} could not be copied'\
                  f' to {dest}.'
        logger.error(err_msg)
        raise CopyFailedError(err_msg)
    time.sleep(retry_delay)
    # upgrade verification_mode to hash on failure
    if always_hash_after_failure:
        verification_mode = 'hash'
        _src_fingerprint = get_file_fingerprint(src, verification_mode, _src_fingerprint)
    return copy_file(src, dest, preserve_metadata = preserve_metadata,
                     retry_count_maximum = retry_count_maximum,
                     retry_delay = min(retry_delay*retry_delay_backoff, retry_delay_maximum),
                     retry_delay_backoff = retry_delay_backoff,
                     retry_delay_maximum = retry_delay_maximum,
                     verification_mode = verification_mode, _current_try = _current_try + 1,
                     _src_fingerprint = _src_fingerprint)


def copy_tree(
    src: str | Path,
    dest: str | Path, *,
    exclude: str | Path | list[str, Path] | None = None,
    parallel: int = 1,
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
    patterns = _normalize_excludes(exclude)
    to_copy = []
    for root, dirs, files in Path(src).walk(on_error = _log_scandir_err):
        rel_root = root.relative_to(src)
        dirs[:] = [d for d in dirs if not _is_excluded(rel_root / d, patterns)]
        for name in files:
            rel_path = rel_root / name
            if _is_excluded(rel_path, patterns):
                logger.debug(f'Directory {src} excluded')
                continue
            src_file = root / name
            dest_file = dest / rel_path
            to_copy.append((src_file, dest_file))
    parallel = min(32, max(1, parallel), len(to_copy))
    completed = 0
    with ThreadPoolExecutor(max_workers = parallel) as executor:
        future_to_filename = {executor.submit(copy_file, src_file, dest_file, **kwargs):src_file\
                             for src_file, dest_file in to_copy}
        for future in concurrent.futures.as_completed(future_to_filename):
            completed += 1
            print(f'\r[{completed} of {len(to_copy)} files copied]', end = '', flush = True)
            try:
                data = future.result()
            except CopyFailedError as exc:
                failures += 1
                if failures == stop_after_n_failures:
                    executor.shutdown(wait = False, cancel_futures = True)
                    err_msg = f'Failed to copy directory {src} to {dest}'
                    logger.error(err_msg)
                    return None
            except Exception as exc:
                logger.exception(exc)
    logger.info(f'Directory {src} copied to {dest}')
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
    dest: str | Path,
    **kwargs
)  -> Path:
    res = copy_file(src, dest, **kwargs)
    if isinstance(res, Path) and res.is_file():
        src.unlink()
        return res
    logger.warning(f'Move {src} to {dest} was unsuccessful')
    return None


def move_tree(
    src: str | Path,
    dest: str | Path,
    **kwargs
) -> Path | None:
    res = copy_tree(src, dest, **kwargs)
    if isinstance(res, Path) and res.is_dir():
        rm_tree(src)


def rm_tree(src: str | Path) -> None:
    for root, dirs, files in src.walk(top_down=False):
        for name in files:
            (root / name).unlink()
        for name in dirs:
            (root / name).rmdir()
    logger.debug(f'Directory {src} removed')
