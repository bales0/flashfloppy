/* Host test of the actual application dispatcher and vector installation.
 * Build: cc -Wall -Wextra -Werror -Wno-pointer-to-int-cast
 *          tests/emulation_test.c -o out/emulation_test
 */
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>

typedef unsigned int bool_t;
struct ff_cfg {unsigned int marker;};
static const struct ff_cfg dfl_ff_cfg={1};
static struct ff_cfg ff_cfg;
#include "../inc/build_enums.h"
#define TARGET TARGET_dual
#ifndef MCU
#define MCU MCU_stm32f105
#endif
#define TIMER_IRQ_PRI 4
#define aligned(n) __attribute__((aligned(n)))

struct slot { unsigned int value; };
struct track_info { unsigned int value; };
#include "../inc/emulation.h"

static struct { uint32_t vtor; } registers;
#define scb (&registers)
static unsigned int saved, restored, synced;
#define IRQ_save(pri) (assert((pri) == TIMER_IRQ_PRI), saved++, 17)
#define IRQ_restore(pri) (assert((pri) == 17), restored++)
#define cpu_sync() (synced++)

uint32_t vector_table[16 + 90];
static uint32_t *installed_vectors;
static unsigned int calls[2][10];
static uint32_t masks[2];

/* Stubs record exactly which engine is called for each public operation. */
#define ENGINE(prefix, id) \
static void prefix##_init(void) { calls[id][0]++; masks[id] = 0x10 + id; } \
static bool_t prefix##_ribbon(void) { calls[id][1]++; return id; } \
static void prefix##_insert(unsigned int unit, struct slot *slot) \
{ assert(unit == 0 && slot->value == 73); calls[id][2]++; } \
static void prefix##_cancel(void) { calls[id][3]++; } \
static bool_t prefix##_handle(void) { calls[id][4]++; return id; } \
static void prefix##_cyl(uint8_t unit, uint8_t cyl) \
{ assert(unit == 0 && cyl == 42); calls[id][5]++; } \
static void prefix##_track(struct track_info *ti) \
{ calls[id][6]++; ti->value = id; } \
static void prefix##_fintf(void) { calls[id][7]++; } \
static void prefix##_max_cyl(void) { calls[id][8]++; } \
static void prefix##_exti(void) { calls[id][9]++; masks[id] = 0x20 + id; } \
static void prefix##_bind(uint32_t *vectors) \
{ installed_vectors = vectors; vectors[16 + 6] = 0xfdd00000 + id; } \
const struct emulation_ops prefix##_emulation_ops = { \
    .init = prefix##_init, .ribbon_is_reversed = prefix##_ribbon, \
    .insert = prefix##_insert, .cancel = prefix##_cancel, \
    .handle = prefix##_handle, .set_cyl = id ? NULL : prefix##_cyl, \
    .get_track = prefix##_track, .set_fintf_mode = prefix##_fintf, \
    .set_max_cyl = prefix##_max_cyl, .setup_exti = prefix##_exti, \
    .exti_mask = &masks[id], .bind_irqs = prefix##_bind \
};

ENGINE(fdd, 0)
ENGINE(qd, 1)

#include "../src/emulation.c"

#define B_LEFT 1
#define B_RIGHT 2
#define B_SELECT 4
#include "../inc/boot_policy.h"

static void check_boot_policy(void)
{
    unsigned int b;
    for (b = 0; b < 8; b++) {
        bool_t recovery = (b & (B_LEFT|B_RIGHT)) == (B_LEFT|B_RIGHT);
        enum firmware_boot_action dual = recovery ? BOOT_UPDATE
            : (b & B_SELECT) ? BOOT_MENU : BOOT_FIRMWARE;
        enum firmware_boot_action legacy = (recovery || (b & B_SELECT))
            ? BOOT_UPDATE : BOOT_FIRMWARE;
        assert(firmware_boot_action(DUAL_FW_MAGIC, b, 0) == dual);
        assert(firmware_boot_action(0xffffffff, b, 0) == legacy);
        assert(firmware_boot_action(0, b, 0) == legacy);
        /* An explicit update request takes priority over the boot menu. */
        assert(firmware_boot_action(DUAL_FW_MAGIC, b, 1) == BOOT_UPDATE);
        assert(firmware_boot_action(0xffffffff, b, 1) == BOOT_UPDATE);
    }
}

static void check_engine(uint8_t mode, unsigned int id)
{
    struct slot slot = { 73 };
    struct track_info ti = { 99 };
    unsigned int i, j;

    memset(calls, 0, sizeof(calls));
    emulation_select(mode);
    assert(emulation_is_qd() == id);
    assert(emulation_is_apple2() == (mode == EMULATION_APPLE2));
    assert(fdd_cfg == (emulation_is_apple2() ? &dfl_ff_cfg : &ff_cfg));
    assert(((uintptr_t)installed_vectors & 511) == 0);
    assert(registers.vtor == (uint32_t)(uintptr_t)installed_vectors);
    for (i = 0; i < NR_VECTORS; i++)
        assert(installed_vectors[i] == ((i == 22)
               ? 0xfdd00000u + id : vector_table[i]));
    /* Choosing a mode must not initialise either engine before confirmation. */
    assert(calls[0][0] == 0 && calls[1][0] == 0);

    floppy_init();
    assert(motor_chgrst_exti_mask == 0x10 + id);
    assert(floppy_ribbon_is_reversed() == id);
    floppy_insert(0, &slot);
    assert(floppy_handle() == id);
    floppy_set_cyl(0, 42);
    floppy_get_track(&ti);
    assert(ti.value == id);
    floppy_set_fintf_mode();
    floppy_set_max_cyl();
    motor_chgrst_setup_exti();
    assert(motor_chgrst_exti_mask == 0x20 + id);
    floppy_cancel();
    for (j = 0; j < 10; j++) {
        assert(calls[id][j] == ((id == 1 && j == 5) ? 0 : 1));
        assert(calls[1 - id][j] == 0);
    }
}

int main(void)
{
    unsigned int i;
    check_boot_policy();
    for (i = 0; i < sizeof(vector_table)/sizeof(vector_table[0]); i++)
        vector_table[i] = 0x08000000 + i*4;
    check_engine(EMULATION_FDD, 0);
    check_engine(EMULATION_QD, 1);
    check_engine(EMULATION_APPLE2, 0); /* Shares the same FDD core. */
    check_engine(255, 0); /* Older or invalid saved mode falls back to FDD. */
    assert(saved == 4 && restored == 4 && synced == 4);
    return 0;
}
