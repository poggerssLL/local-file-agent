"""Etapa 3: simulacoes deterministicas e fixtures Windows locais isoladas."""
import copy
import hashlib
import itertools
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import patch

from src.core import (DirectoryScanner, FileItem, FileObservation, ScanReport,
                      HashConfig, HashSession)
from src.core.hasher import HashFailure, check_observation
from src.core.windows_hash_backend import WindowsHashBackend

RUNTIME = Path(__file__).resolve().parent / 'fixtures' / 'phase3_runtime'
BASE = str(RUNTIME / 'memory_root')  # Fake backend: nenhum syscall nesse path.


def observation(size=0, inode=1, kind='file', **kwargs):
    return FileObservation(7, inode, size, 10, 20, 1, kind, 0, 0, **kwargs)


class FakeStream:
    def __init__(self, backend, path, expected):
        self.backend, self.path, self.expected = backend, path, expected
        self.offset = 0

    def observe(self):
        return self.backend.current.get(self.path, self.expected)

    def check_namespace(self):
        hook = self.backend.namespace_hook
        if hook:
            hook(self)

    def read(self, count):
        self.backend.requests.append((self.path, count))
        if self.backend.read_error:
            raise self.backend.read_error
        if self.backend.read_hook:
            self.backend.read_hook(self)
        count = min(count, self.backend.short_limit or count)
        data = self.backend.contents[self.path][self.offset:self.offset + count]
        self.offset += len(data)
        self.backend.actual += len(data)
        return data


class FakeRoot:
    def __init__(self, backend):
        self.backend = backend

    def check(self):
        self.backend.checks += 1
        if self.backend.root_error or (self.backend.fail_root_after is not None
                                       and self.backend.checks >= self.backend.fail_root_after):
            raise HashFailure('root_changed', root=True)

    @contextmanager
    def open_file(self, path, expected, observations):
        if self.backend.open_error:
            raise self.backend.open_error
        self.backend.opened += 1
        try:
            if self.backend.before_open:
                self.backend.before_open(path)
            parts = path.split('/')
            for depth in range(1, len(parts)):
                ancestor = '/'.join(parts[:depth])
                check_observation(observations.get(ancestor),
                                  self.backend.current.get(ancestor, observations.get(ancestor)), directory=True)
            stream = FakeStream(self.backend, path, expected)
            check_observation(expected, stream.observe())
            yield stream
        finally:
            self.backend.closed += 1


class FakeBackend:
    supported = True

    def __init__(self, contents):
        self.contents = dict(contents)
        self.current = {}
        self.requests = []
        self.actual = self.opened = self.closed = self.checks = 0
        self.short_limit = None
        self.open_error = self.read_error = None
        self.before_open = self.read_hook = self.namespace_hook = None
        self.root_error = False
        self.fail_root_after = None

    @contextmanager
    def pin_root(self, base, expected):
        check_observation(observation(inode=1000, kind='directory'), expected, directory=True)
        yield FakeRoot(self)


def inventory(contents):
    items, snapshots = [], {}
    for index, (path, data) in enumerate(contents.items(), 1):
        items.append(FileItem(path, len(data), 0, 'untrusted-input-hash'))
        snapshots[path] = observation(len(data), index)
        parts = path.split('/')
        for depth in range(1, len(parts)):
            snapshots['/'.join(parts[:depth])] = observation(inode=2000 + depth, kind='directory')
    return ScanReport(BASE, len(items), sum(i.size_bytes for i in items), items,
                      root_observation=observation(inode=1000, kind='directory'), item_observations=snapshots)


