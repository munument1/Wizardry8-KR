// Entry points for running the *compiled x86* adapter under Unicorn on non-Windows hosts.
#define WIZ8KR_TESTING
#include "../src/korean.cpp"
static unsigned char g_heap[131072];
static unsigned g_used;
static void* __cdecl TestMalloc(size_t n) {
    unsigned offset=g_used;g_used=(g_used+static_cast<unsigned>(n)+15)&~15u;
    return g_used<=sizeof(g_heap)?g_heap+offset:nullptr;
}
static int g_locale;
static char* __cdecl TestLocale(int category,const char* name) {
    if(category!=2 || strcmp(name,".949"))return nullptr;
    g_locale=949;
    return const_cast<char*>(".949");
}
extern "C" __declspec(dllexport) void __cdecl TestInstall(HMODULE hybrid) {
    g_malloc=TestMalloc;g_setlocale=TestLocale;KoreanInstall(hybrid);
}
extern "C" __declspec(dllexport) FontTable* __cdecl TestCreate() {return CreateKoreanTable();}
extern "C" __declspec(dllexport) int __cdecl TestLocaleCode() {return g_locale;}
