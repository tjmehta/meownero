"""Windows ownership, exclusive locks and suspended Job Object children.

Contracts: Microsoft Win32 Job Objects, CreateProcessW, CreateFileW,
JOBOBJECT_EXTENDED_LIMIT_INFORMATION and EnumProcessModulesEx documentation.
CreateProcess is called through CPython's existing _winapi binding. Processes
remain suspended until registered in an unnamed, non-inheritable owned job.
Native validation is required; importing on Unix provides no Windows evidence.
"""
import ctypes as C
from ctypes import wintypes as W
from contextlib import contextmanager
import msvcrt
import os
from pathlib import Path
import subprocess
import signal
import tempfile
import threading
import time
import _winapi

k = C.WinDLL('kernel32', use_last_error=True, winmode=0x800)
a = C.WinDLL('advapi32', use_last_error=True, winmode=0x800)


def api(library, name, result, *arguments):
    function = getattr(library, name)
    function.restype, function.argtypes = result, arguments
    return function


def check(value):
    if not value:
        raise C.WinError(C.get_last_error())
    return value


close = api(k, 'CloseHandle', W.BOOL, W.HANDLE)
create_job = api(k, 'CreateJobObjectW', W.HANDLE, C.c_void_p, W.LPCWSTR)
assign = api(k, 'AssignProcessToJobObject', W.BOOL, W.HANDLE, W.HANDLE)
set_info = api(k, 'SetInformationJobObject', W.BOOL, W.HANDLE, C.c_int, C.c_void_p, W.DWORD)
query_info = api(k, 'QueryInformationJobObject', W.BOOL, W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p)
terminate_job = api(k, 'TerminateJobObject', W.BOOL, W.HANDLE, W.UINT)
create_file = api(k, 'CreateFileW', W.HANDLE, W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE)
open_token = api(a, 'OpenProcessToken', W.BOOL, W.HANDLE, W.DWORD, C.POINTER(W.HANDLE))
token_info = api(a, 'GetTokenInformation', W.BOOL, W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD))
security_info = api(a, 'GetSecurityInfo', W.DWORD, W.HANDLE, C.c_int, W.DWORD, C.POINTER(C.c_void_p), C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(C.c_void_p))
equal_sid = api(a, 'EqualSid', W.BOOL, C.c_void_p, C.c_void_p)
local_free = api(k, 'LocalFree', C.c_void_p, C.c_void_p)


class BasicLimit(C.Structure):
    _fields_ = [('process_time', C.c_int64), ('job_time', C.c_int64), ('flags', W.DWORD),
                ('min_working_set', C.c_size_t), ('max_working_set', C.c_size_t),
                ('active_limit', W.DWORD), ('affinity', C.c_size_t), ('priority', W.DWORD), ('scheduling', W.DWORD)]


class ExtendedLimit(C.Structure):
    _fields_ = [('basic', BasicLimit), ('io', C.c_uint64 * 6), ('process_memory', C.c_size_t),
                ('job_memory', C.c_size_t), ('peak_process', C.c_size_t), ('peak_job', C.c_size_t)]


class Accounting(C.Structure):
    _fields_ = [('times', C.c_int64 * 4), ('faults', W.DWORD), ('total', W.DWORD),
                ('active', W.DWORD), ('terminated', W.DWORD)]


class Memory(C.Structure):
    _fields_ = [('length', W.DWORD), ('load', W.DWORD), ('total_phys', C.c_uint64),
                ('available_phys', C.c_uint64), ('total_page', C.c_uint64), ('available_page', C.c_uint64),
                ('total_virtual', C.c_uint64), ('available_virtual', C.c_uint64), ('available_extended', C.c_uint64)]


class FileInfo(C.Structure):
    _fields_ = [('attributes', W.DWORD), ('created', W.FILETIME), ('accessed', W.FILETIME),
                ('written', W.FILETIME), ('volume', W.DWORD), ('size_high', W.DWORD),
                ('size_low', W.DWORD), ('links', W.DWORD), ('index_high', W.DWORD), ('index_low', W.DWORD)]