class TestHasher(unittest.TestCase):
    def analyze(self, contents, *, config=None, backend=None, report=None):
        backend = backend or FakeBackend(contents)
        report = report or inventory(contents)
        result = HashSession(BASE, config or HashConfig(enabled=True), _backend=backend).analyze(report)
        self.assertEqual(backend.opened, backend.closed)
        return result, backend

    def test_config_validation_and_limits(self):
        self.assertFalse(HashConfig().enabled)
        self.assertEqual(HashConfig().chunk_size, 262144)
        for name in ('chunk_size', 'max_file_bytes', 'max_total_bytes'):
            for value in (False, True, 0, -1, 1.5, None, float('inf')):
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    HashConfig(**{name: value})
        for chunk in (65535, 1048577):
            with self.assertRaises(ValueError):
                HashConfig(chunk_size=chunk)
        for chunk in (65536, 1048576):
            HashConfig(chunk_size=chunk)
        with self.assertRaises(ValueError):
            HashConfig(enabled=1)

    def test_disabled_and_unsupported_zero_reads(self):
        backend = FakeBackend({'a': b'abc'})
        result = HashSession(BASE, _backend=backend).analyze(inventory(backend.contents))
        self.assertEqual(result.status, 'disabled')
        self.assertEqual(backend.checks, 0)
        backend.supported = False
        result, _ = self.analyze(backend.contents, backend=backend)
        self.assertEqual(result.status, 'unsupported')
        self.assertEqual(backend.requests, [])

    def test_vectors_empty_abc_binary_multiple_chunks(self):
        contents = {'empty': b'', 'abc': b'abc', 'binary': bytes(range(256)) * 2000}
        for chunk in (65536, 262144, 1048576):
            result, backend = self.analyze(contents, config=HashConfig(enabled=True, chunk_size=chunk))
            self.assertEqual(result.status, 'complete')
            self.assertEqual(result.bytes_read, sum(map(len, contents.values())))
            for record in result.results:
                self.assertEqual(record.sha256_hash, hashlib.sha256(contents[record.path]).hexdigest())
            self.assertTrue(all(0 < n <= chunk for _, n in backend.requests))
            self.assertEqual(result.results[0].sha256_hash,
                             'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')

    def test_chunk_boundaries_and_short_positive_reads(self):
        for length in (65535, 65536, 65537, 131072, 131073):
            contents = {'a': b'x' * length}
            backend = FakeBackend(contents)
            backend.short_limit = 13001
            result, _ = self.analyze(contents, backend=backend, config=HashConfig(enabled=True, chunk_size=65536))
            self.assertEqual(result.status, 'complete')
            self.assertEqual(result.bytes_read, length)
            self.assertEqual(result.results[0].sha256_hash, hashlib.sha256(contents['a']).hexdigest())
            self.assertTrue(all(n <= 65536 for _, n in backend.requests))
            self.assertEqual(backend.requests[-1], ('a', 1))

    def test_pairs_trios_empty_same_size_different_content(self):
        contents = {'b': b'abc', 'a': b'abc', 'c': b'abc', 'd': b'xyz', 'e': b'', 'f': b''}
        result, _ = self.analyze(contents)
        self.assertEqual([g.paths for g in result.groups], [('a', 'b', 'c'), ('e', 'f')])
        self.assertEqual(result.logical_redundant_bytes, 6)

    def test_permutations_unicode_global_path_order(self):
        contents = {'z': b'abc', 'sub/a': b'abc', 'x': b'abc', 'Á': b'xyz', 'a': b'xyz'}
        reference = None
        for order in itertools.permutations(contents):
            shuffled = {p: contents[p] for p in order}
            result, _ = self.analyze(shuffled)
            projection = (result.results, result.groups, result.logical_redundant_bytes)
            if reference is None:
                reference = projection
            self.assertEqual(projection, reference)
        self.assertEqual([r.path for r in reference[0]], ['a', 'sub/a', 'x', 'z', 'Á'])

    def test_input_hashes_ignored_original_report_unchanged(self):
        original = inventory({'a': b'abc', 'b': b'xyz'})
        before = copy.deepcopy(original)
        result, _ = self.analyze({'a': b'abc', 'b': b'xyz'}, report=original)
        self.assertEqual(original, before)
        self.assertEqual(result.groups, [])

    def test_inventory_errors_partial_valid_hashes_no_message_copy(self):
        contents = {'a': b'abc', 'b': b'abc'}
        report = inventory(contents)
        report.errors = ['sensitive-root/credential-value', 'inventory limit reached']
        before = copy.deepcopy(report)
        result, _ = self.analyze(contents, report=report)
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.scope, 'provided_inventory')
        self.assertEqual(result.inventory_error_count, 2)
        self.assertEqual(result.errors, [])
        self.assertTrue(all(r.sha256_hash == hashlib.sha256(b'abc').hexdigest() for r in result.results))
        self.assertEqual(result.groups[0].paths, ('a', 'b'))
        self.assertEqual(report, before)
        self.assertNotIn('sensitive-root', repr(result))
        self.assertNotIn('credential-value', repr(result))

    def test_duplicate_items_aliases_objects_and_conflicts(self):
        contents = {'a': b'abc', 'b': b'abc'}
        report = inventory(contents)
        report.items += [copy.copy(report.items[0]), replace(report.items[0], path='./a')]
        result, backend = self.analyze(contents, report=report)
        self.assertEqual(result.logical_redundant_bytes, 3)
        self.assertEqual(len(result.results), 2)
        report.item_observations['b'] = report.item_observations['a']
        result, _ = self.analyze(contents, report=report)
        self.assertEqual(result.groups, [])
        self.assertIn('duplicate_object', [e.code for e in result.errors])
        report.items += [replace(report.items[0], size_bytes=4)]
        result, _ = self.analyze(contents, report=report)
        self.assertIn('conflicting_item', [e.code for e in result.errors])

    def test_hostile_input_zero_item_syscalls_no_raw_leak(self):
        for hostile in ('../sentinel', 'C:/private/token', 'C:secret', '//server/share',
                        'a:ads', 'NUL', 'a\nprivate', '', None, '/absolute'):
            report = inventory({})
            report.items = [FileItem(hostile, 3, 0)]
            result, backend = self.analyze({}, report=report)
            self.assertEqual(backend.opened, 0)
            self.assertEqual(backend.requests, [])
            self.assertEqual(result.errors[0].path, None)
            self.assertEqual(result.errors[0].code, 'invalid_path')

    def test_missing_snapshots_root_mismatch_stale_identity(self):
        for mode in ('root_missing', 'item_missing', 'ancestor_missing', 'root_mismatch', 'root_stale', 'item_stale'):
            contents = {'sub/a': b'abc'}
            report = inventory(contents)
            backend = FakeBackend(contents)
            if mode == 'root_missing': report.root_observation = None
            if mode == 'item_missing': report.item_observations.clear()
            if mode == 'ancestor_missing': report.item_observations.pop('sub')
            if mode == 'root_mismatch': report.base_dir += '_sibling'
            if mode == 'root_stale': report.root_observation = replace(report.root_observation, inode=999)
            if mode == 'item_stale': backend.current['sub/a'] = replace(report.item_observations['sub/a'], inode=999)
            result, backend = self.analyze(contents, report=report, backend=backend)
            self.assertEqual(backend.requests, [], mode)
            self.assertFalse(any(r.sha256_hash for r in result.results))

    def test_cloud_offline_recall_reparse_special_hardlinks_zero_reads(self):
        for attrs, tag, nlink, kind in ((0x400, 0x9000001A, 1, 'file'), (0x1000, 0, 1, 'file'),
             (0x40000, 0, 1, 'file'), (0x400000, 0, 1, 'file'), (0, 3, 1, 'file'),
             (0, 0, 2, 'file'), (0, 0, 1, 'special')):
            contents = {'a': b'abc'}
            report = inventory(contents)
            report.item_observations['a'] = replace(report.item_observations['a'], attributes=attrs,
                                                    reparse_tag=tag, nlink=nlink, kind=kind)
            result, backend = self.analyze(contents, report=report)
            self.assertEqual(backend.requests, [])
            self.assertEqual(result.results[0].sha256_hash, None)

    def test_ancestor_reparse_and_leaf_swap_before_read(self):
        contents = {'sub/a': b'abc'}
        for target in ('sub', 'sub/a'):
            report, backend = inventory(contents), FakeBackend(contents)
            def swap(path):
                backend.current[target] = replace(report.item_observations[target],
                                                  attributes=0x400, reparse_tag=0xA0000003, inode=999)
            backend.before_open = swap
            result, backend = self.analyze(contents, backend=backend, report=report)
            self.assertEqual(backend.requests, [])

    def test_open_stat_read_failures_sanitized_cleanup(self):
        for stage in ('open', 'stat', 'read'):
            backend = FakeBackend({'a': b'abc'})
            exc = PermissionError(13, 'secret absolute path and token')
            if stage == 'open': backend.open_error = exc
            if stage == 'stat': backend.namespace_hook = lambda stream: (_ for _ in ()).throw(exc)
            if stage == 'read': backend.read_error = exc
            result, _ = self.analyze(backend.contents, backend=backend)
            self.assertEqual(result.errors[0].code, 'io_failure')
            self.assertEqual(result.errors[0].errno, 13)
            self.assertNotIn('secret', repr(result))
            self.assertEqual(result.results[0].sha256_hash, None)

    def test_failed_read_accounts_partial_transfer(self):
        backend = FakeBackend({'a': b'abc'})
        backend.read_error = HashFailure('read_failure', bytes_read=2)
        result, _ = self.analyze(backend.contents, backend=backend)
        self.assertEqual(result.bytes_read, 2)
        self.assertEqual(result.results[0].bytes_read, 2)
        self.assertIsNone(result.results[0].sha256_hash)

    def test_truncate_grow_mutate_identity_same_size_mtime(self):
        for mode in ('truncate', 'grow', 'mtime', 'identity', 'ctime'):
            contents = {'a': b'x' * 65537}
            backend, report = FakeBackend(contents), inventory(contents)
            def mutate(stream):
                if stream.offset == 0:
                    if mode == 'truncate': backend.contents['a'] = b'x'
                    if mode == 'grow': backend.contents['a'] += b'yy'
                    if mode in ('mtime', 'identity', 'ctime'):
                        field = {'mtime': 'mtime_ns', 'identity': 'inode', 'ctime': 'ctime_ns'}[mode]
                        backend.current['a'] = replace(report.item_observations['a'], **{field: 9999})
            backend.read_hook = mutate
            result, _ = self.analyze(contents, backend=backend, report=report,
                                     config=HashConfig(enabled=True, chunk_size=65536))
            self.assertIsNone(result.results[0].sha256_hash, mode)
            self.assertLessEqual(result.bytes_read, 65538)
            self.assertEqual(result.bytes_read, backend.actual)
            self.assertEqual(result.groups, [])

    def test_budgets_probe_and_failures_consumed(self):
        for config in (HashConfig(enabled=True, max_file_bytes=3), HashConfig(enabled=True, max_total_bytes=3)):
            result, backend = self.analyze({'a': b'abc'}, config=config)
            self.assertEqual(backend.requests, [])
            self.assertIsNone(result.results[0].sha256_hash)
        result, backend = self.analyze({'a': b'abc'}, config=HashConfig(enabled=True, max_total_bytes=4))
        self.assertEqual(result.status, 'complete')
        self.assertEqual(result.bytes_read, 3)
        contents = {'a': b'abc', 'b': b'abc'}
        backend = FakeBackend(contents)
        backend.contents['a'] = b'abcd'
        result, _ = self.analyze(contents, backend=backend, config=HashConfig(enabled=True, max_total_bytes=7))
        self.assertEqual(result.bytes_read, 4)
        self.assertEqual([r.sha256_hash for r in result.results], [None, None])
        self.assertEqual([n for p, n in backend.requests if p == 'b'], [])

    def test_root_failure_invalidates_previous_digests(self):
        backend = FakeBackend({'a': b'abc', 'b': b'abc'})
        backend.fail_root_after = 6
        result, _ = self.analyze(backend.contents, backend=backend)
        self.assertEqual(result.status, 'invalid_root')
        self.assertTrue(all(r.sha256_hash is None for r in result.results))
        self.assertEqual(result.groups, [])


