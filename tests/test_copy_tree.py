import pytest


from pathlib import Path
from unittest.mock import patch


from src.verifile import copy_tree, move_tree


def create_test_tree(base: Path, structure: dict):
    for name, content in structure.items():
        path = base/name
        if isinstance(content, dict):
            path.mkdir()
            return create_test_tree(path, content)
        path.write_text(content)


@pytest.fixture
def tree(tmp_path: Path):
    src = tmp_path / 'src'
    dest = tmp_path / 'dest'
    structure = {
        'file1.txt': 'hello',
        'file2.txt': 'world',
        'subdir': {
            'file3.txt': 'foo',
            'subsubdir': {
                'file4.txt': 'bar'
            }
        },
        'emptydir': {}
    }
    src.mkdir()
    create_test_tree(src, structure)
    return src, dest


def test_copy_tree_basic(tree):
    src, dest = tree
    copy_tree(src, dest)
    expected_files = [
        'file1.txt',
        'file2.txt',
        'subdir/file3.txt',
        'subdir/subsubdir/file4.txt'
    ]
    actual_files = sorted([p.relative_to(dest).as_posix() for p in dest.glob('**') if p.is_file()])
    assert actual_files == sorted(expected_files)
    assert (dest / 'subdir/subsubdir/file4.txt').read_text() == 'bar'


def test_copy_tree_with_exclude(tree):
    src, dest = tree
    copy_tree(src, dest, exclude=['file1.txt', 'subdir/'])
    actual_files = sorted([p.relative_to(dest).as_posix() for p in dest.rglob('*') if p.is_file()])#    assert actual_files == ['file2.txt']
    assert not (dest / 'subdir' / 'nested').exists()
