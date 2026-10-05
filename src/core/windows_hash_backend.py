"""Backend conservador Win32/NTFS local, exclusivamente stdlib.

Dados via ReOpenFile do objeto validado. READ_ATTRIBUTES sozinho nao bloqueia
share-access; o handle de dados recusa escritores/deleters comuns. A janela
anterior a ReOpenFile e detectada, nao bloqueada. Metadata por path pode seguir
componentes intermediarios e contactar SMB antes de recusar final path/attrs.
OPEN_NO_RECALL e recusa de cloud sao controles conservadores, sem garantia
absoluta contra hidratacao/contato remoto quando componentes intermediarios mudam.
Nao e snapshot atomico nem barreira contra kernel/filtros/mappings existentes.
"""
import ctypes
import ntpath
import os
from contextlib import contextmanager, ExitStack
from ctypes import wintypes as W

from .boundary import normalize_relative_path, resolve_within
from .hasher import HashFailure, check_observation
from .models import FileObservation

_EPOCH = 116444736000000000
_UNSAFE = 0x400 | 0x1000 | 0x40000 | 0x400000
_FLAGS = 0x00200000 | 0x02000000 | 0x00100000  # reparse, backup, no recall


class _FileTime(ctypes.Structure):
    _fields_ = [('low', W.DWORD), ('high', W.DWORD)]


class _Info(ctypes.Structure):
    _fields_ = [('attrs', W.DWORD), ('created', _FileTime),
                ('accessed', _FileTime), ('written', _FileTime),
                ('volume', W.DWORD), ('size_high', W.DWORD), ('size_low', W.DWORD),
                ('links', W.DWORD), ('index_high', W.DWORD), ('index_low', W.DWORD)]


class _Basic(ctypes.Structure):
    _fields_ = [('creation', ctypes.c_int64), ('access', ctypes.c_int64),
                ('write', ctypes.c_int64), ('change', ctypes.c_int64), ('attrs', W.DWORD)]


class _Tag(ctypes.Structure):
    _fields_ = [('attrs', W.DWORD), ('tag', W.DWORD)]


class _Id(ctypes.Structure):
    _fields_ = [('volume', ctypes.c_uint64), ('identifier', ctypes.c_ubyte * 16)]


def _ns(time):
    return (((time.high << 32) | time.low) - _EPOCH) * 100