class RuntimeFixture(unittest.TestCase):
    def setUp(self):
        RUNTIME.mkdir(exist_ok=True)
        self.assertEqual(os.path.realpath(RUNTIME), str(RUNTIME))
        self.temp = tempfile.TemporaryDirectory(dir=RUNTIME, prefix='phase3_')
        self.fixture = Path(self.temp.name)
        self.root = self.fixture / 'authorized'
        self.root.mkdir()
        self.addCleanup(self.safe_cleanup)

    def safe_cleanup(self):
        # Verificacao imediatamente anterior a delecao; walk nao segue links.
        absolute = os.path.abspath(self.temp.name)
        self.assertEqual(os.path.commonpath([str(RUNTIME), absolute]), str(RUNTIME))
        self.assertNotEqual(absolute, str(RUNTIME))
        self.assertFalse(os.path.islink(absolute))
        self.assertEqual(os.path.realpath(absolute), absolute)
        for parent, dirs, files in os.walk(absolute, topdown=True, followlinks=False):
            for name in list(dirs):
                path = os.path.join(parent, name)
                if os.path.islink(path):
                    os.unlink(path)
                    dirs.remove(name)
                elif getattr(os.path, 'isjunction', lambda p: False)(path):
                    os.rmdir(path)  # junction itself only, never its target
                    dirs.remove(name)
        self.temp.cleanup()

    def write(self, rel, data):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


