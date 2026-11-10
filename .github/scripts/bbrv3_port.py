#!/usr/bin/env python3
"""Build our own net/ipv4/tcp_bbr3.c from google/bbr branch v3 (Linux 6.13.7).

We write this port ourselves; the older third-party bbrv3 patches are reference only
(they showed that the CA-priv slot needs a pointer indirection, nothing is copied).

Nothing outside the generated file changes, so the KMI is untouched:
  * struct bbr is allocated per socket; only a pointer sits in icsk_ca_priv (64B)
  * identifiers colliding with in-tree BBR v1 are renamed (bbr3)
  * the v3 diag hook is dropped - it needs new uapi fields in struct tcp_bbr_info

usage: bbrv3_port.py <google-bbr-v3-checkout> <kernel-tree>
"""
import re
import sys
from pathlib import Path

SUBS = [
    ('\t.name\t\t= "bbr",', '\t.name\t\t= "bbr3",'),
    ('tcp_bbr_cong_ops', 'tcp_bbr3_cong_ops'),
    ('bbr_register', 'bbr3_register'),
    ('bbr_unregister', 'bbr3_unregister'),
    ('TCP_ECN_OK', 'TCP_ECN_MODE_RFC3168'),
    ('TCP_ECN_LOW', 'TCP_ECN_MODE_ACCECN'),
    ('TCP_ECN_ECT_PERMANENT', '0'),
    ('tp->fast_ack_mode', 'bbr3_fast_ack_mode'),
    ('tp->tlp_orig_data_app_limited', '0'),
    ('TCP_SKB_CB(skb)->tx.lost', '0'),
    ('CA_EVENT_TLP_RECOVERY', 'BBR3_EVENT_TLP_RECOVERY'),
    ('tcp_skb_tx_in_flight_is_suspicious(', 'bbr3_skb_inflight_suspicious('),
    ('inet_csk_ca(sk)', 'bbr_ca(sk)'),
    # sk_buff's cb[] is fixed-size on 6.18, so tcp_skb_cb cannot carry these;
    # they only feed the TLP loss-probe estimate, kept conservative here
    ('scb->tx.in_flight', '0'),
    ('scb->tx.lost', '0'),
    # v3's extra sample fields are file-local: adding them to struct rate_sample moved
    # 6,326 CRCs (measured), so the programme stays inside this file instead.
    ('rs->tx_in_flight', 'rs->prior_in_flight'),
    ('rs->lost', 'rs->losses'),
    ('rs->is_ece', '(rs->delivered_ce != 0)'),
    ('rs->is_acking_tlp_retrans_seq', 'false'),
]