class _API:
    def __init__(self):
        self.dll = ctypes.WinDLL('kernel32', use_last_error=True)
        declarations = {
            'CreateFileW': ([W.LPCWSTR, W.DWORD, W.DWORD, W.LPVOID, W.DWORD, W.DWORD, W.HANDLE], W.HANDLE),
            'ReOpenFile': ([W.HANDLE, W.DWORD, W.DWORD, W.DWORD], W.HANDLE),
            'CloseHandle': ([W.HANDLE], W.BOOL),
            'GetFileInformationByHandle': ([W.HANDLE, ctypes.POINTER(_Info)], W.BOOL),
            'GetFileInformationByHandleEx': ([W.HANDLE, ctypes.c_int, W.LPVOID, W.DWORD], W.BOOL),
            'GetFinalPathNameByHandleW': ([W.HANDLE, W.LPWSTR, W.DWORD, W.DWORD], W.DWORD),
            'GetFileType': ([W.HANDLE], W.DWORD),
            'GetDriveTypeW': ([W.LPCWSTR], W.UINT),
            'GetVolumeInformationByHandleW': ([W.HANDLE, W.LPWSTR, W.DWORD, ctypes.POINTER(W.DWORD),
                                              ctypes.POINTER(W.DWORD), ctypes.POINTER(W.DWORD),
                                              W.LPWSTR, W.DWORD], W.BOOL),
            'ReadFile': ([W.HANDLE, W.LPVOID, W.DWORD, ctypes.POINTER(W.DWORD), W.LPVOID], W.BOOL),
        }
        for name, (args, result) in declarations.items():
            func = getattr(self.dll, name)
            func.argtypes, func.restype = args, result
            setattr(self, name, func)

    def require(self, value):
        if not value:
            # WinError text/path never leaves this module through HashReport.
            raise ctypes.WinError(ctypes.get_last_error())
        return value

    def valid_handle(self, handle):
        if handle is None or handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    @contextmanager
    def metadata(self, path):
        handle = self.valid_handle(self.CreateFileW(path, 0x80, 1, None, 3, _FLAGS, None))
        try:
            yield handle
        finally:
            self.CloseHandle(handle)

    @contextmanager
    def data(self, handle):
        # OPEN_NO_RECALL nao e aceito por ReOpenFile (WinError 87). A rejeicao
        # previa de atributos/cloud no objeto fixado precede esta reabertura.
        reopened = self.valid_handle(self.ReOpenFile(handle, 0x80000000, 1, 0x00200000 | 0x08000000))
        try:
            yield reopened
        finally:
            self.CloseHandle(reopened)

    def inspect(self, handle):
        if self.GetFileType(handle) != 1:  # FILE_TYPE_DISK
            raise HashFailure('special_file')
        info, tag, basic, identity = _Info(), _Tag(), _Basic(), _Id()
        self.require(self.GetFileInformationByHandle(handle, ctypes.byref(info)))
        self.require(self.GetFileInformationByHandleEx(handle, 9, ctypes.byref(tag), ctypes.sizeof(tag)))
        self.require(self.GetFileInformationByHandleEx(handle, 0, ctypes.byref(basic), ctypes.sizeof(basic)))
        self.require(self.GetFileInformationByHandleEx(handle, 18, ctypes.byref(identity), ctypes.sizeof(identity)))
        if info.attrs != tag.attrs or info.attrs != basic.attrs:
            raise HashFailure('metadata_inconsistent')
        buf = ctypes.create_unicode_buffer(32768)
        length = self.require(self.GetFinalPathNameByHandleW(handle, buf, len(buf), 0))
        if length >= len(buf) or not buf.value.startswith('\\\\?\\'):
            raise HashFailure('final_path_unknown')
        final = buf.value[4:]
        if ntpath.splitdrive(final)[0].startswith('\\\\') or not ntpath.isabs(final):
            raise HashFailure('remote_unsupported')
        kind = 'directory' if info.attrs & 0x10 else 'file'
        # Python 3.12+ usa volume 64 bits e FileId 128 bits, nao o DWORD legado.
        obs = FileObservation(identity.volume, int.from_bytes(bytes(identity.identifier), 'little'),
                              (info.size_high << 32) | info.size_low, _ns(info.written),
                              _ns(info.created), info.links, kind, info.attrs, tag.tag)
        # ChangeTime e adicional aos snapshots Python e detecta mutacoes durante leitura.
        return obs, os.path.normcase(os.path.normpath(final)), basic.change

    def directory_capability(self, handle):
        flags = W.DWORD()
        self.require(self.GetFileInformationByHandleEx(handle, 23, ctypes.byref(flags), ctypes.sizeof(flags)))
        if flags.value != 0:
            raise HashFailure('case_sensitive_unsupported')

    def local_capability(self, handle, base):
        self.local_drive(base)
        serial, max_component, flags = W.DWORD(), W.DWORD(), W.DWORD()
        fs = ctypes.create_unicode_buffer(64)
        self.require(self.GetVolumeInformationByHandleW(handle, None, 0, ctypes.byref(serial),
                     ctypes.byref(max_component), ctypes.byref(flags), fs, len(fs)))
        if fs.value != 'NTFS' or not flags.value & 0x80:  # FILE_SUPPORTS_REPARSE_POINTS
            raise HashFailure('filesystem_unsupported')
        self.directory_capability(handle)

    def local_drive(self, base):
        # Antes de CreateFile: UNC/mapped remote/unknown nao causam open remoto.
        drive, _ = ntpath.splitdrive(base)
        if len(drive) != 2 or drive[1] != ':' or self.GetDriveTypeW(drive + '\\') != 3:
            raise HashFailure('remote_unsupported')


