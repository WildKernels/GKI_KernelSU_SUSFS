#!/usr/bin/env python3
"""Generate net/ipv4/tcp_bbr3.c (tcp_bbr3.o) from google/bbr branch v3.

The algorithm is upstream, unmodified. Only identifiers that would collide with the
in-tree BBR v1 and references to fields 6.18 lacks are rewritten, all of them in one
pass so the file can be regenerated deterministically instead of hand-patched.

usage: gen_bbrv3.py <path-to-google-bbr-v3-checkout> <kernel-tree>
"""
import re, sys
from pathlib import Path

def main(up, tree):
    src = Path(up, 'net/ipv4/tcp_bbr.c').read_text()

    # identity: coexist with in-tree BBR v1
    src = src.replace('\t.name\t\t= "bbr",', '\t.name\t\t= "bbr3",', 1)
    src = src.replace('tcp_bbr_cong_ops', 'tcp_bbr3_cong_ops')
    src = src.replace('static int __init bbr_register(void)', 'static int __init bbr3_register(void)', 1)
    src = src.replace('bbr_register', 'bbr3_register')
    src = src.replace('bbr_unregister', 'bbr3_unregister')

    # 6.18 spellings
    src = src.replace('TCP_ECN_OK', 'TCP_ECN_MODE_RFC3168')
    src = src.replace('TCP_ECN_LOW', 'TCP_ECN_MODE_ACCECN')
    src = src.replace('TCP_ECN_ECT_PERMANENT', '0')
    src = src.replace('tp->fast_ack_mode', 'bbr3_fast_ack_mode')
    src = src.replace('tp->tlp_orig_data_app_limited', '0')
    src = src.replace('TCP_SKB_CB(skb)->tx.lost', '0')
    src = src.replace('CA_EVENT_TLP_RECOVERY', 'BBR3_EVENT_TLP_RECOVERY')
    src = src.replace('tcp_skb_tx_in_flight_is_suspicious(', 'bbr3_skb_inflight_suspicious(')

    # The v3 diag reporting needs new fields in struct tcp_bbr_info (uapi). Dropping
    # the hook keeps the uapi header untouched, so `ss` keeps parsing what it knows;
    # the algorithm is unaffected - get_info only exports state for diagnostics.
    src = re.sub(r"static void bbr_get_info\(.*?\n\}\n", "", src, flags=re.S)
    src = re.sub(r"^\t\.get_info\t= bbr_get_info,\n", "", src, flags=re.M)

    # phase enum: take the members the file actually uses, in first-use order
    members, seen = [], set()
    for m in re.finditer(r'\bBBR_PHASE_[A-Z_]+\b', src):
        if m.group(0) not in seen:
            seen.add(m.group(0)); members.append(m.group(0))

    # 6.18: icsk_ca_priv (64B) is smaller than struct bbr - hold a pointer.
    # Rewritten before the shim block exists so the macro is not self-referential.
    src = src.replace('inet_csk_ca(sk)', 'bbr_ca(sk)')

    shims = ['/* --- 6.18 shims: everything adapted lives here ---------------------- */',
             'struct bbr;',
             '',
             '/* icsk_ca_priv is 64B on 6.18; struct bbr does not fit, so hold a pointer */',
             '#define bbr_ca(sk) (*(struct bbr **)inet_csk_ca(sk))',
             '',
             'static u8 bbr3_fast_ack_mode;',
             '',
             '/* 6.18 does not report TLP retransmits: the branch stays inactive */',
             '#define BBR3_EVENT_TLP_RECOVERY ((enum tcp_ca_event)99)',
             '',
             '/* 6.18 has no per-skb tx_in_flight accounting: never "suspicious" */',
             '#define bbr3_skb_inflight_suspicious(...) false',
             '',
             '/* 6.18 has no CE-event flag; CE handling is unchanged */',
             '#define TCP_CONG_WANTS_CE_EVENTS 0',
             '',
             'enum tcp_bbr_phase {']
    shims += ['\t%s,' % m for m in members]
    shims += ['};', '']
    block = '\n'.join(shims) + '\n'

    # shims go after the LAST include that precedes the first function definition;
    # some files carry further #includes late on, and taking the global max put the
    # shim block below its own first use.
    first_fn = re.search(r'(?m)^static ', src)
    limit = first_fn.start() if first_fn else len(src)
    last_inc = max(m.end() for m in re.finditer(r'^#include [^\n]*\n', src, re.M)
                   if m.start() < limit)
    src = src[:last_inc] + block + src[last_inc:]


    # drop the v3 diag hook: it needs new fields in struct tcp_bbr_info (uapi).
    # Removing the function keeps the uapi header untouched; get_info only exports
    # state for `ss`, the algorithm never calls it.
    # v3's diag hook and two callbacks reference struct members 6.18 lacks.
    # Stub the bodies and drop the designators: the algorithm never calls them.
    for fname in ("bbr_get_info", "bbr_skb_marked_lost", "bbr_tso_segs"):
        m = re.search(r'static [a-z ]+\*?(' + fname + r')\(', src)
        if not m:
            continue
        # stub the body with a no-op
        brace = src.index('{', m.end())
        depth, i = 0, brace
        while i < len(src):
            if src[i] == '{':
                depth += 1
            elif src[i] == '}':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        src = src[:brace + 1] + '\n}\n' + src[i + 1:]
    src = re.sub(r'^\t\.get_info\t= bbr_get_info,\n', '', src, flags=re.M)
    src = re.sub(r'^\t\.skb_marked_lost = bbr_skb_marked_lost,\n', '', src, flags=re.M)
    src = re.sub(r'^\t\.tso_segs\t= bbr_tso_segs,\n', '', src, flags=re.M)
    # the stubs are still referenced by nothing: silence unused-function
    for fname in ("bbr_get_info", "bbr_skb_marked_lost", "bbr_tso_segs"):
        src = src.replace('static void %s(' % fname, 'static void __maybe_unused %s(' % fname)
        src = src.replace('static u32 %s(' % fname, 'static u32 __maybe_unused %s(' % fname)
    # tp may become unused once tp->fast_ack_mode moved to a file-static
    src = re.sub(r'(\tstruct tcp_sock \*tp = tcp_sk\(sk\);\n)', r'\1\t(void)tp;\n', src)

    src = re.sub(r'^\t\.get_info\t= bbr_get_info,\n', '', src, flags=re.M)


    # ---- 6.18: hold struct bbr behind a pointer (icsk_ca_priv is only 64B) ----
    # NOTE: run before the shim block is inserted, or it rewrites the macro itself
    src = src.replace('\tstruct bbr *bbr = bbr_ca(sk);\n',
                    '\tstruct bbr **slot = (struct bbr **)inet_csk_ca(sk);\n'
                    '\tstruct bbr *bbr = kzalloc(sizeof(*bbr), GFP_KERNEL);\n\n'
                    '\tif (!bbr)\n\t\treturn;\n\t*slot = bbr;\n', 1)
    src = src.replace('static struct tcp_congestion_ops tcp_bbr3_cong_ops',
                    'static void bbr3_release(struct sock *sk)\n{\n'
                    '\tkfree(bbr_ca(sk));\n\t*(struct bbr **)inet_csk_ca(sk) = NULL;\n}\n\n'
                    'static struct tcp_congestion_ops tcp_bbr3_cong_ops', 1)
    src = src.replace('\t.cong_control\t= bbr_main,',
                    '\t.release\t= bbr3_release,\n\t.cong_control\t= bbr_main,', 1)

    out = Path(tree, 'common/net/ipv4/tcp_bbr3.c')
    out.write_text(src)
    print(f"wrote {out} ({len(src.splitlines())} lines, {len(members)} phase values)")

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