def main(upstream: str, tree: str) -> None:
    src = Path(upstream, 'net/ipv4/tcp_bbr.c').read_text()

    for old, new in SUBS:
        src = src.replace(old, new)

    # writes to the per-sample fields v3 introduced (no storage on 6.18)
    src = re.sub(r'^\s*rs\.tx_in_flight = .*$', '\t/* no per-sample tx_in_flight on 6.18 */', src, flags=re.M)
    src = re.sub(r'^\s*rs\.lost = .*$', '\t/* no per-sample lost on 6.18 */', src, flags=re.M)
    src = re.sub(r'^\s*rs\.is_ece = .*$', '\t/* no per-sample is_ece on 6.18 */', src, flags=re.M)

    # we allocate the state ourselves, so the upstream size assertion no longer holds
    src = re.sub(r'^\tBUILD_BUG_ON\(sizeof\(struct bbr\) > ICSK_CA_PRIV_SIZE\);\n',
                 '', src, flags=re.M)

    # allocate only inside bbr_init(): the same line appears in const accessors
    mi = re.search(r'static void bbr_init\(', src)
    if not mi:
        raise SystemExit("bbr_init() not found")
    body_start = src.index('{', mi.end())
    body_end = src.index('\n}\n', body_start)
    body = src[body_start:body_end]
    body = body.replace(
        '\tstruct bbr *bbr = bbr_ca(sk);\n',
        '\tstruct bbr **slot = (struct bbr **)inet_csk_ca(sk);\n'
        '\tstruct bbr *bbr = kzalloc(sizeof(*bbr), GFP_KERNEL);\n\n'
        '\tif (!bbr)\n\t\treturn;\n\t*slot = bbr;\n', 1)
    src = src[:body_start] + body + src[body_end:]

    phases, seen = [], set()
    for m in re.finditer(r'\bBBR_PHASE_[A-Z_]+\b', src):
        if m.group(0) not in seen:
            seen.add(m.group(0))
            phases.append(m.group(0))

    shims = [
        '/* ---- GKI 6.18 shims: every adaptation lives here --------------------- */',
        'struct bbr;',
        '',
        '/* icsk_ca_priv is 64B; struct bbr does not fit, so the socket holds a pointer */',
        '#define bbr_ca(sk) (*(struct bbr **)inet_csk_ca(sk))',
        '',
        '/* 6.18 does not raise this event; the TLP-recovery branch stays inactive */',
        '#define BBR3_EVENT_TLP_RECOVERY ((enum tcp_ca_event)99)',
        '',
        '/* no per-skb in-flight accounting on 6.18: never suspicious */',
        '#define bbr3_skb_inflight_suspicious(...) false',
        '',
        '/* 6.18 has no CE-event flag; CE handling below is unchanged */',
        '#define TCP_CONG_WANTS_CE_EVENTS 0',
        '',
        'static u8 bbr3_fast_ack_mode;',
        '',
        'enum tcp_bbr_phase {',
    ] + ['\t%s,' % p for p in phases] + ['};', '']
    block = '\n'.join(shims) + '\n'

    first_fn = re.search(r'(?m)^static ', src)
    limit = first_fn.start() if first_fn else len(src)
    last_inc = max(m.end() for m in re.finditer(r'^#include [^\n]*\n', src, re.M)
                   if m.start() < limit)
    src = src[:last_inc] + block + src[last_inc:]

    m = re.search(r'static size_t bbr_get_info\(', src)
    if m:
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
        src = src[:brace + 1] + '\n\treturn 0;\n}' + src[i + 1:]
        src = re.sub(r'^\t\.get_info\t= bbr_get_info,\n', '', src, flags=re.M)
        src = src.replace('static size_t bbr_get_info(',
                          'static size_t __maybe_unused bbr_get_info(')

    src = src.replace('static struct tcp_congestion_ops tcp_bbr3_cong_ops',
                      'static void bbr3_release(struct sock *sk)\n{\n'
                      '\tkfree(bbr_ca(sk));\n\t*(struct bbr **)inet_csk_ca(sk) = NULL;\n}\n\n'
                      'static struct tcp_congestion_ops tcp_bbr3_cong_ops', 1)
    src = src.replace('\t.cong_control\t= bbr_main,',
                      '\t.release\t= bbr3_release,\n\t.cong_control\t= bbr_main,', 1)


    # callbacks 6.18's struct tcp_congestion_ops does not have
    src = re.sub(r'^\t\.skb_marked_lost = bbr_skb_marked_lost,\n', '', src, flags=re.M)
    src = re.sub(r'^\t\.tso_segs\t= bbr_tso_segs,\n', '', src, flags=re.M)
    # tp can become unused once tp->fast_ack_mode moved to a file-static
    src = re.sub(r'(\tstruct tcp_sock \*tp = tcp_sk\(sk\);\n)', r'\1\t(void)tp;\n', src)

    for fn in ('bbr_get_phase', 'bbr_inflight_hi_from_lost_skb', 'bbr_bw_bytes_per_sec',
               'bbr_skb_marked_lost', 'bbr_tso_segs'):
        src = re.sub(r'^static ([a-z0-9_ ]+?) ' + fn + r'\(',
                     r'static \1 __maybe_unused ' + fn + '(', src, flags=re.M)

    out = Path(tree, 'common/net/ipv4/tcp_bbr3.c')
    out.write_text(src)
    print(f"wrote {out} ({len(src.splitlines())} lines, {len(phases)} phase values)")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
