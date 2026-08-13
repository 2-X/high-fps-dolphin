/*
 * memhelper.c — ad-hoc-signed Mach memory bridge for macmem.py
 *
 * Usage: memhelper <pid>
 *   Attaches to the given PID via task_for_pid (requires debugger
 *   entitlement; no sudo needed when signed correctly).  Prints "OK" on
 *   success or "ERR attach kr=<n>" on failure, then exits.
 *
 *   On success, reads one command per line from stdin and writes one
 *   response line per command to stdout.  All I/O is line-buffered.
 *   Exit 0 on EOF.
 *
 * Commands (addresses / lengths in hex, with or without leading "0x"):
 *
 *   READ <hexaddr> <hexlen>
 *     mach_vm_read_overwrite → "OK <hexbytes>" or "ERR kr=<n>"
 *     Max length: 1 MiB (1048576 bytes → 2097152 hex chars + NUL)
 *
 *   WRITE <hexaddr> <hexbytes>
 *     Decode hex payload, mach_vm_write → "OK" or "ERR kr=<n>"
 *     Max payload: 5.5 KB (BSMSO comm-buffer subregion; WRITE line ≤~12 KB)
 *
 *   REGIONS
 *     Enumerate readable committed regions via mach_vm_region.
 *     Per region: "REGION <hexbase> <hexsize>"
 *     Finish: "OK"
 *
 *   SCAN <hexaddr> <hexlen> <hexmagic>
 *     Scan [addr, addr+len) on a 4-byte stride for the 4-byte <hexmagic>
 *     (8 hex chars, big-endian as bytes appear in memory).  Reads region
 *     memory natively in chunks — only match addresses cross the pipe.
 *     Per match: "HIT <hexaddr>"
 *     Finish: "OK"
 */

#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

#define MAX_READ_LEN  (1024 * 1024)          /* 1 MiB */
#define MAX_HEX_OUT   (MAX_READ_LEN * 2 + 2) /* hex chars + NUL */

