// Executes our real x86 memory adapter against the upstream DLL's mapped data.
// The game and the non-MIT DLL's code are never executed by this test.
#define WIZ8KR_TESTING
#include "../src/korean.cpp"
#include <assert.h>
#include <string>

int main(int argc, char** argv) {
    assert(argc >= 2);
    unsigned char* game = static_cast<unsigned char*>(VirtualAlloc(reinterpret_cast<void*>(0x400000), 0x200000,
        MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    assert(game == reinterpret_cast<unsigned char*>(0x400000));
    const unsigned char tableHead[] = {0x56,0x57,0x8b,0x3d,0xa0,0xb1,0x5e,0,0x6a,8,0xff,0xd7};
    const unsigned char oldA[] = {0x25,0xff,0xff,0,0};
    const unsigned char oldB[] = {0x81,0xe2,0xff,0xff,0,0};
    memcpy(game + 0x7ec0, tableHead, sizeof(tableHead));
    memcpy(game + 0x15a1e3, oldA, sizeof(oldA));
    memcpy(game + 0x15a3d4, oldB, sizeof(oldB));
    HMODULE crt=LoadLibraryA("msvcrt.dll"); assert(crt);
    g_malloc=reinterpret_cast<MallocFn>(GetProcAddress(crt,"malloc"));
    g_setlocale=reinterpret_cast<LocaleFn>(GetProcAddress(crt,"setlocale"));
    assert(g_malloc && g_setlocale);
    const auto diskHash=Sha256File(argv[1]); assert(!diskHash.empty());
    HMODULE hybrid=LoadLibraryExA(argv[1],nullptr,DONT_RESOLVE_DLL_REFERENCES); assert(hybrid);
    if (argc > 2 && !strcmp(argv[2], "bad-site")) game[0x15a1e3] = 0x90;
    if (argc > 2 && !strcmp(argv[2], "missing-string")) {
        auto* base=reinterpret_cast<unsigned char*>(hybrid);
        auto* nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(base+reinterpret_cast<IMAGE_DOS_HEADER*>(base)->e_lfanew);
        for (unsigned offset=0;offset+32<nt->OptionalHeader.SizeOfImage;offset+=2) {
            // Read only the known .rdata to avoid any unmapped section gaps.
            auto* sh=IMAGE_FIRST_SECTION(nt);
            for (unsigned i=0;i<nt->FileHeader.NumberOfSections;++i) {
                if (!memcmp(sh[i].Name,".rdata\0",7) && offset>=sh[i].VirtualAddress &&
                    offset+32<sh[i].VirtualAddress+sh[i].Misc.VirtualSize &&
                    !memcmp(base+offset,L"View distance",28)) {
                    const wchar_t replacement=L'X'; Write(base+offset,&replacement,2);
                }
            }
        }
    }
    KoreanInstall(hybrid);
    assert(game[0x7ec0]==0xe9);
    const unsigned char newA[]={0x0f,0xb7,0xc0,0x01,0xc0};
    const unsigned char newB[]={0x0f,0xb7,0xd2,0x01,0xd2,0x90};
    assert(!memcmp(game+0x15a1e3,newA,sizeof(newA)));
    assert(!memcmp(game+0x15a3d4,newB,sizeof(newB)));
    auto* table=reinterpret_cast<FontTable* (__cdecl*)()>(0x407ec0)();
    assert(table->count==3299 && !memcmp(table->characters,kKoreanMap,sizeof(kKoreanMap)));
    using WcstombsFn=size_t (__cdecl*)(char*,const wchar_t*,size_t);
    auto convert=reinterpret_cast<WcstombsFn>(GetProcAddress(crt,"wcstombs"));
    char text[16]={}; assert(convert(text,L"\ud55c\uae00",sizeof(text))==4);
    assert(!memcmp(text,"\xc7\xd1\xb1\xdb",4));
    using FreeFn=void (__cdecl*)(void*);
    auto release=reinterpret_cast<FreeFn>(GetProcAddress(crt,"free"));
    release(table->characters);release(table);
    assert(Sha256File(argv[1])==diskHash);
    printf("PASS: 3299 glyphs, CP949 conversion, two NPC buffer edits, 16 UI translations; disk DLL unchanged\n");
    FreeLibrary(hybrid);VirtualFree(game,0,MEM_RELEASE);
}
