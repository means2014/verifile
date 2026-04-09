# Migrated to codeberg

This repository has been migrated to [codeberg](https://codeberg.org/cmeans/verifile), and will not be maintained on Github.

# Verifile
`verifile` is a Python utility, inspired by rsync, for transferring files and directories, verifying that each file is accurately copied.
It is designed to be simple, reliable, and fully implemented through the Python standard library.

## Features
- Copy full directory trees
- Verify file integrity
- Pure Python implementation (no additional dependencies)

## Installation
Installation via `uv` is suggested:
```
uv add "verifile @ git+https://github.com/means2014/verifile.git"
```

## API 
### Copy File

Copy a file, `src`, to path `dest`.
Returns Path pointing to `dest` on success, otherwise `None`.
```
copy_file(
    src: str | Path,
    dest: str | Path, *,
    always_hash_after_failure: bool = True,
    chunk_size: int = 1024*1024,
    existing_mode: ExistingBehavior = ExistingBehavior.REPLACE,
    follow_symlinks: bool = True,
    preserve_metadata: bool = False,
    retry_count_maximum: int = 3,
    retry_delay: bool = True,
    retry_delay_backoff: float = 1.5,
    retry_delay_maximum: int = 30,
    verification_mode: VerificationMode = VerificationMode.SIZE_ONLY,
    **kwargs
) -> None | Path
```

`always_hash_after_failure` -> If true, verification_mode will be upgraded to 'hash' for subsequent retries.

`chunk_size` -> Size (in bytes) to copy in each chunk (default: 1MB)

`existing_mode` -> Behavior when `dest` file already exists

  Options:

    - 'error' -- raise Exception
    - 'replace' (default) -- replace existing
    - 'skip' -- ignore and skip

`follow_symlinks` -> If true, and if `src` refers to a symlink, its target will be copied to `dest`.

`preserve_metadata` -> If true, `src` metadata will be preserved.

`retry_count_maximum` -> Maximum number of retries before aborting a failed copy.

`retry_delay` -> Number of seconds to wait before retrying a failed copy.

`retry_delay_backoff` -> Growth factor by which `retry_delay` will be increased with each subsequent failure.

`retry_delay_maximum` -> Maximum number of seconds that `retry_delay` can reach (capping `retry_delay_backoff`).

`verification_mode` -> Defines how `src` and `dest` should be compared for verification.

  Options:
  
  - 'hash' -- Compute 'md5' hash for both files (most secure, but slow)
  - 'metadata' -- Compare file modtime and size (if `preserve_metadata` is False, this is the same as 'size_only')
  - 'size_only' (default) -- Compare file size only
  - 'skip' -- Do not verify

  ### Move File
  
  Move a file, `src`, to path `dest`.
  Returns a path pointing to `dest` on success, otherwise `None`.
  
  ```
  move_file(
    src: str | Path,
    dest: str | Path,
    **kwargs
)  -> Path
```
Shares all arguments with copy file

### Copy Tree

Copy a directory, `src`, to path `dest`.
Returns Path pointing to `dest` on success, otherwise `None`.
```
copy_tree(
    src: str | Path,
    dest: str | Path, *,
    exclude: str | Path | list[str, Path] | None = None,
    parallel: int = 1,
    stop_after_n_failures: int = 1,
    **kwargs
) -> None | Path
```

`exclude` -> Provide a list of strings or paths, relative to `src`, which will be omitted.

`parallel` -> Number of files to copy concurrently.

`stop_after_n_failures` -> Number of failed file copies after which to abort.

### Move Tree

Move a directory, `src`, to path `dest`.
Returns Path pointing to `dest` on success, otherwise `None`.

```
move_tree(
    src: str | Path,
    dest: str | Path, *,
    exclude: str | Path | list[str, Path],
    parallel: int = min(32, (os.process_cpu_count() or 1) + 4),
    stop_after_n_failures: int = 1,
    **kwargs
) -> Path | None
```
Shares all arguments with copy tree
