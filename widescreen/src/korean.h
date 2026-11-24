#pragma once
#include <windows.h>
// Outside DllMain, before HybridInstall/game initialization. Failure stops startup.
void KoreanPreflight(const char* gameDir);
void KoreanInstall(HMODULE hybrid);
