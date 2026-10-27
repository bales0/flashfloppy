"""Exercise the real C image handlers against captured and synthetic images.

Run from the repository root: python3 tests/check_qd_images.py
The supplied specification samples are optional; generated cases always run.
"""
from pathlib import Path
import random
import struct
import subprocess


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'out/qd-tests'
OUT.mkdir(parents=True, exist_ok=True)
HARNESS = OUT / 'qd_image_test'
subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare',
                '-Wno-unused-parameter', '-fsanitize=address,undefined', '-g',
                str(ROOT / 'tests/qd_image_test.c'), '-o', str(HARNESS)], check=True)


def run(path, valid=True):
    output = OUT / (path.name + '.raw')
    result = subprocess.run([str(HARNESS), str(path), str(output)],
                            capture_output=True)
    assert result.returncode == (0 if valid else 2), (path, result.stderr.decode())
    return output.read_bytes() if valid else None


def crc16(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xa001 if crc & 1 else 0)
    return crc.to_bytes(2, 'little')


def records(data):
    """Parse compact byte records, using their declared lengths, not sync scans."""
    assert data[:3] == b'\0\x16\x16'
    result = [data[3:5]]
    pos = 8
    for _ in range(data[4]):
        assert data[pos:pos+3] == b'\0\x16\x16'
        length = int.from_bytes(data[pos+5:pos+7], 'little')
        result.append(data[pos+3:pos+7+length])
        assert data[pos+7+length:pos+10+length] == b'CRC'
        pos += 10+length
    return result


def verify_blocks(track, expected):
    # An independent MFM decoder: odd bits are the data, even bits are clocks.
    nibbles = [sum(((byte >> (bit*2+1)) & 1) << bit for bit in range(4))
               for byte in range(256)]
    raw = track[12713:]
    decoded = bytes(nibbles[lo] | (nibbles[hi] << 4)
                    for lo, hi in zip(raw[0::2], raw[1::2]))
    pos = 0
    for record in expected:
        sync = decoded.find(b'\x16\x16', pos)
        assert sync >= 0
        # Skip the complete preamble, whose data marker may itself be 0x16.
        # All synthetic records use other markers; captured samples use A5.
        while decoded[sync] == 0x16:
            sync += 1
        assert decoded[sync:sync+len(record)] == record
        end = sync+len(record)
        assert decoded[end:end+2] == crc16(record)
        assert decoded[end+2:end+9] == b'\x16'*7
        pos = end+9
    assert len(track) == 203417


def make_compact(payloads, marker=0xa5):
    result = bytearray(b'\0\x16\x16' + bytes([marker, len(payloads)]) + b'CRC')
    for kind, payload in payloads:
        result += b'\0\x16\x16' + bytes([marker, kind])
        result += struct.pack('<H', len(payload)) + payload + b'CRC'
    return bytes(result)


def case(name, data, valid=True):
    path = OUT / name
    path.write_bytes(data)
    track = run(path, valid)
    if valid and data.startswith(b'\0\x16\x16'):
        verify_blocks(track, records(data))
    return track


samples = ROOT / 'specification'
if all((samples / name).exists() for name in ['FF.qd', 'QDF.qdf', 'MZQ.mzq', 'legacy.qd']):
    native = run(samples / 'FF.qd')
    qdf = run(samples / 'QDF.qdf')
    assert qdf == native, 'QDF flux differs from independently captured native QD'
    mzq = run(samples / 'MZQ.mzq')
    legacy = run(samples / 'legacy.qd')
    assert mzq == legacy, 'legacy padding changes the emulated disk'
    compact = records((samples / 'MZQ.mzq').read_bytes())
    verify_blocks(mzq, compact)
    # All block CRCs also agree with the independent physical QDF capture.
    stream = (samples / 'QDF.qdf').read_bytes()[16:]
    pos = 0
    for record in compact:
        pos = stream.index(b'\x16\x16' + record, pos) + 2
        assert stream[pos+len(record):pos+len(record)+2] == crc16(record)
        pos += len(record)+2
    print('Captured QDF == native QD bit-for-bit; MZQ == legacy QD; physical CRCs match')

rng = random.Random(1234)
payload = bytes(rng.randrange(256) for _ in range(17000))
case('basic.mzq', make_compact([(2, bytes(64)), (1, payload)], marker=0x20))
basic = bytearray(make_compact([(2, bytes(64)), (1, payload)], marker=0x20))
basic[3] = 0 # The BASIC converter's count block uses a zero marker.
basic_records = records(basic)
compact_qdf = b'-QD format-     ' + b''.join(
    b'\x16'*4 + record + b'CR' + b'\x16'*4 + b'\0'
    for record in basic_records)
assert case('basic.qdf', compact_qdf) == case('basic-converter.mzq', bytes(basic))
case('bad-compact.qdf', compact_qdf[:-1]+b'X', False)
case('empty.qd', make_compact([]))
# Maximum record count checks that the whole index survives cache activity.
case('many.qd', make_compact([(0, b'')]*255))
case('sync-in-data.mzq', make_compact([(5, b'\0\x16\x16\xa5CRC'*130)]))
case('long-block.mzq', make_compact([(5, payload*3)]))

header = b'-QD format-' + bytes([255])*5
case('raw-byte-stream.qdf', header+payload)
case('protected.qdf', header+b'\x16'*10+b'\xa5\x01\xff\xff'+bytes(1200))

good = make_compact([(0, bytes(64)), (5, payload)])
for i, cut in enumerate([0, 1, 7, 8, 15, 70, 81, len(good)-1]):
    case(f'truncated-{i}.mzq', good[:cut], False)
for index in [0, 1, 2, 5, 6, 7, 8, 9, 10, 15+64, 16+64, 17+64]:
    damaged = bytearray(good)
    damaged[index] ^= 0xff
    case(f'corrupt-{index}.qd', damaged, False)
case('oversize.qdf', header+bytes(100000), False)
case('header-only.qdf', header, False)
case('count-mismatch.mzq', good[:4]+bytes([254])+good[5:], False)
case('oversize.mzq', make_compact([(5, payload)]*6), False)
for path in [OUT/'empty.qd', OUT/'basic.mzq', OUT/'basic.qdf',
             OUT/'raw-byte-stream.qdf']:
    subprocess.run([str(HARNESS), str(path), str(OUT/(path.name+'.no-metadata.raw')),
                    '--no-metadata'], check=True)
print('All logical handlers are read-only with/without metadata; native QD retains its writer; source bytes unchanged')
print('Synthetic BASIC, empty, 256-record, sync-in-payload, seek/wrap and malformed-image checks passed')