def available_memory():
    info = Memory()
    info.length = C.sizeof(info)
    check(api(k, 'GlobalMemoryStatusEx', W.BOOL, C.POINTER(Memory))(C.byref(info)))
    return info.available_phys


def native_architecture():
    process_machine, native_machine = W.USHORT(), W.USHORT()
    check(api(k, 'IsWow64Process2', W.BOOL, W.HANDLE, C.POINTER(W.USHORT), C.POINTER(W.USHORT))(_winapi.GetCurrentProcess(), C.byref(process_machine), C.byref(native_machine)))
    return {0x14c: 'i686', 0x8664: 'x86_64', 0xaa64: 'aarch64'}.get(native_machine.value, 'unsupported')


def owned_file(handle):
    """Require the kernel file owner to match the current process token user."""
    token, needed = W.HANDLE(), W.DWORD()
    check(open_token(_winapi.GetCurrentProcess(), 8, C.byref(token)))
    owner, descriptor = C.c_void_p(), C.c_void_p()
    try:
        token_info(token, 1, None, 0, C.byref(needed))
        data = C.create_string_buffer(needed.value)
        check(token_info(token, 1, data, needed.value, C.byref(needed)))
        result = security_info(handle, 1, 1, C.byref(owner), None, None, None, C.byref(descriptor))
        if result:
            raise C.WinError(result)
        if not equal_sid(owner, C.cast(data, C.POINTER(C.c_void_p))[0]):
            raise RuntimeError('unsafe tester lock owner')
    finally:
        if descriptor:
            local_free(descriptor)
        close(token)


@contextmanager
def lock(safe):
    path = safe(Path(tempfile.gettempdir()) / 'meownero-vanguard-tester-windows.lock')
    # No sharing means the kernel serializes writers. Open the reparse point
    # itself so an unsafe existing leaf cannot redirect the lock operation.
    handle = create_file(str(path), 0x80000000 | 0x40000000 | 0x20000, 0, None, 4, 0x00200000, None)
    if handle == C.c_void_p(-1).value:
        if C.get_last_error() in (32, 33):
            raise RuntimeError('tester busy; no processes started')
        raise C.WinError(C.get_last_error())
    try:
        info = FileInfo()
        check(api(k, 'GetFileInformationByHandle', W.BOOL, W.HANDLE, C.POINTER(FileInfo))(handle, C.byref(info)))
        if info.links != 1 or info.attributes & (0x400 | 0x10):
            raise RuntimeError('unsafe tester lock')
        owned_file(handle)
        yield
    finally:
        close(handle)


class Process:
    def __init__(self, handle, pid):
        self.handle, self.pid = handle, pid
        self.returncode = None

    def poll(self):
        if self.returncode is None and _winapi.WaitForSingleObject(self.handle, 0) == 0:
            self.returncode = _winapi.GetExitCodeProcess(self.handle)
        return self.returncode

    def wait(self, timeout):
        if self.returncode is not None:
            return self.returncode
        if _winapi.WaitForSingleObject(self.handle, int(timeout * 1000)) == 258:
            raise subprocess.TimeoutExpired('owned Windows process', timeout)
        self.returncode = _winapi.GetExitCodeProcess(self.handle)
        return self.returncode

    def terminate(self):
        if self.poll() is None:
            _winapi.TerminateProcess(self.handle, 1)

    kill = terminate