class TestSnapshots(RuntimeFixture):
    def test_scanner_metadata_only_and_additive_snapshots(self):
        path = self.write('sub/a', b'abc')
        with patch('builtins.open', side_effect=AssertionError('content read forbidden')):
            report = DirectoryScanner(str(self.root)).scan()
        self.assertIsInstance(report.root_observation, FileObservation)
        self.assertEqual(report.item_observations['sub/a'].inode, path.stat().st_ino)
        self.assertEqual(report.item_observations['sub'].kind, 'directory')
        self.assertEqual(report.items[0].sha256_hash, None)


@unittest.skipUnless(os.name == 'nt', 'Windows nativo indisponivel: lacuna de handles/sharing/reparse')
class TestWindowsNative(RuntimeFixture):
    def run_hash(self, report=None, backend=None):
        return HashSession(str(self.root), HashConfig(enabled=True), _backend=backend).analyze(
            report or DirectoryScanner(str(self.root)).scan())

    def test_native_hash_identity_content_size_mtime_preserved(self):
        self.write('abc', b'abc')
        self.write('empty', b'')
        self.write('sub/binary', bytes(range(256)) * 2000)
        paths = [p for p in self.root.rglob('*') if p.is_file()]
        before = {p: (p.read_bytes(), p.stat().st_size, p.stat().st_mtime_ns) for p in paths}
        result = self.run_hash()
        self.assertEqual(result.status, 'complete', result)
        for record in result.results:
            self.assertEqual(record.sha256_hash, hashlib.sha256(before[self.root / record.path][0]).hexdigest())
        after = {p: (p.read_bytes(), p.stat().st_size, p.stat().st_mtime_ns) for p in paths}
        self.assertEqual(before, after)

    def test_native_inventory_limit_partial_success_original_preserved(self):
        from src.core import ScannerConfig
        self.write('a', b'abc')
        self.write('b', b'xyz')
        report = DirectoryScanner(str(self.root), ScannerConfig(max_files_limit=1)).scan()
        self.assertEqual(len(report.items), 1)
        self.assertEqual(len(report.errors), 1)
        before = copy.deepcopy(report)
        result = self.run_hash(report)
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.scope, 'provided_inventory')
        self.assertEqual(result.inventory_error_count, 1)
        self.assertEqual(result.results[0].sha256_hash, hashlib.sha256(b'abc').hexdigest())
        self.assertEqual(result.errors, [])
        self.assertNotIn(report.errors[0], repr(result))
        self.assertEqual(report, before)

    def test_native_hardlinks_zero_reads(self):
        path = self.write('a', b'abc')
        os.link(path, self.root / 'b')
        result = self.run_hash()
        self.assertEqual(result.bytes_read, 0)
        self.assertEqual(result.groups, [])
        self.assertEqual([e.code for e in result.errors], ['hardlink_skipped', 'hardlink_skipped'])

    def test_native_identity_replacement_same_size_mtime(self):
        path = self.write('a', b'abc')
        report = DirectoryScanner(str(self.root)).scan()
        stat = path.stat()
        replacement = self.fixture / 'replacement'
        replacement.write_bytes(b'xyz')
        os.utime(replacement, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        os.replace(replacement, path)
        os.utime(self.root, ns=(self.root.stat().st_atime_ns, report.root_observation.mtime_ns))
        result = self.run_hash(report)
        self.assertEqual(result.status, 'partial')
        self.assertIn('snapshot_changed', [e.code for e in result.errors])
        self.assertEqual(result.bytes_read, 0)
        self.assertTrue(all(r.sha256_hash is None for r in result.results))

    def test_native_root_changed_zero_reads(self):
        self.write('a', b'abc')
        report = DirectoryScanner(str(self.root)).scan()
        os.rename(self.root, self.fixture / 'oldroot')
        self.root.mkdir()
        (self.root / 'a').write_bytes(b'xyz')
        result = self.run_hash(report)
        self.assertEqual(result.status, 'invalid_root')
        self.assertEqual(result.bytes_read, 0)

    def test_native_handles_deny_writes_deletes_and_close(self):
        path = self.write('sub/a', b'abc')
        report = DirectoryScanner(str(self.root)).scan()
        backend = WindowsHashBackend()
        with backend.pin_root(str(self.root), report.root_observation) as root:
            with root.open_file('sub/a', report.item_observations['sub/a'], report.item_observations) as stream:
                self.assertEqual(stream.read(3), b'abc')
                with self.assertRaises(PermissionError):
                    with path.open('wb'):
                        pass
                for target in (path, path.parent, self.root):
                    with self.assertRaises(PermissionError):
                        os.rename(target, target.with_name(target.name + '_swap'))
        # Finally fechou todos os handles: escrita/rename passam apos sair.
        self.assertEqual(path.read_bytes(), b'abc')
        path.write_bytes(b'xyz')
        os.rename(path.parent, path.parent.with_name('renamed'))

    def test_native_leaf_symlink_external_before_first_read(self):
        path = self.write('a', b'abc')
        sentinel = self.fixture / 'sentinel'
        sentinel.write_bytes(b'EXTERNAL_SENTINEL')
        report = DirectoryScanner(str(self.root)).scan()
        path.unlink()
        try:
            os.symlink(sentinel, path)
        except OSError as exc:
            self.skipTest(f'symlink privilege unavailable: winerror={getattr(exc, "winerror", None)}; external-leaf proof gap')
        os.utime(self.root, ns=(self.root.stat().st_atime_ns, report.root_observation.mtime_ns))
        backend = WindowsHashBackend()
        with patch.object(backend.api, 'ReadFile', wraps=backend.api.ReadFile) as read:
            result = self.run_hash(report, backend)
            read.assert_not_called()
        self.assertEqual(result.bytes_read, 0)
        self.assertTrue(all(r.sha256_hash is None for r in result.results))
        self.assertEqual(sentinel.read_bytes(), b'EXTERNAL_SENTINEL')

    def test_native_ancestor_junction_external_before_first_read(self):
        self.write('sub/a', b'abc')
        external = self.fixture / 'sentinel_dir'
        external.mkdir()
        (external / 'a').write_bytes(b'EXTERNAL_SENTINEL')
        report = DirectoryScanner(str(self.root)).scan()
        os.rename(self.root / 'sub', self.root / 'original')
        # Sem shell dinâmico/destrutivo: mklink e apenas criacao de junction sintetica.
        proc = subprocess.run(['cmd', '/c', 'mklink', '/J', str(self.root / 'sub'), str(external)],
                              capture_output=True, check=False)
        if proc.returncode:
            self.skipTest('junction unavailable; external-ancestor proof gap')
        # Restaurar mtime da raiz exercita o ancestral, nao apenas root mismatch.
        os.utime(self.root, ns=(self.root.stat().st_atime_ns, report.root_observation.mtime_ns))
        backend = WindowsHashBackend()
        with patch.object(backend.api, 'ReadFile', wraps=backend.api.ReadFile) as read:
            result = self.run_hash(report, backend)
            read.assert_not_called()
        self.assertEqual(result.status, 'partial')
        self.assertIn('unsafe_attributes', [e.code for e in result.errors])
        self.assertEqual(result.bytes_read, 0)
        self.assertTrue(all(r.sha256_hash is None for r in result.results))
        self.assertEqual((external / 'a').read_bytes(), b'EXTERNAL_SENTINEL')

    def test_native_leaf_external_hardlink_swap_no_sentinel_reads(self):
        path = self.write('a', b'abc')
        sentinel = self.fixture / 'sentinel'
        sentinel.write_bytes(b'EXTERNAL_SENTINEL')
        report = DirectoryScanner(str(self.root)).scan()
        path.unlink()
        os.link(sentinel, path)
        os.utime(self.root, ns=(self.root.stat().st_atime_ns, report.root_observation.mtime_ns))
        backend = WindowsHashBackend()
        with patch.object(backend.api, 'ReadFile', wraps=backend.api.ReadFile) as read:
            result = self.run_hash(report, backend)
            read.assert_not_called()
        self.assertEqual(result.status, 'partial')
        self.assertEqual([e.code for e in result.errors], ['hardlink_skipped'])
        self.assertEqual(sentinel.read_bytes(), b'EXTERNAL_SENTINEL')

    def test_native_failure_closes_metadata_data_and_ancestors(self):
        path = self.write('sub/a', b'abc')
        backend = WindowsHashBackend()
        api = backend.api
        with patch.object(api, 'CreateFileW', wraps=api.CreateFileW) as opened, \
             patch.object(api, 'ReOpenFile', wraps=api.ReOpenFile) as reopened, \
             patch.object(api, 'CloseHandle', wraps=api.CloseHandle) as closed, \
             patch.object(api, 'ReadFile', side_effect=OSError(5, 'private message')):
            result = self.run_hash(backend=backend)
        self.assertEqual(opened.call_count + reopened.call_count, closed.call_count)
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.bytes_read, 0)
        self.assertNotIn('private', repr(result))
        path.write_bytes(b'xyz')
        os.rename(path.parent, path.parent.with_name('renamed'))

    def test_native_capability_failures_zero_data_reads(self):
        self.write('a', b'abc')
        for code in ('case_sensitive_unsupported', 'filesystem_unsupported', 'capability_unknown'):
            backend = WindowsHashBackend()
            with patch.object(backend.api, 'local_capability', side_effect=HashFailure(code)), \
                 patch.object(backend.api, 'ReadFile', wraps=backend.api.ReadFile) as read:
                result = self.run_hash(backend=backend)
                read.assert_not_called()
            self.assertEqual(result.status, 'invalid_root')
            self.assertEqual(result.errors[0].code, code)

    def test_native_unc_rejected_before_any_open(self):
        backend = WindowsHashBackend()
        with patch.object(backend.api, 'CreateFileW', wraps=backend.api.CreateFileW) as opened:
            with self.assertRaises(HashFailure):
                with backend.pin_root(r'\\synthetic_server\share', observation(kind='directory')):
                    self.fail('UNC accepted')
            opened.assert_not_called()

    def test_native_mapped_remote_unknown_drive_zero_opens(self):
        for drive_kind in (0, 1, 2, 4, 5, 6):
            backend = WindowsHashBackend()
            with patch.object(backend.api, 'GetDriveTypeW', return_value=drive_kind), \
                 patch.object(backend.api, 'CreateFileW', wraps=backend.api.CreateFileW) as opened:
                result = self.run_hash(backend=backend)
                opened.assert_not_called()
            self.assertEqual(result.status, 'invalid_root')
            self.assertEqual(result.bytes_read, 0)

    def test_native_reopen_handle_is_same_object_before_read(self):
        self.write('a', b'abc')
        external = self.fixture / 'sentinel'
        external.write_bytes(b'EXTERNAL_SENTINEL')
        backend = WindowsHashBackend()
        api = backend.api
        # Injecao Win32 controlada: devolver OUTRO objeto em vez de ReOpenFile.
        # Prova a verificacao do handle de dados, sem ler o sentinela.
        def wrong_reopen(*args):
            return api.CreateFileW(str(external), 0x80000000, 1, None, 3, 0x00200000, None)
        with patch.object(api, 'ReOpenFile', side_effect=wrong_reopen), \
             patch.object(api, 'ReadFile', wraps=api.ReadFile) as read:
            result = self.run_hash(backend=backend)
            read.assert_not_called()
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.bytes_read, 0)
        self.assertEqual(external.read_bytes(), b'EXTERNAL_SENTINEL')

    def test_native_final_path_rejects_external_ancestor_handle(self):
        self.write('sub/a', b'abc')
        external = self.fixture / 'sentinel_dir'
        external.mkdir()
        (external / 'a').write_bytes(b'EXTERNAL_SENTINEL')
        report = DirectoryScanner(str(self.root)).scan()
        # Injecao de troca do namespace: snapshot forjado igual ao alvo para
        # isolar a verificacao de final path/ancestralidade (simulacao + handles reais).
        report.item_observations['sub'] = FileObservation.from_stat(external.stat())
        backend = WindowsHashBackend()
        api, original = backend.api, backend.api.CreateFileW
        def redirected(path, *args):
            return original(str(external) if path == str(self.root / 'sub') else path, *args)
        with patch.object(api, 'CreateFileW', side_effect=redirected), \
             patch.object(api, 'ReadFile', wraps=api.ReadFile) as read:
            result = self.run_hash(report, backend)
            read.assert_not_called()
        self.assertEqual([e.code for e in result.errors], ['ancestor_namespace_changed'])

    def test_native_cloud_metadata_simulated_no_reopen_or_reads(self):
        self.write('sub/a', b'abc')
        for target in ('sub', 'sub/a'):
            backend = WindowsHashBackend()
            api, original = backend.api, backend.api.inspect
            expected_path = os.path.normcase(str(self.root / target))
            def cloud(handle):
                obs, final, change = original(handle)
                if final == expected_path:
                    obs = replace(obs, attributes=obs.attributes | 0x400, reparse_tag=0x9000001A)
                return obs, final, change
            with patch.object(api, 'inspect', side_effect=cloud), \
                 patch.object(api, 'ReOpenFile', wraps=api.ReOpenFile) as reopened, \
                 patch.object(api, 'ReadFile', wraps=api.ReadFile) as read:
                result = self.run_hash(backend=backend)
                read.assert_not_called()
                reopened.assert_not_called()
            self.assertEqual([e.code for e in result.errors], ['unsafe_attributes'])