class WindowsHashBackend:
    def __init__(self):
        self.supported = os.name == 'nt' and hasattr(ctypes, 'WinDLL')
        self.api = None
        if self.supported:
            try:
                self.api = _API()
            except (OSError, AttributeError):
                self.supported = False

    @contextmanager
    def pin_root(self, base_dir, expected):
        if not self.supported:
            raise HashFailure('backend_unsupported', root=True)
        drive, _ = ntpath.splitdrive(base_dir)
        if len(drive) != 2 or drive[1] != ':':
            raise HashFailure('remote_unsupported', root=True)
        try:
            self.api.local_drive(base_dir)
            with self.api.metadata(base_dir) as handle:
                self.api.local_capability(handle, base_dir)
                root = _Root(self.api, base_dir, handle, expected)
                root.check()
                yield root
        except HashFailure as exc:
            exc.root = True
            raise
        except OSError as exc:
            # Any error propagating out of the root context invalidates the session.
            raise HashFailure('root_io_failure', root=True) from exc


class _Root:
    def __init__(self, api, base, handle, expected):
        self.api, self.base, self.handle, self.expected = api, base, handle, expected
        self.final = os.path.normcase(os.path.normpath(base))

    def check(self):
        try:
            obs, final, _ = self.api.inspect(self.handle)
            check_observation(self.expected, obs, directory=True)
            if final != self.final:
                raise HashFailure('root_namespace_changed')
            self.api.directory_capability(self.handle)
            # Revalidar namespace da raiz: nao e abertura de dados por path.
            with self.api.metadata(self.base) as current:
                now, name, _ = self.api.inspect(current)
                check_observation(self.expected, now, directory=True)
                if name != final:
                    raise HashFailure('root_namespace_changed')
        except HashFailure as exc:
            exc.root = True
            raise
        except OSError as exc:
            raise HashFailure('root_io_failure', root=True) from exc

    @contextmanager
    def open_file(self, path, expected, observations):
        path = normalize_relative_path(path)
        absolute = resolve_within(self.base, path)
        self.check()
        with ExitStack() as stack:
            pinned = []
            parts = path.split('/')
            for depth in range(1, len(parts)):
                rel = '/'.join(parts[:depth])
                snapshot = observations.get(rel)
                if not isinstance(snapshot, FileObservation):
                    raise HashFailure('ancestor_snapshot_missing')
                handle = stack.enter_context(self.api.metadata(resolve_within(self.base, rel)))
                self.api.directory_capability(handle)
                obs, name, change = self.api.inspect(handle)
                check_observation(snapshot, obs, directory=True)
                if name != os.path.normcase(resolve_within(self.base, rel)) or obs.device != self.expected.device:
                    raise HashFailure('ancestor_namespace_changed')
                pinned.append((handle, snapshot, name, change))
            meta = stack.enter_context(self.api.metadata(absolute))
            obs, name, change = self.api.inspect(meta)
            check_observation(expected, obs)
            if name != os.path.normcase(absolute) or obs.device != self.expected.device:
                raise HashFailure('file_namespace_changed')
            data = stack.enter_context(self.api.data(meta))
            stream = _Stream(self.api, data, expected, name, change, pinned)
            check_observation(expected, stream.observe())
            stream.check_namespace()
            self.check()
            yield stream


class _Stream:
    def __init__(self, api, handle, expected, final, change, pinned):
        self.api, self.handle, self.expected = api, handle, expected
        self.final, self.change, self.pinned = final, change, pinned

    def observe(self):
        obs, name, change = self.api.inspect(self.handle)
        if name != self.final or change != self.change:
            raise HashFailure('file_changed')
        return obs

    def check_namespace(self):
        for handle, snapshot, final, change in self.pinned:
            obs, name, current_change = self.api.inspect(handle)
            check_observation(snapshot, obs, directory=True)
            self.api.directory_capability(handle)
            if name != final or current_change != change:
                raise HashFailure('ancestor_namespace_changed')
        check_observation(self.expected, self.observe())

    def read(self, count):
        if type(count) is not int or not 1 <= count <= 1048576:
            raise HashFailure('invalid_read_size')
        buffer = ctypes.create_string_buffer(count)
        transferred = W.DWORD()
        ok = self.api.ReadFile(self.handle, buffer, count, ctypes.byref(transferred), None)
        if not ok:
            raise HashFailure('read_failure', bytes_read=transferred.value)
        return buffer.raw[:transferred.value]
