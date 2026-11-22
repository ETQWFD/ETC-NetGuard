/*
 * ETC NetGuard - tiny native helper (x64)
 *
 * The password flow lives in Python. This DLL only provides the low-level
 * pieces that are more reliable in native code:
 *   - window subclass that can hold WM_CLOSE until the UI unlocks it
 *   - process termination helper for the parental-control blacklist
 *   - a named single-instance mutex
 *
 * It deliberately does NOT touch Task Manager policy, Safe Mode, Ctrl+Alt+Del,
 * keyboard filters or any anti-recovery mechanism.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

static WNDPROC  g_old_proc = NULL;
static HWND     g_guard_hwnd = NULL;
static volatile LONG g_guard_enabled = 0;
static volatile LONG g_close_requested = 0;
static HANDLE   g_instance_mutex = NULL;
static DWORD    g_own_pid = 0;

static LRESULT CALLBACK guard_proc(HWND hwnd, UINT msg, WPARAM wparam, LPARAM lparam)
{
    if (msg == WM_CLOSE && InterlockedCompareExchange(&g_guard_enabled, 1, 1) != 0) {
        InterlockedExchange(&g_close_requested, 1);
        return 0; /* hold the close; Python asks for the password */
    }
    if (msg == WM_NCDESTROY && g_old_proc) {
        WNDPROC old = g_old_proc;
        g_old_proc = NULL;
        g_guard_hwnd = NULL;
        SetWindowLongPtrW(hwnd, GWLP_WNDPROC, (LONG_PTR)old);
        return CallWindowProcW(old, hwnd, msg, wparam, lparam);
    }
    if (g_old_proc)
        return CallWindowProcW(g_old_proc, hwnd, msg, wparam, lparam);
    return DefWindowProcW(hwnd, msg, wparam, lparam);
}

__declspec(dllexport) int ng_install_close_guard(void *hwnd_ptr)
{
    HWND hwnd = (HWND)hwnd_ptr;
    if (!hwnd || !IsWindow(hwnd))
        return 0;
    if (g_guard_hwnd == hwnd && g_old_proc)
        return 1;
    if (g_old_proc && g_guard_hwnd) {
        SetWindowLongPtrW(g_guard_hwnd, GWLP_WNDPROC, (LONG_PTR)g_old_proc);
        g_old_proc = NULL;
    }
    g_guard_hwnd = hwnd;
    g_old_proc = (WNDPROC)SetWindowLongPtrW(hwnd, GWLP_WNDPROC, (LONG_PTR)guard_proc);
    return g_old_proc != NULL;
}

__declspec(dllexport) void ng_set_close_guard(int enabled)
{
    InterlockedExchange(&g_guard_enabled, enabled ? 1 : 0);
    if (!enabled)
        InterlockedExchange(&g_close_requested, 0);
}

__declspec(dllexport) int ng_take_close_request(void)
{
    return (int)InterlockedExchange(&g_close_requested, 0);
}

__declspec(dllexport) int ng_terminate_process(unsigned long pid)
{
    DWORD target = (DWORD)pid;
    if (target == 0 || target == 4)
        return 0;
    if (g_own_pid == 0)
        g_own_pid = GetCurrentProcessId();
    if (target == g_own_pid)
        return 0;
    HANDLE h = OpenProcess(PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION, FALSE, target);
    if (!h)
        return 0;
    BOOL ok = TerminateProcess(h, 1);
    CloseHandle(h);
    return ok ? 1 : 0;
}

__declspec(dllexport) int ng_single_instance(const wchar_t *name)
{
    if (g_instance_mutex)
        return 1;
    g_instance_mutex = CreateMutexW(NULL, FALSE, name);
    if (!g_instance_mutex)
        return 1; /* never block startup because of a mutex failure */
    if (GetLastError() == ERROR_ALREADY_EXISTS) {
        CloseHandle(g_instance_mutex);
        g_instance_mutex = NULL;
        return 0;
    }
    return 1;
}
