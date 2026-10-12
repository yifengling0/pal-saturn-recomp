#include "pal_medicine_chest.h"
#include <saturn/sh2.h>
#include "saturn.h"

#ifndef PAL_MEDICINE_ASSETS_VERIFIED
#error "The medicine chest fix requires the exact original asset identity check"
#endif

namespace {
constexpr uint32_t kCall = 0x06028700u;
uint16_t word(uint32_t address) { return static_cast<uint16_t>(ld16(address)); }
void repair_yangzhou_medicine_argument(SH2Context& c, uint32_t address) {
    if (address != kCall || c.cpu != 0 || c.r[4] != 0 || c.r[5] != 1) return;
    // Do not dereference an arbitrary guest script pointer.
    const auto script = ld32(0x0609EE78u);
    if (script != 0x060A008Au) return;
    const pal_medicine_chest::Snapshot s{
        address, static_cast<uint32_t>(c.cpu),
        word(0x060768EEu), word(0x060769EAu), word(0x0609EE84u),
        script, word(script), c.r[4], c.r[5],
        {word(0x0609C4C0u), word(0x0609C4C2u), word(0x0609C4C4u), word(0x0609C4C6u)},
        {word(kCall), word(kCall + 2), word(kCall + 4)}, ld32(0x06028720u)};
    if (!pal_medicine_chest::matches(s)) return;
    c.r[4] = 103;
    sat_note("PAL disc fix medicine-chest-v1: scene=93 event=1661 script=36788 object=0->103 count=1");
}
struct RegisterMedicineChest {
    RegisterMedicineChest() { sh2_hook_add(kCall, repair_yangzhou_medicine_argument); }
} register_medicine_chest;
} // namespace
