/* Host harness for the actual QD image handlers, with an in-memory filesystem.
 * It exports raw tracks and exercises the DMA-facing read/flux pipeline.
 */
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

typedef unsigned int bool_t;
typedef unsigned int UINT;
typedef uint32_t FSIZE_t;
typedef uint32_t DWORD;
typedef struct { uint8_t *data; uint32_t size, pos; void *dir_ptr; } FIL;
typedef struct { unsigned int unused; } FILINFO;
struct da_status_sector { uint8_t unused[512]; };
struct slot { uint32_t size; };
#include "../inc/build_enums.h"
#define TARGET TARGET_quickdisk
#define STK_MHZ 9
#define TRUE 1
#define FALSE 0
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define min_t(t,a,b) ((t)(a) < (t)(b) ? (t)(a) : (t)(b))
#define max_t(t,a,b) ((t)(a) > (t)(b) ? (t)(a) : (t)(b))
#define ASSERT assert
#define barrier() ((void)0)
#define unlikely(x) (x)
#define f_size(fp) ((fp)->size)
#define f_tell(fp) ((fp)->pos)
static void printk(const char *fmt, ...) { (void)fmt; }
#define time_now() ((time_t)0)
#define time_diff(a,b) ((b)-(a))
#define TIME_MHZ 9
#include "../inc/floppy.h"

static void F_lseek(FIL *fp, uint32_t pos)
{
    assert(pos < 1024*1024);
    if (pos > fp->size) {
        memset(fp->data+fp->size, 0, pos-fp->size);
        fp->size = pos;
    }
    fp->pos = pos;
}
static void F_read(FIL *fp, void *out, UINT nr, UINT *read)
{
    assert(fp->pos <= fp->size);
    nr = min_t(UINT, nr, fp->size-fp->pos);
    memcpy(out, fp->data+fp->pos, nr);
    fp->pos += nr;
    if (read) *read = nr;
}
static unsigned int writes;
static void F_write(FIL *fp, const void *buf, UINT nr, UINT *written)
{
    writes++;
    assert(fp->pos+nr < 1024*1024);
    memcpy(fp->data+fp->pos, buf, nr);
    fp->pos += nr;
    fp->size = max_t(uint32_t, fp->size, fp->pos);
    if (written) *written = nr;
}
static uint32_t _rbit32(uint32_t val)
{
    uint32_t out = 0;
    for (unsigned int i = 0; i < 32; i++, val >>= 1)
        out = (out << 1) | (val & 1);
    return out;
}
static void volume_cache_init(void *start, void *end)
{
    /* Catch any record-index overlap with the filesystem cache. */
    memset(start, 0xa5, (uint8_t *)end-(uint8_t *)start);
}
static void volume_cache_metadata_only(FIL *fp) { (void)fp; }

#include "../src/image/qd.c"

bool_t image_read_track(struct image *im)
{
    return im->track_handler->read_track(im);
}

static uint8_t staging[10*1024], bitcells[16*1024];
static struct slot test_slot;
static bool_t no_metadata;

static bool_t mount(struct image *im, uint8_t *data, uint32_t size)
{
    const struct image_handler *handlers[] = {
        &qd_image_handler, &qd_logical_image_handler
    };
    for (unsigned int i = 0; i < ARRAY_SIZE(handlers); i++) {
        memset(im, 0, sizeof(*im));
        memset(staging, 0xcc, sizeof(staging));
        im->fp = (FIL){ data, size, 0, no_metadata ? NULL : data };
        test_slot.size = size;
        im->slot = &test_slot;
        im->bufs.read_data = (struct image_buf){ staging, sizeof(staging), 0, 0 };
        im->bufs.read_bc = (struct image_buf){ bitcells, sizeof(bitcells), 0, 0 };
        im->bufs.write_data = im->bufs.read_data;
        im->track_handler = im->disk_handler = handlers[i];
        if (handlers[i]->open(im)) {
            assert((im->disk_handler->write_track != NULL)
                   == (im->qd.tb != 0));
            assert(im->qd.win_start < im->qd.win_end);
            assert(im->qd.win_end < im->stk_per_rev);
            return TRUE;
        }
    }
    return FALSE;
}

static void verify_seek(struct image *im, const uint8_t *track, uint32_t bit)
{
    uint32_t ticks = bit * im->ticks_per_cell, pos = bit;
    uint16_t flux[97];
    uint32_t interval = 0;
    im->track_handler->setup_track(im, 0, &ticks);
    assert(ticks == bit * im->ticks_per_cell);
    for (unsigned int batch = 0; batch < 4; batch++) {
        image_read_track(im);
        uint16_t nr = im->track_handler->rdata_flux(im, flux, ARRAY_SIZE(flux));
        assert(nr > 0);
        for (unsigned int i = 0; i < nr; i++) {
            do {
                if (pos == im->tracklen_bc) pos = 0;
                interval += im->ticks_per_cell;
                unsigned int pulse = (track[pos/8] >> (pos%8)) & 1;
                pos++;
                if (pulse) break;
            } while (1);
            assert(flux[i] == interval-1);
            interval = 0;
        }
    }
}

int main(int argc, char **argv)
{
    struct image im;
    FILE *fp;
    long size;
    uint8_t *data, *track, *original;
    uint32_t start = 0, pos = 0;
    assert(argc == 3 || (argc == 4 && !strcmp(argv[3], "--no-metadata")));
    fp = fopen(argv[1], "rb");
    assert(fp);
    assert(!fseek(fp, 0, SEEK_END));
    size = ftell(fp);
    assert(size >= 0 && size < 1024*1024);
    rewind(fp);
    data = malloc(1024*1024);
    assert(data && fread(data, 1, size, fp) == (size_t)size);
    fclose(fp);
    original = malloc(size ? size : 1);
    assert(original);
    memcpy(original, data, size);
    no_metadata = (argc == 4) && !strcmp(argv[3], "--no-metadata");
    if (!mount(&im, data, size)) { free(original); free(data); return 2; }
    track = malloc(im.qd.trk_len);
    assert(track);
    im.track_handler->setup_track(&im, 0, &start);
    while (pos < im.qd.trk_len) {
        image_read_track(&im);
        struct image_buf *bc = &im.bufs.read_bc;
        uint32_t nr = (bc->prod-bc->cons)/8;
        assert(nr);
        while (nr-- && pos < im.qd.trk_len) {
            track[pos++] = bitcells[(bc->cons/8) & (bc->len-1)];
            bc->cons += 8;
        }
    }
    if (im.qd.tb == 0) {
        /* Seeks across cache sectors, record boundaries, MFM nibbles,
         * the end of the track, and the first bytes after wrapping.
         */
        uint32_t points[] = {0, 1, 511*8+3, QDL_LEAD_IN*8-1,
                            QDL_LEAD_IN*8, (QDL_LEAD_IN+511)*8+7,
                            (QDL_LEAD_IN+9672)*8, im.tracklen_bc-123};
        for (unsigned int i = 0; i < ARRAY_SIZE(points); i++)
            verify_seek(&im, track, points[i]);
    }
    fp = fopen(argv[2], "wb");
    assert(fp && fwrite(track, 1, im.qd.trk_len, fp) == im.qd.trk_len);
    fclose(fp);
    assert(writes == 0);
    assert(im.fp.size == (uint32_t)size && !memcmp(original, data, size));
    free(original); free(track); free(data);
    return 0;
}
