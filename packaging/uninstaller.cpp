// Pigment Paint — tiny per-user uninstaller.

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX

#include <windows.h>
#include <knownfolders.h>
#include <objbase.h>
#include <shellapi.h>
#include <shlobj.h>
#include <shlwapi.h>

#include <filesystem>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

std::wstring GetSelfPath() {
    std::vector<wchar_t> buffer(32768);
    DWORD length = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (length == 0 || length >= buffer.size()) {
        return {};
    }
    return std::wstring(buffer.data(), length);
}

std::wstring KnownFolder(REFKNOWNFOLDERID folder_id) {
    PWSTR raw = nullptr;
    if (FAILED(SHGetKnownFolderPath(folder_id, KF_FLAG_DEFAULT, nullptr, &raw))) {
        return {};
    }
    std::wstring value(raw);
    CoTaskMemFree(raw);
    return value;
}

bool HasSilentArgument() {
    int argc = 0;
    LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argv == nullptr) {
        return false;
    }
    bool silent = false;
    for (int index = 1; index < argc; ++index) {
        if (_wcsicmp(argv[index], L"/S") == 0 || _wcsicmp(argv[index], L"/SILENT") == 0) {
            silent = true;
            break;
        }
    }
    LocalFree(argv);
    return silent;
}

void RemoveShortcuts() {
    const std::wstring desktop = KnownFolder(FOLDERID_Desktop);
    const std::wstring programs = KnownFolder(FOLDERID_Programs);
    if (!desktop.empty()) {
        const fs::path link = fs::path(desktop) / L"Pigment.lnk";
        DeleteFileW(link.c_str());
        SHChangeNotify(SHCNE_DELETE, SHCNF_PATHW, link.c_str(), nullptr);
    }
    if (!programs.empty()) {
        const fs::path menu = fs::path(programs) / L"Pigment";
        DeleteFileW((menu / L"Pigment.lnk").c_str());
        DeleteFileW((menu / L"Удалить Pigment.lnk").c_str());
        RemoveDirectoryW(menu.c_str());
    }
}

void RemoveRegistryEntry() {
    RegDeleteKeyExW(
        HKEY_CURRENT_USER,
        L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Pigment",
        KEY_WOW64_64KEY,
        0);
}

void ScheduleDirectoryRemoval(const fs::path& directory) {
    wchar_t windows_dir[MAX_PATH]{};
    if (GetWindowsDirectoryW(windows_dir, MAX_PATH) == 0) {
        return;
    }
    const fs::path cmd = fs::path(windows_dir) / L"System32" / L"cmd.exe";
    std::wstring command =
        L"\"" + cmd.wstring() + L"\" /d /c ping 127.0.0.1 -n 3 >nul & rmdir /s /q \"" +
        directory.wstring() + L"\"";

    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESHOWWINDOW;
    startup.wShowWindow = SW_HIDE;
    PROCESS_INFORMATION process{};
    std::vector<wchar_t> mutable_command(command.begin(), command.end());
    mutable_command.push_back(L'\0');
    if (CreateProcessW(
            cmd.c_str(),
            mutable_command.data(),
            nullptr,
            nullptr,
            FALSE,
            CREATE_NO_WINDOW,
            nullptr,
            windows_dir,
            &startup,
            &process)) {
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
    }
}

}  // namespace

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    const bool silent = HasSilentArgument();
    if (!silent) {
        const int answer = MessageBoxW(
            nullptr,
            L"Удалить Pigment Paint с этого компьютера?\n\n"
            L"Будут удалены приложение, ярлыки и записи в меню «Установленные приложения».",
            L"Удаление Pigment Paint",
            MB_ICONQUESTION | MB_YESNO | MB_DEFBUTTON2 | MB_TASKMODAL);
        if (answer != IDYES) {
            CoUninitialize();
            return 1;
        }
    }

    const std::wstring self = GetSelfPath();
    if (self.empty()) {
        CoUninitialize();
        return 2;
    }
    const fs::path install_dir = fs::path(self).parent_path();

    RemoveShortcuts();
    RemoveRegistryEntry();
    ScheduleDirectoryRemoval(install_dir);
    // The helper process waits two seconds, then removes the folder including
    // this running executable after the process exits.
    CoUninitialize();
    return 0;
}
