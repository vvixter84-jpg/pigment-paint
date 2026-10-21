// Pigment Paint — self-contained per-user installer.
//
// The installer carries PigmentPortable.zip appended to its own executable.
// It expands the archive straight into %LOCALAPPDATA%\Programs\Pigment using
// miniz. No temporary directory and no second setup executable are used.

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX

#include <windows.h>
#include <commctrl.h>
#include <knownfolders.h>
#include <objbase.h>
#include <shellapi.h>
#include <shlobj.h>
#include <shlwapi.h>
#include <shobjidl.h>

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include "miniz.h"

namespace fs = std::filesystem;

namespace {

constexpr int kIconResourceId = 101;
constexpr int kProgressWindowWidth = 470;
constexpr int kProgressWindowHeight = 176;
const char kPayloadMagic[8] = {'P', 'I', 'G', 'M', 'N', 'T', '0', '1'};

#pragma pack(push, 1)
struct PayloadFooter {
    char magic[8];
    uint64_t payload_offset;
    uint64_t payload_size;
};
#pragma pack(pop)

HWND g_window = nullptr;
HWND g_status = nullptr;
HWND g_progress = nullptr;
HFONT g_font = nullptr;
bool g_installing = true;
std::wstring g_failure;

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

std::wstring Utf8ToWide(const std::string& text) {
    if (text.empty()) {
        return {};
    }
    int length = MultiByteToWideChar(
        CP_UTF8, MB_ERR_INVALID_CHARS, text.data(), static_cast<int>(text.size()), nullptr, 0);
    if (length <= 0) {
        length = MultiByteToWideChar(
            CP_UTF8, 0, text.data(), static_cast<int>(text.size()), nullptr, 0);
    }
    if (length <= 0) {
        return {};
    }
    std::wstring result(static_cast<size_t>(length), L'\0');
    MultiByteToWideChar(
        CP_UTF8, 0, text.data(), static_cast<int>(text.size()), result.data(), length);
    return result;
}

std::string WideToUtf8(const std::wstring& text) {
    if (text.empty()) {
        return {};
    }
    const int length = WideCharToMultiByte(
        CP_UTF8, 0, text.data(), static_cast<int>(text.size()), nullptr, 0, nullptr, nullptr);
    if (length <= 0) {
        return {};
    }
    std::string result(static_cast<size_t>(length), '\0');
    WideCharToMultiByte(
        CP_UTF8,
        0,
        text.data(),
        static_cast<int>(text.size()),
        result.data(),
        length,
        nullptr,
        nullptr);
    return result;
}

void WriteInstallLog(const std::string& line) {
    const std::wstring local_app_data = KnownFolder(FOLDERID_LocalAppData);
    if (local_app_data.empty()) {
        return;
    }
    const fs::path log_path = fs::path(local_app_data) / L"PigmentSetup.log";
    HANDLE file = CreateFileW(
        log_path.c_str(),
        GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    SetFilePointer(file, 0, nullptr, FILE_END);
    const std::string content = line + "\r\n";
    DWORD written = 0;
    WriteFile(file, content.data(), static_cast<DWORD>(content.size()), &written, nullptr);
    CloseHandle(file);
}

bool FailStage(const std::wstring& text) {
    g_failure = text;
    WriteInstallLog("FAIL: " + WideToUtf8(text));
    return false;
}

LRESULT CALLBACK WindowProc(HWND window, UINT message, WPARAM w_param, LPARAM l_param) {
    switch (message) {
        case WM_CLOSE:
            if (g_installing) {
                return 0;
            }
            break;
        case WM_DESTROY:
            PostQuitMessage(0);
            return 0;
        default:
            break;
    }
    return DefWindowProcW(window, message, w_param, l_param);
}

void PumpMessages() {
    MSG message{};
    while (PeekMessageW(&message, nullptr, 0, 0, PM_REMOVE)) {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }
}

bool CreateProgressWindow() {
    INITCOMMONCONTROLSEX controls{};
    controls.dwSize = sizeof(controls);
    controls.dwICC = ICC_PROGRESS_CLASS | ICC_STANDARD_CLASSES;
    InitCommonControlsEx(&controls);

    const wchar_t* class_name = L"PigmentSetupWindow";
    WNDCLASSEXW window_class{};
    window_class.cbSize = sizeof(window_class);
    window_class.style = CS_HREDRAW | CS_VREDRAW;
    window_class.lpfnWndProc = WindowProc;
    window_class.hInstance = GetModuleHandleW(nullptr);
    window_class.hIcon = LoadIconW(GetModuleHandleW(nullptr), MAKEINTRESOURCEW(kIconResourceId));
    window_class.hIconSm = window_class.hIcon;
    window_class.hCursor = LoadCursorW(nullptr, IDC_ARROW);
    window_class.hbrBackground = reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1);
    window_class.lpszClassName = class_name;
    if (!RegisterClassExW(&window_class) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS) {
        return false;
    }

    RECT work_area{};
    SystemParametersInfoW(SPI_GETWORKAREA, 0, &work_area, 0);
    const int x = work_area.left + ((work_area.right - work_area.left) - kProgressWindowWidth) / 2;
    const int y = work_area.top + ((work_area.bottom - work_area.top) - kProgressWindowHeight) / 2;

    g_window = CreateWindowExW(
        WS_EX_APPWINDOW,
        class_name,
        L"Установка Pigment Paint",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU,
        x,
        y,
        kProgressWindowWidth,
        kProgressWindowHeight,
        nullptr,
        nullptr,
        window_class.hInstance,
        nullptr);
    if (!g_window) {
        return false;
    }

    g_font = CreateFontW(
        -16,
        0,
        0,
        0,
        FW_NORMAL,
        FALSE,
        FALSE,
        FALSE,
        DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS,
        CLIP_DEFAULT_PRECIS,
        CLEARTYPE_QUALITY,
        DEFAULT_PITCH | FF_DONTCARE,
        L"Segoe UI");

    HWND title = CreateWindowExW(
        0,
        L"STATIC",
        L"Устанавливаю Pigment Paint…",
        WS_CHILD | WS_VISIBLE,
        24,
        22,
        410,
        26,
        g_window,
        nullptr,
        window_class.hInstance,
        nullptr);
    g_status = CreateWindowExW(
        0,
        L"STATIC",
        L"Подготавливаю файлы",
        WS_CHILD | WS_VISIBLE,
        24,
        55,
        410,
        24,
        g_window,
        nullptr,
        window_class.hInstance,
        nullptr);
    g_progress = CreateWindowExW(
        0,
        PROGRESS_CLASSW,
        nullptr,
        WS_CHILD | WS_VISIBLE | PBS_SMOOTH,
        24,
        92,
        410,
        18,
        g_window,
        nullptr,
        window_class.hInstance,
        nullptr);
    HWND note = CreateWindowExW(
        0,
        L"STATIC",
        L"Ярлык Pigment будет добавлен на Рабочий стол.",
        WS_CHILD | WS_VISIBLE,
        24,
        121,
        410,
        20,
        g_window,
        nullptr,
        window_class.hInstance,
        nullptr);
    for (HWND label : {title, g_status, g_progress, note}) {
        SendMessageW(label, WM_SETFONT, reinterpret_cast<WPARAM>(g_font), TRUE);
    }

    ShowWindow(g_window, SW_SHOWNORMAL);
    UpdateWindow(g_window);
    PumpMessages();
    return true;
}

void CloseProgressWindow() {
    g_installing = false;
    if (g_window) {
        DestroyWindow(g_window);
        g_window = nullptr;
    }
    if (g_font) {
        DeleteObject(g_font);
        g_font = nullptr;
    }
    PumpMessages();
}

void SetStatus(const std::wstring& text, int progress = -1) {
    if (g_status) {
        SetWindowTextW(g_status, text.c_str());
    }
    if (progress >= 0 && g_progress) {
        SendMessageW(g_progress, PBM_SETPOS, static_cast<WPARAM>(progress), 0);
    }
    PumpMessages();
}

void ShowError(const std::wstring& text) {
    CloseProgressWindow();
    MessageBoxW(
        nullptr,
        text.c_str(),
        L"Pigment — ошибка установки",
        MB_ICONERROR | MB_OK | MB_TASKMODAL);
}

bool ReadPayload(std::vector<uint8_t>& payload) {
    const std::wstring self = GetSelfPath();
    if (self.empty()) {
        return false;
    }
    std::ifstream file(fs::path(self), std::ios::binary | std::ios::ate);
    if (!file) {
        return false;
    }
    const std::streamoff file_size = file.tellg();
    if (file_size < static_cast<std::streamoff>(sizeof(PayloadFooter))) {
        return false;
    }
    file.seekg(file_size - static_cast<std::streamoff>(sizeof(PayloadFooter)));
    PayloadFooter footer{};
    file.read(reinterpret_cast<char*>(&footer), sizeof(footer));
    if (std::memcmp(footer.magic, kPayloadMagic, sizeof(kPayloadMagic)) != 0) {
        return false;
    }
    const uint64_t max_size = static_cast<uint64_t>(file_size);
    if (footer.payload_size == 0 || footer.payload_offset > max_size ||
        footer.payload_size > max_size - footer.payload_offset ||
        footer.payload_offset + footer.payload_size + sizeof(PayloadFooter) != max_size) {
        return false;
    }
    if (footer.payload_size > 512ull * 1024ull * 1024ull) {
        return false;
    }
    payload.resize(static_cast<size_t>(footer.payload_size));
    file.seekg(static_cast<std::streamoff>(footer.payload_offset));
    file.read(reinterpret_cast<char*>(payload.data()), static_cast<std::streamsize>(payload.size()));
    return static_cast<size_t>(file.gcount()) == payload.size();
}

bool SafeRelativePath(const std::string& raw) {
    if (raw.empty() || raw[0] == '/' || raw[0] == '\\' || raw.find(':') != std::string::npos) {
        return false;
    }
    std::string path = raw;
    std::replace(path.begin(), path.end(), '\\', '/');
    size_t start = 0;
    while (start <= path.size()) {
        const size_t end = path.find('/', start);
        const std::string part = path.substr(start, end == std::string::npos ? std::string::npos : end - start);
        if (part == "..") {
            return false;
        }
        if (end == std::string::npos) {
            break;
        }
        start = end + 1;
    }
    return true;
}

bool WriteAll(HANDLE file, const unsigned char* data, size_t size) {
    size_t written_total = 0;
    while (written_total < size) {
        const DWORD chunk = static_cast<DWORD>(std::min<size_t>(size - written_total, 1u << 20));
        DWORD written = 0;
        if (!WriteFile(file, data + written_total, chunk, &written, nullptr) || written != chunk) {
            return false;
        }
        written_total += written;
    }
    return true;
}

bool ExtractPayload(
    const std::vector<uint8_t>& payload,
    const fs::path& install_dir,
    int& file_count) {
    mz_zip_archive archive{};
    if (!mz_zip_reader_init_mem(&archive, payload.data(), payload.size(), 0)) {
        return FailStage(L"miniz: не удалось открыть встроенный ZIP");
    }

    const mz_uint count = mz_zip_reader_get_num_files(&archive);
    if (count == 0) {
        mz_zip_reader_end(&archive);
        return FailStage(L"Встроенный ZIP пуст");
    }
    file_count = static_cast<int>(count);
    if (g_progress) {
        SendMessageW(
            g_progress,
            PBM_SETRANGE32,
            0,
            static_cast<LPARAM>(count));
    }

    std::error_code error;
    fs::create_directories(install_dir, error);
    if (error) {
        mz_zip_reader_end(&archive);
        return FailStage(
            L"Не удалось создать папку установки: " + install_dir.wstring() +
            L" (код " + std::to_wstring(error.value()) + L")");
    }

    for (mz_uint index = 0; index < count; ++index) {
        char filename[4096]{};
        if (mz_zip_reader_get_filename(
                &archive, index, filename, static_cast<mz_uint>(sizeof(filename))) == 0) {
            mz_zip_reader_end(&archive);
            return FailStage(
                L"Не удалось прочитать имя файла #" + std::to_wstring(index));
        }
        const std::string raw_name(filename);
        if (!SafeRelativePath(raw_name)) {
            mz_zip_reader_end(&archive);
            return FailStage(
                L"Небезопасный путь во встроенном архиве: " + Utf8ToWide(raw_name));
        }

        std::string normalized = raw_name;
        std::replace(normalized.begin(), normalized.end(), '\\', '/');
        if (!normalized.empty() && normalized.back() == '/') {
            error.clear();
            fs::create_directories(install_dir / fs::path(Utf8ToWide(normalized)), error);
            continue;
        }

        const std::wstring wide_name = Utf8ToWide(normalized);
        if (wide_name.empty()) {
            mz_zip_reader_end(&archive);
            return FailStage(
                L"Не удалось декодировать имя файла: " + Utf8ToWide(raw_name));
        }
        const fs::path destination = install_dir / fs::path(wide_name);
        error.clear();
        fs::create_directories(destination.parent_path(), error);
        if (error) {
            mz_zip_reader_end(&archive);
            return FailStage(
                L"Не удалось создать папку: " + destination.parent_path().wstring() +
                L" (код " + std::to_wstring(error.value()) + L")");
        }

        size_t size = 0;
        void* data = mz_zip_reader_extract_to_heap(&archive, index, &size, 0);
        if (!data && size != 0) {
            mz_zip_reader_end(&archive);
            return FailStage(L"Не удалось распаковать файл: " + wide_name);
        }
        HANDLE file = CreateFileW(
            destination.c_str(),
            GENERIC_WRITE,
            0,
            nullptr,
            CREATE_ALWAYS,
            FILE_ATTRIBUTE_NORMAL,
            nullptr);
        if (file == INVALID_HANDLE_VALUE) {
            const DWORD code = GetLastError();
            mz_free(data);
            mz_zip_reader_end(&archive);
            return FailStage(
                L"Не удалось создать файл: " + destination.wstring() +
                L" (Windows error " + std::to_wstring(code) + L")");
        }
        const bool written = WriteAll(
            file, static_cast<const unsigned char*>(data), size);
        const DWORD write_error = written ? ERROR_SUCCESS : GetLastError();
        FlushFileBuffers(file);
        CloseHandle(file);
        mz_free(data);
        if (!written) {
            mz_zip_reader_end(&archive);
            return FailStage(
                L"Не удалось записать файл: " + destination.wstring() +
                L" (Windows error " + std::to_wstring(write_error) + L")");
        }

        SetStatus(
            L"Устанавливаю файлы… " + std::to_wstring(index + 1) + L" из " +
                std::to_wstring(count),
            static_cast<int>(index + 1));
    }

    mz_zip_reader_end(&archive);
    return true;
}

bool CreateShortcut(
    const fs::path& link_path,
    const fs::path& target,
    const fs::path& working_directory,
    const std::wstring& description) {
    IShellLinkW* link = nullptr;
    HRESULT result = CoCreateInstance(
        CLSID_ShellLink,
        nullptr,
        CLSCTX_INPROC_SERVER,
        IID_IShellLinkW,
        reinterpret_cast<void**>(&link));
    if (FAILED(result) || link == nullptr) {
        return false;
    }
    link->SetPath(target.c_str());
    link->SetWorkingDirectory(working_directory.c_str());
    link->SetIconLocation(target.c_str(), 0);
    link->SetDescription(description.c_str());

    IPersistFile* file = nullptr;
    bool saved = false;
    if (SUCCEEDED(link->QueryInterface(IID_IPersistFile, reinterpret_cast<void**>(&file)))) {
        saved = SUCCEEDED(file->Save(link_path.c_str(), TRUE));
        file->Release();
    }
    link->Release();
    return saved;
}

bool CreateShortcuts(const fs::path& install_dir) {
    const std::wstring desktop = KnownFolder(FOLDERID_Desktop);
    const std::wstring programs = KnownFolder(FOLDERID_Programs);
    if (desktop.empty() || programs.empty()) {
        return false;
    }

    const fs::path exe = install_dir / L"Pigment.exe";
    const fs::path uninstaller = install_dir / L"Uninstall.exe";
    const fs::path desktop_link = fs::path(desktop) / L"Pigment.lnk";
    bool ok = CreateShortcut(desktop_link, exe, install_dir, L"Pigment Paint");
    if (ok) {
        SHChangeNotify(SHCNE_CREATE, SHCNF_PATHW, desktop_link.c_str(), nullptr);
    }

    const fs::path menu_dir = fs::path(programs) / L"Pigment";
    std::error_code error;
    fs::create_directories(menu_dir, error);
    ok = CreateShortcut(menu_dir / L"Pigment.lnk", exe, install_dir, L"Pigment Paint") && ok;
    ok = CreateShortcut(
             menu_dir / L"Удалить Pigment.lnk",
             uninstaller,
             install_dir,
             L"Удалить Pigment Paint") &&
         ok;
    return ok;
}

bool WriteString(HKEY key, const wchar_t* name, const std::wstring& value) {
    return RegSetValueExW(
               key,
               name,
               0,
               REG_SZ,
               reinterpret_cast<const BYTE*>(value.c_str()),
               static_cast<DWORD>((value.size() + 1) * sizeof(wchar_t))) == ERROR_SUCCESS;
}

bool WriteRegistry(const fs::path& install_dir) {
    const wchar_t* key_path =
        L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Pigment";
    HKEY key = nullptr;
    if (RegCreateKeyExW(
            HKEY_CURRENT_USER,
            key_path,
            0,
            nullptr,
            0,
            KEY_WRITE | KEY_WOW64_64KEY,
            nullptr,
            &key,
            nullptr) != ERROR_SUCCESS) {
        return false;
    }

    const fs::path exe = install_dir / L"Pigment.exe";
    const fs::path uninstaller = install_dir / L"Uninstall.exe";
    bool ok = true;
    ok = WriteString(key, L"DisplayName", L"Pigment Paint") && ok;
    ok = WriteString(key, L"DisplayVersion", L"1.0.0") && ok;
    ok = WriteString(key, L"Publisher", L"Pigment Studio") && ok;
    ok = WriteString(key, L"DisplayIcon", exe.wstring()) && ok;
    ok = WriteString(key, L"InstallLocation", install_dir.wstring()) && ok;
    ok = WriteString(key, L"UninstallString", L"\"" + uninstaller.wstring() + L"\"") && ok;
    ok = WriteString(
             key,
             L"QuietUninstallString",
             L"\"" + uninstaller.wstring() + L"\" /S") &&
         ok;

    DWORD one = 1;
    ok = RegSetValueExW(
             key,
             L"NoModify",
             0,
             REG_DWORD,
             reinterpret_cast<const BYTE*>(&one),
             sizeof(one)) == ERROR_SUCCESS &&
         ok;
    ok = RegSetValueExW(
             key,
             L"NoRepair",
             0,
             REG_DWORD,
             reinterpret_cast<const BYTE*>(&one),
             sizeof(one)) == ERROR_SUCCESS &&
         ok;
    DWORD estimated_size = 94000;
    ok = RegSetValueExW(
             key,
             L"EstimatedSize",
             0,
             REG_DWORD,
             reinterpret_cast<const BYTE*>(&estimated_size),
             sizeof(estimated_size)) == ERROR_SUCCESS &&
         ok;

    RegCloseKey(key);
    return ok;
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

bool IsLowIntegrity() {
    HANDLE token = nullptr;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token)) {
        return false;
    }
    DWORD size = 0;
    GetTokenInformation(token, TokenIntegrityLevel, nullptr, 0, &size);
    std::vector<BYTE> buffer(size);
    DWORD rid = SECURITY_MANDATORY_MEDIUM_RID;
    if (GetTokenInformation(token, TokenIntegrityLevel, buffer.data(), size, &size)) {
        auto* label = reinterpret_cast<TOKEN_MANDATORY_LABEL*>(buffer.data());
        const DWORD count = *GetSidSubAuthorityCount(label->Label.Sid);
        rid = *GetSidSubAuthority(label->Label.Sid, count - 1);
    }
    CloseHandle(token);
    return rid < SECURITY_MANDATORY_MEDIUM_RID;
}

}  // namespace

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    const bool silent = HasSilentArgument();
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    if (IsLowIntegrity()) {
        MessageBoxW(
            nullptr,
            L"Установщик запущен из папки с ограниченными правами.\n\n"
            L"Скопируйте PigmentSetup.exe на Рабочий стол (или в «Загрузки») "
            L"и запустите оттуда. Тогда ярлык Pigment появится на Рабочем столе.",
            L"Pigment — установка",
            MB_ICONWARNING | MB_OK | MB_TASKMODAL);
        CoUninitialize();
        return 6;
    }
    if (!silent && !CreateProgressWindow()) {
        CoUninitialize();
        return 1;
    }

    const std::wstring local_app_data = KnownFolder(FOLDERID_LocalAppData);
    if (local_app_data.empty()) {
        ShowError(L"Не удалось найти папку пользователя LocalAppData.");
        CoUninitialize();
        return 2;
    }
    const fs::path install_dir =
        fs::path(local_app_data) / L"Programs" / L"Pigment";

    if (!silent) {
        SetStatus(L"Читаю встроенные файлы…", 0);
    }
    std::vector<uint8_t> payload;
    WriteInstallLog("Installer started");
    if (!ReadPayload(payload)) {
        WriteInstallLog("FAIL: embedded payload could not be read");
        ShowError(
            L"Не удалось прочитать встроенный архив приложения.\n"
            L"Скачайте PigmentSetup.exe заново — файл повреждён.");
        CoUninitialize();
        return 3;
    }
    WriteInstallLog("Payload size: " + std::to_string(payload.size()));

    int file_count = 0;
    if (!ExtractPayload(payload, install_dir, file_count)) {
        ShowError(
            L"Не удалось распаковать приложение.\n\n" + g_failure +
            L"\n\nПапка установки: " + install_dir.wstring() +
            L"\nПодробности: %LOCALAPPDATA%\\PigmentSetup.log");
        CoUninitialize();
        return 4;
    }
    WriteInstallLog("Files extracted: " + std::to_string(file_count));

    if (!silent) {
        SetStatus(L"Создаю ярлык на Рабочем столе…", file_count);
    }
    const bool shortcuts_ok = CreateShortcuts(install_dir);
    const bool registry_ok = WriteRegistry(install_dir);
    WriteInstallLog(
        std::string("Shortcuts: ") + (shortcuts_ok ? "ok" : "failed") +
        "; registry: " + (registry_ok ? "ok" : "failed"));

    if (!silent) {
        if (!shortcuts_ok) {
            MessageBoxW(
                nullptr,
                L"Приложение установлено, но ярлык создать не удалось.\n"
                L"Запустите Pigment.exe из папки установки.",
                L"Pigment",
                MB_ICONWARNING | MB_OK | MB_TASKMODAL);
        } else if (!registry_ok) {
            MessageBoxW(
                nullptr,
                L"Приложение установлено, но запись для удаления в параметрах "
                L"Windows создать не удалось.",
                L"Pigment",
                MB_ICONWARNING | MB_OK | MB_TASKMODAL);
        }
        SetStatus(L"Готово. Запускаю Pigment…", file_count);
        Sleep(250);
        CloseProgressWindow();
        const fs::path exe = install_dir / L"Pigment.exe";
        HINSTANCE launched = ShellExecuteW(
            nullptr,
            L"open",
            exe.c_str(),
            nullptr,
            install_dir.c_str(),
            SW_SHOWNORMAL);
        if (reinterpret_cast<INT_PTR>(launched) <= 32) {
            MessageBoxW(
                nullptr,
                L"Pigment установлен, но не удалось запустить приложение.\n"
                L"Откройте ярлык Pigment на Рабочем столе.",
                L"Pigment",
                MB_ICONWARNING | MB_OK | MB_TASKMODAL);
        }
    }

    if (shortcuts_ok && registry_ok) {
        const fs::path log_path = fs::path(local_app_data) / L"PigmentSetup.log";
        DeleteFileW(log_path.c_str());
    }
    CoUninitialize();
    return (shortcuts_ok || silent) ? 0 : 5;
}