class Job:
    def __init__(self, seconds=1200):
        self.handle = check(create_job(None, None))
        self.children = []
        self.expired = False
        limits = ExtendedLimit()
        limits.basic.flags = 0x2000 | 0x200  # KILL_ON_JOB_CLOSE | JOB_MEMORY
        limits.job_memory = min(4 * 1024**3, 2**(C.sizeof(C.c_size_t) * 8) - 1)
        try:
            check(set_info(self.handle, 9, C.byref(limits), C.sizeof(limits)))
        except BaseException:
            close(self.handle)
            raise
        self.timer = threading.Timer(seconds, self.deadline)
        self.timer.daemon = True
        self.timer.start()

    def deadline(self):
        self.expired = True
        terminate_job(self.handle, 124)

    def spawn(self, executable, arguments, stream, env, cwd):
        if self.expired:
            raise RuntimeError('owned Windows journey deadline reached')
        startup = subprocess.STARTUPINFO()
        startup.dwFlags = subprocess.STARTF_USESTDHANDLES
        with open(os.devnull, 'rb') as null:
            handles = [msvcrt.get_osfhandle(null.fileno()), msvcrt.get_osfhandle(stream.fileno())]
            startup.hStdInput, startup.hStdOutput, startup.hStdError = handles[0], handles[1], handles[1]
            startup.lpAttributeList = {'handle_list': handles}
            inherited = [os.get_handle_inheritable(handle) for handle in handles]
            process, thread = None, None
            pending = []
            handlers = {sig: signal.signal(sig, lambda number, frame: pending.append(number))
                        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGBREAK)}
            try:
                for handle in handles:
                    os.set_handle_inheritable(handle, True)
                process, thread, pid, _ = _winapi.CreateProcess(str(executable), subprocess.list2cmdline([str(executable), *arguments]), None, None, True, 4 | 0x08000000 | 0x200, env, str(cwd), startup)
                child = Process(process, pid)
                self.children.append(child)
                check(assign(self.handle, process))
                if self.expired:
                    raise RuntimeError('owned Windows journey deadline reached')
                if api(k, 'ResumeThread', W.DWORD, W.HANDLE)(thread) == 0xffffffff:
                    raise C.WinError(C.get_last_error())
                return child
            except BaseException:
                if process is not None:
                    _winapi.TerminateProcess(process, 1)
                    _winapi.WaitForSingleObject(process, 5000)
                raise
            finally:
                if thread is not None:
                    _winapi.CloseHandle(thread)
                for handle, was_inherited in zip(handles, inherited):
                    os.set_handle_inheritable(handle, was_inherited)
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)
                if pending:
                    raise KeyboardInterrupt('Windows child registered before cancellation')

    def close(self):
        self.timer.cancel()
        self.timer.join(timeout=5)
        try:
            check(terminate_job(self.handle, 1))
            end = time.monotonic() + 10
            while True:
                info = Accounting()
                check(query_info(self.handle, 1, C.byref(info), C.sizeof(info), None))
                if not info.active:
                    break
                if time.monotonic() >= end:
                    raise RuntimeError('owned Windows job cleanup timeout')
                time.sleep(0.05)
            for process in self.children:
                process.wait(timeout=5)
            limits = ExtendedLimit()
            check(query_info(self.handle, 9, C.byref(limits), C.sizeof(limits), None))
            self.cleanup = {'active_processes': info.active, 'total_processes': info.total,
                            'peak_committed_bytes': limits.peak_job,
                            'memory_limit_bytes': limits.job_memory,
                            'children': [{'pid': process.pid, 'exit': process.returncode} for process in self.children]}
        finally:
            for process in self.children:
                _winapi.CloseHandle(process.handle)
            close(self.handle)


def mapped_paths(process):
    buffer, length = C.create_unicode_buffer(32768), W.DWORD(32768)
    check(api(k, 'QueryFullProcessImageNameW', W.BOOL, W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD))(process.handle, 0, buffer, C.byref(length)))
    executable = Path(buffer.value)
    modules, needed = (W.HMODULE * 2048)(), W.DWORD()
    check(api(k, 'K32EnumProcessModulesEx', W.BOOL, W.HANDLE, C.POINTER(W.HMODULE), W.DWORD, C.POINTER(W.DWORD), W.DWORD)(process.handle, modules, C.sizeof(modules), C.byref(needed), 3))
    if needed.value > C.sizeof(modules):
        raise RuntimeError('native module inventory overflow')
    paths = []
    for module in modules[:needed.value // C.sizeof(W.HMODULE)]:
        check(api(k, 'K32GetModuleFileNameExW', W.DWORD, W.HANDLE, W.HMODULE, W.LPWSTR, W.DWORD)(process.handle, module, buffer, len(buffer)))
        paths.append(Path(buffer.value))
    return executable, paths
