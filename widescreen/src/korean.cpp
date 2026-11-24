// Korean compatibility layer for abr17/wiz8-widescreen 1.0.3.
// Original implementation; no decompiled game implementation is included here.
#include "korean.h"
#include "exe_version.h"
#include "korean_data.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

static char g_dir[MAX_PATH];
// Retail addresses stay fixed in production. The Windows unit harness can place
// its synthetic image elsewhere, where the process heap cannot claim it first.
static uintptr_t g_retailBase = 0x400000;
static void* Retail(uintptr_t address) {
    return reinterpret_cast<void*>(g_retailBase + address - 0x400000);
}
static void Note(const char* text) {
#ifdef WIZ8KR_TESTING
    (void)text;
    return;
#endif
    char path[MAX_PATH + 32];
    snprintf(path, sizeof(path), "%swiz8kr.log", g_dir);
    FILE* f = fopen(path, "a");
    if (f) { fprintf(f, "%s\n", text); fclose(f); }
}
[[noreturn]] static void Fail(const char* text) {
    Note(text);
#ifndef WIZ8KR_TESTING
    MessageBoxA(nullptr, text, "Wizardry 8 Korean Widescreen", MB_OK | MB_ICONERROR);
#else
    OutputDebugStringA(text);
#endif
    ExitProcess(1);
}
static void Write(void* target, const void* bytes, size_t size) {
    DWORD old, ignored;
    if (!VirtualProtect(target, size, PAGE_EXECUTE_READWRITE, &old))
        Fail("Cannot make a Korean patch location writable. See wiz8kr.log.");
    memcpy(target, bytes, size);
    if (!FlushInstructionCache(GetCurrentProcess(), target, size) ||
        !VirtualProtect(target, size, old, &ignored))
        Fail("Cannot finish a Korean memory patch. See wiz8kr.log.");
}
static void Jump(uintptr_t from, const void* to) {
    unsigned char code[5] = {0xe9};
    const uint32_t rel = static_cast<uint32_t>(reinterpret_cast<uintptr_t>(to) - from - 5);
    memcpy(code + 1, &rel, sizeof(rel));
    Write(reinterpret_cast<void*>(from), code, sizeof(code));
}
struct FontTable { uint16_t count; uint16_t padding; uint16_t* characters; };
static_assert(sizeof(FontTable) == 8, "32-bit game ABI");
using MallocFn = void* (__cdecl*)(size_t);
using LocaleFn = char* (__cdecl*)(int, const char*);
static MallocFn g_malloc;
static LocaleFn g_setlocale;
static FontTable* __cdecl CreateKoreanTable() {
    // The game's %S conversion uses its own msvcrt locale, not this DLL's CRT.
    if (!g_setlocale(2 /* MSVCRT LC_CTYPE */, ".949"))
        Fail("The game's CRT could not activate Korean CP949.");
    auto* table = static_cast<FontTable*>(g_malloc(sizeof(FontTable)));
    auto* chars = static_cast<uint16_t*>(g_malloc(sizeof(kKoreanMap)));
    if (!table || !chars) Fail("Not enough memory for the Korean font table.");
    memcpy(chars, kKoreanMap, sizeof(kKoreanMap));
    table->count = static_cast<uint16_t>(sizeof(kKoreanMap) / sizeof(kKoreanMap[0]));
    table->padding = 0;
    table->characters = chars;
    Note("Korean font table: 3299 cells, game CRT CP949");
    return table;
}
static std::string FileHash(const char* name) {
    char path[MAX_PATH + 32];
    snprintf(path, sizeof(path), "%s%s", g_dir, name);
    return Sha256File(path);
}
void KoreanPreflight(const char* dir) {
    if (strlen(dir) >= sizeof(g_dir)) Fail("Game folder path is too long.");
    strcpy(g_dir, dir);
    Note("Korean widescreen compatibility 0.3.0-test1");
    char exe[MAX_PATH];
    if (!GetModuleFileNameA(nullptr, exe, sizeof(exe)) ||
        Sha256File(exe) != "18A74FF61C65B8A2D4CFA11FFCE82AD7FEF022A94EAF0C2F217E479E981420D2" ||
        reinterpret_cast<uintptr_t>(GetModuleHandleA(nullptr)) != 0x400000)
        Fail("Use the original GOG/Steam 1.2.4 Wiz8.exe, not the old Korean EXE.");
    const auto dll = FileHash("wiz8hy.dll"), hooks = FileHash("wiz8hy_hooks.txt");
    const bool base = dll == "015B9F1B17983A005D84C9DD351D80A8F42409245577C28F5A6A1B60C19F399B" &&
                      hooks == "608AA4D17F9860036A6C1D985661FCBF4573FA4AF908A9B2D6F092FDA8619237";
    const bool hotfix = dll == "54A0D9426E8B59FA1C69CECC7DB190BA495BA5B02C0389E9AB526C880B1B826F" &&
                        hooks == "E0383A1B418E69C99B3A7432E0FBB571C8633AB662E60B22990863137A45FE69";
    if (!base && !hotfix) Fail("Install Widescreen 1.0.3 (or 1.0.3 hotfix1) with its matching hooks file first.");
    char ini[MAX_PATH + 32], value[16];
    snprintf(ini, sizeof(ini), "%swiz8wide.ini", g_dir);
    GetPrivateProfileStringA("Text", "Cyrillic", "auto", value, sizeof(value), ini);
    if (strcmp(value, "0") != 0)
        Fail("Set [Text] Cyrillic=0 in wiz8wide.ini (run the Korean installer again).");
    HMODULE crt = GetModuleHandleA("msvcrt.dll");
    g_malloc = crt ? reinterpret_cast<MallocFn>(GetProcAddress(crt, "malloc")) : nullptr;
    g_setlocale = crt ? reinterpret_cast<LocaleFn>(GetProcAddress(crt, "setlocale")) : nullptr;
    if (!g_malloc || !g_setlocale) Fail("Cannot find the game's msvcrt allocation/locale functions.");
    Note(base ? "Widescreen 1.0.3 verified" : "Widescreen 1.0.3 hotfix1 verified");
}
void KoreanInstall(HMODULE hybrid) {
    if (!hybrid) Fail("The widescreen engine could not be loaded.");
    const unsigned char tableHead[] = {0x56,0x57,0x8b,0x3d,0xa0,0xb1,0x5e,0,0x6a,8,0xff,0xd7};
    const unsigned char oldA[] = {0x25,0xff,0xff,0,0};
    const unsigned char oldB[] = {0x81,0xe2,0xff,0xff,0,0};
    if (memcmp(Retail(0x407ec0), tableHead, sizeof(tableHead)) ||
        memcmp(Retail(0x55a1e3), oldA, sizeof(oldA)) ||
        memcmp(Retail(0x55a3d4), oldB, sizeof(oldB)))
        Fail("Korean patch sites differ after installing the widescreen hooks. Startup stopped.");
    // Find every expected option literal BEFORE changing anything. Scan only .rdata;
    // the on-disk non-MIT wiz8hy.dll is never edited or redistributed by this project.
    auto* image = reinterpret_cast<unsigned char*>(hybrid);
    auto* nt = reinterpret_cast<IMAGE_NT_HEADERS32*>(image + reinterpret_cast<IMAGE_DOS_HEADER*>(image)->e_lfanew);
    IMAGE_SECTION_HEADER* sections = IMAGE_FIRST_SECTION(nt);
    unsigned char* strings = nullptr;
    size_t size = 0;
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        if (!memcmp(sections[i].Name, ".rdata\0", 7)) {
            strings = image + sections[i].VirtualAddress;
            size = sections[i].Misc.VirtualSize;
        }
    }
    if (!strings) Fail("The widescreen engine has no expected string section.");
    constexpr size_t count = sizeof(kOptionText) / sizeof(kOptionText[0]);
    unsigned char* sites[count] = {};
    for (size_t i = 0; i < count; ++i) {
        const size_t bytes = (wcslen(kOptionText[i].english) + 1) * sizeof(wchar_t);
        if (wcslen(kOptionText[i].korean) > wcslen(kOptionText[i].english))
            Fail("Internal error: Korean option text exceeds its reserved space.");
        for (size_t offset = 0; offset + bytes <= size; offset += 2) {
            if (!memcmp(strings + offset, kOptionText[i].english, bytes)) {
                if (sites[i]) Fail("Ambiguous widescreen option string; startup stopped.");
                sites[i] = strings + offset;
            }
        }
        if (!sites[i]) Fail("Expected widescreen option string is missing; startup stopped.");
    }
    const unsigned char newA[] = {0x0f,0xb7,0xc0,0x01,0xc0};
    const unsigned char newB[] = {0x0f,0xb7,0xd2,0x01,0xd2,0x90};
    Write(Retail(0x55a1e3), newA, sizeof(newA));
    Write(Retail(0x55a3d4), newB, sizeof(newB));
    Jump(reinterpret_cast<uintptr_t>(Retail(0x407ec0)), reinterpret_cast<const void*>(&CreateKoreanTable));
    for (size_t i = 0; i < count; ++i)
        Write(sites[i], kOptionText[i].korean, (wcslen(kOptionText[i].korean) + 1) * sizeof(wchar_t));
    Note("Installed: font table hook, two NPC buffer fixes, 16 Korean option strings. Game files unchanged.");
}