/* Convert a single hex nibble to its value; returns -1 on bad input. */
static int hex_val(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

/*
 * Decode a hex string (no spaces) into dst.
 * hex_len must be even.  Returns number of bytes written, or -1 on error.
 */
static ssize_t hex_decode(const char *hex, size_t hex_len, uint8_t *dst, size_t dst_cap)
{
    if (hex_len % 2 != 0) return -1;
    size_t n = hex_len / 2;
    if (n > dst_cap) return -1;
    for (size_t i = 0; i < n; i++) {
        int hi = hex_val(hex[i * 2]);
        int lo = hex_val(hex[i * 2 + 1]);
        if (hi < 0 || lo < 0) return -1;
        dst[i] = (uint8_t)((hi << 4) | lo);
    }
    return (ssize_t)n;
}

/* Encode bytes as lowercase hex into dst (must be 2*n+1 bytes).  */
static void hex_encode(const uint8_t *src, size_t n, char *dst)
{
    static const char digits[] = "0123456789abcdef";
    for (size_t i = 0; i < n; i++) {
        dst[i * 2]     = digits[(src[i] >> 4) & 0xf];
        dst[i * 2 + 1] = digits[src[i]        & 0xf];
    }
    dst[n * 2] = '\0';
}

/* -------------------------------------------------------------------------
 * Command handlers
 * ---------------------------------------------------------------------- */

static void cmd_read(mach_port_t task, const char *addr_str, const char *len_str)
{
    uint64_t addr = strtoull(addr_str, NULL, 16);
    uint64_t rlen = strtoull(len_str, NULL, 16);

    if (rlen == 0 || rlen > MAX_READ_LEN) {
        printf("ERR kr=invalid_len\n");
        fflush(stdout);
        return;
    }

    uint8_t *buf = malloc(rlen);
    if (!buf) {
        printf("ERR kr=oom\n");
        fflush(stdout);
        return;
    }

    mach_vm_size_t out_len = 0;
    kern_return_t kr = mach_vm_read_overwrite(
        task, addr, rlen,
        (mach_vm_address_t)buf, &out_len
    );

    if (kr != KERN_SUCCESS || out_len != rlen) {
        printf("ERR kr=%d\n", kr);
        fflush(stdout);
        free(buf);
        return;
    }

    char *hex = malloc(MAX_HEX_OUT);
    if (!hex) {
        printf("ERR kr=oom\n");
        fflush(stdout);
        free(buf);
        return;
    }
    hex_encode(buf, rlen, hex);
    printf("OK %s\n", hex);
    fflush(stdout);
    free(hex);
    free(buf);
}

static void cmd_write(mach_port_t task, const char *addr_str, const char *hex_payload)
{
    uint64_t addr = strtoull(addr_str, NULL, 16);
    size_t hex_len = strlen(hex_payload);

    /* Strip trailing newline / whitespace that getline may have left */
    while (hex_len > 0 && (hex_payload[hex_len - 1] == '\n' ||
                            hex_payload[hex_len - 1] == '\r' ||
                            hex_payload[hex_len - 1] == ' '))
        hex_len--;

    if (hex_len == 0 || hex_len % 2 != 0) {
        printf("ERR kr=invalid_hex\n");
        fflush(stdout);
        return;
    }

    size_t nbytes = hex_len / 2;
    uint8_t *buf = malloc(nbytes);
    if (!buf) {
        printf("ERR kr=oom\n");
        fflush(stdout);
        return;
    }

    if (hex_decode(hex_payload, hex_len, buf, nbytes) < 0) {
        printf("ERR kr=invalid_hex\n");
        fflush(stdout);
        free(buf);
        return;
    }

    kern_return_t kr = mach_vm_write(task, addr, (vm_offset_t)buf, (mach_msg_type_number_t)nbytes);
    if (kr != KERN_SUCCESS) {
        printf("ERR kr=%d\n", kr);
    } else {
        printf("OK\n");
    }
    fflush(stdout);
    free(buf);
}

static void cmd_regions(mach_port_t task)
{
    mach_vm_address_t addr = 0;
    while (1) {
        mach_vm_size_t size = 0;
        vm_region_basic_info_data_64_t info;
        mach_msg_type_number_t cnt = VM_REGION_BASIC_INFO_COUNT_64;
        mach_port_t obj = MACH_PORT_NULL;

        kern_return_t kr = mach_vm_region(
            task, &addr, &size,
            VM_REGION_BASIC_INFO_64,
            (vm_region_info_t)&info, &cnt, &obj
        );
        if (kr != KERN_SUCCESS || size == 0)
            break;

        if (info.protection & VM_PROT_READ) {
            printf("REGION %llx %llx\n", (unsigned long long)addr,
                   (unsigned long long)size);
            fflush(stdout);
        }
        addr += size;
    }
    printf("OK\n");
    fflush(stdout);
}

static void cmd_scan(mach_port_t task, const char *addr_str,
                     const char *len_str, const char *mag_str)
{
    uint64_t base = strtoull(addr_str, NULL, 16);
    uint64_t len  = strtoull(len_str, NULL, 16);

    uint8_t magic[4];
    if (hex_decode(mag_str, strlen(mag_str), magic, 4) != 4) {
        printf("ERR kr=bad_magic\n");
        fflush(stdout);
        return;
    }

    const size_t CH = 1u << 20;   /* 1 MiB scan chunk (multiple of 4) */
    uint8_t *buf = malloc(CH);
    if (!buf) {
        printf("ERR kr=oom\n");
        fflush(stdout);
        return;
    }

    const int MAX_HITS = 8192;
    int hits = 0;
    uint64_t off = 0;

    while (off < len) {
        size_t want = (size_t)((len - off < CH) ? (len - off) : CH);
        want &= ~((size_t)3);          /* keep 4-byte aligned */
        if (want == 0)
            break;

        mach_vm_size_t got = 0;
        kern_return_t kr = mach_vm_read_overwrite(
            task, base + off, want, (mach_vm_address_t)buf, &got);

        if (kr != KERN_SUCCESS || got < 4) {
            /* Unmapped/short chunk — skip past it and continue. */
            off += want;
            continue;
        }

        size_t scan = (size_t)got & ~((size_t)3);
        for (size_t i = 0; i + 4 <= scan; i += 4) {
            if (buf[i]   == magic[0] && buf[i+1] == magic[1] &&
                buf[i+2] == magic[2] && buf[i+3] == magic[3]) {
                printf("HIT %llx\n", (unsigned long long)(base + off + i));
                if (++hits >= MAX_HITS) {
                    off = len;
                    break;
                }
            }
        }
        off += scan;
    }

    free(buf);
    printf("OK\n");
    fflush(stdout);
}

/* -------------------------------------------------------------------------
 * main
 * ---------------------------------------------------------------------- */

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: memhelper <pid>\n");
        return 2;
    }

    pid_t pid = (pid_t)atoi(argv[1]);
    mach_port_t task = MACH_PORT_NULL;
    kern_return_t kr = task_for_pid(mach_task_self(), pid, &task);
    if (kr != KERN_SUCCESS) {
        printf("ERR attach kr=%d\n", kr);
        fflush(stdout);
        return 1;
    }
    printf("OK\n");
    fflush(stdout);

    /* Line-buffer stdout so fflush() calls are belt-and-suspenders */
    setvbuf(stdout, NULL, _IOLBF, 0);

    char   *line     = NULL;
    size_t  line_cap = 0;
    ssize_t line_len;

    while ((line_len = getline(&line, &line_cap, stdin)) != -1) {
        /* Trim trailing newline */
        while (line_len > 0 && (line[line_len - 1] == '\n' ||
                                 line[line_len - 1] == '\r'))
            line[--line_len] = '\0';

        if (line_len == 0)
            continue;

        /* Tokenise: command word + up to 2 arguments */
        char *saveptr = NULL;
        char *cmd  = strtok_r(line, " \t", &saveptr);
        char *arg1 = strtok_r(NULL, " \t", &saveptr);
        char *arg2 = saveptr; /* rest of line (may contain no spaces) */

        if (!cmd)
            continue;

        /* Skip leading whitespace in arg2 */
        if (arg2) {
            while (*arg2 == ' ' || *arg2 == '\t') arg2++;
            if (*arg2 == '\0') arg2 = NULL;
        }

        if (strcmp(cmd, "READ") == 0) {
            if (!arg1 || !arg2) {
                printf("ERR kr=bad_args\n");
                fflush(stdout);
            } else {
                /* arg2 here is just the length token (no payload after) */
                char *len_str = strtok_r(arg2, " \t", &saveptr);
                cmd_read(task, arg1, len_str ? len_str : arg2);
            }
        } else if (strcmp(cmd, "WRITE") == 0) {
            if (!arg1 || !arg2) {
                printf("ERR kr=bad_args\n");
                fflush(stdout);
            } else {
                cmd_write(task, arg1, arg2);
            }
        } else if (strcmp(cmd, "REGIONS") == 0) {
            cmd_regions(task);
        } else if (strcmp(cmd, "SCAN") == 0) {
            char *len_str = arg2 ? strtok_r(arg2, " \t", &saveptr) : NULL;
            char *mag_str = len_str ? strtok_r(NULL, " \t", &saveptr) : NULL;
            if (!arg1 || !len_str || !mag_str) {
                printf("ERR kr=bad_args\n");
                fflush(stdout);
            } else {
                cmd_scan(task, arg1, len_str, mag_str);
            }
        } else {
            printf("ERR kr=unknown_cmd\n");
            fflush(stdout);
        }
    }

    free(line);
    return 0;
}
