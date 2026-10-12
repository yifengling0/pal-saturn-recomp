#include "pal_medicine_chest.h"

#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#include <limits>
#include <type_traits>

using pal_medicine_chest::Snapshot;
using pal_medicine_chest::matches;

namespace {

// Keep the observed identity independent of production constants. In particular,
// script_pc is the unsigned guest word 36788, not a signed 16-bit value.
Snapshot medicine_chest() {
    return Snapshot{
        0x06028700u, 0u, 93u, 1454u, 206u, 0x060A008Au, 36788u,
        0u, 1u, {31u, 0u, 0u, 0u}, {0xD807u, 0x480Bu, 0x0009u},
        0x0604F210u,
    };
}

bool unchanged(const Snapshot& a, const Snapshot& b) {
    // Do not compare padding bytes: only the guest-observable fields matter.
    return a.pc == b.pc && a.cpu == b.cpu && a.scene == b.scene &&
           a.chapter_base == b.chapter_base && a.event_index == b.event_index &&
           a.script_pointer == b.script_pointer && a.script_pc == b.script_pc &&
           a.object == b.object && a.count == b.count &&
           a.command == b.command && a.code == b.code &&
           a.call_target == b.call_target;
}

[[noreturn]] void fail(const char* why, const char* field, std::uint32_t value) {
    std::fprintf(stderr, "%s: %s = 0x%08X\n", why, field,
                 static_cast<unsigned>(value));
    std::exit(EXIT_FAILURE);
}

void check(Snapshot candidate, bool expected, const char* field,
           std::uint32_t value) {
    const Snapshot before = candidate;
    for (int repetition = 0; repetition < 2; ++repetition) {
        if (matches(candidate) != expected) {
            fail(expected ? "valid snapshot rejected" : "near miss accepted",
                 field, value);
        }
        if (!unchanged(candidate, before)) {
            fail("snapshot mutated", field, value);
        }
    }
}

// Test every representable value of every guest-word scalar/array element.
// Besides the nearby values, this covers zero, sign boundaries and 0xFFFF.
void check_word(std::uint16_t Snapshot::*member, const char* name) {
    const Snapshot valid = medicine_chest();
    for (std::uint32_t value = 0; value <= 0xFFFFu; ++value) {
        Snapshot candidate = valid;
        candidate.*member = static_cast<std::uint16_t>(value);
        check(candidate, value == valid.*member, name, value);
    }
}

void check_register(std::uint32_t Snapshot::*member, const char* name) {
    const Snapshot valid = medicine_chest();
    const std::uint32_t expected = valid.*member;
    const std::array<std::uint32_t, 20> values{
        0u, 1u, 2u, 0xFFu, 0x100u, 0x7FFFu, 0x8000u, 0xFFFFu,
        0x10000u, 0x7FFFFFFFu, 0x80000000u, 0xFFFFFFFEu, 0xFFFFFFFFu,
        expected, expected - 1u, expected + 1u,
        expected + 0x10000u, expected + 0x01000000u,
        expected | 0x80000000u, expected | 0xFFFF0000u,
    };
    for (const std::uint32_t value : values) {
        Snapshot candidate = valid;
        candidate.*member = value;
        check(candidate, value == expected, name, value);
    }
    // Every bit is significant, including bits lost by accidental u8/u16 casts.
    for (unsigned bit = 0; bit < 32; ++bit) {
        Snapshot candidate = valid;
        const std::uint32_t value = expected ^ (std::uint32_t{1} << bit);
        candidate.*member = value;
        check(candidate, false, name, value);
    }
}

template <std::size_t N>
void check_words(std::array<std::uint16_t, N> Snapshot::*member,
                 const char* name) {
    const Snapshot valid = medicine_chest();
    for (std::size_t index = 0; index < N; ++index) {
        for (std::uint32_t value = 0; value <= 0xFFFFu; ++value) {
            Snapshot candidate = valid;
            (candidate.*member)[index] = static_cast<std::uint16_t>(value);
            check(candidate, value == (valid.*member)[index], name, value);
        }
    }
}

void check_shared_script_scope() {
    // The same script bytes/pointer must not repair a chest in another scene,
    // event or chapter. Exercise combinations as well as single-field misses.
    for (const std::uint16_t scene : {92u, 93u, 94u, 0xFFFFu}) {
        for (const std::uint16_t event : {205u, 206u, 207u, 0xFFFFu}) {
            for (const std::uint16_t chapter : {1453u, 1454u, 1455u, 0xFFFFu}) {
                Snapshot candidate = medicine_chest();
                candidate.scene = scene;
                candidate.event_index = event;
                candidate.chapter_base = chapter;
                check(candidate, scene == 93u && event == 206u && chapter == 1454u,
                      "shared script scene/event/chapter", event);
            }
        }
    }
}

void check_repeated_and_interleaved_calls() {
    for (unsigned iteration = 0; iteration < 128; ++iteration) {
        check(medicine_chest(), true, "repeated valid snapshot", iteration);
        check(Snapshot{}, false, "empty snapshot", iteration);
        Snapshot wrong_count = medicine_chest();
        wrong_count.count = iteration % 2 == 0 ? 0u : 2u;
        check(wrong_count, false, "wrong count", wrong_count.count);
        Snapshot real_object = medicine_chest();
        real_object.object = iteration + 1u;
        check(real_object, false, "real item object", real_object.object);
        check(medicine_chest(), true, "valid after rejected snapshot", iteration);
    }
}

} // namespace

int main() {
    static_assert(std::is_same_v<decltype(Snapshot{}.script_pc), std::uint16_t>);
    static_assert(std::is_same_v<decltype(Snapshot{}.object), std::uint32_t>);
    static_assert(std::is_same_v<decltype(Snapshot{}.count), std::uint32_t>);
    static_assert(std::numeric_limits<decltype(Snapshot{}.script_pc)>::max() >= 36788u);

    check(medicine_chest(), true, "exact captured snapshot", 36788u);
    check(Snapshot{}, false, "empty snapshot", 0u);

    check_register(&Snapshot::pc, "pc");
    check_register(&Snapshot::cpu, "cpu");
    check_word(&Snapshot::scene, "scene");
    check_word(&Snapshot::chapter_base, "chapter_base");
    check_word(&Snapshot::event_index, "event_index");
    check_register(&Snapshot::script_pointer, "script_pointer");
    check_word(&Snapshot::script_pc, "script_pc");
    check_register(&Snapshot::object, "object");
    check_register(&Snapshot::count, "count");
    check_words(&Snapshot::command, "command word");
    check_words(&Snapshot::code, "code word");
    check_register(&Snapshot::call_target, "call_target");

    check_shared_script_scope();
    check_repeated_and_interleaved_calls();
}
