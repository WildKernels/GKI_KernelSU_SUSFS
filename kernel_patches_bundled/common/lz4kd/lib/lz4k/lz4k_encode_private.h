/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
 * Description: LZ4K compression algorithm
 * Author: Aleksei Romanovskii aleksei.romanovskii@huawei.com
 * Created: 2020-03-25
 */

#ifndef _LZ4K_ENCODE_PRIVATE_H
#define _LZ4K_ENCODE_PRIVATE_H

#include "lz4k_private.h"

/* <nrSize bytes for whole block>+<1 terminating 0 byte> */
inline static uint_fast32_t size_bytes_count(uint_fast32_t u)
{
	return (u + BYTE_MAX - 1) / BYTE_MAX;
}

/* minimum encoded size for non-compressible data */
inline static uint_fast32_t encoded_bytes_min(
	uint_fast32_t nr_log2,
	uint_fast32_t in_max)
{
	return in_max < mask(nr_log2) ?
		TAG_BYTES_MAX + in_max :
		TAG_BYTES_MAX + size_bytes_count(in_max - mask(nr_log2)) + in_max;
}

enum {
	NR_COPY_LOG2 = 4,
	NR_COPY_MIN = 1 << NR_COPY_LOG2
};

inline static uint_fast32_t u_32(int64_t i)
{
	return (uint_fast32_t)i;
}

/* maximum encoded size for non-comprressible data if "fast" encoder is used */
inline static uint_fast32_t encoded_bytes_max(
	uint_fast32_t nr_log2,
	uint_fast32_t in_max)
{
	uint_fast32_t r = TAG_BYTES_MAX + (uint32_t)round_up_to_log2(in_max, NR_COPY_LOG2);
	return in_max < mask(nr_log2) ? r : r + size_bytes_count(in_max - mask(nr_log2));
}

enum {
	HT_LOG2 = 12
};

/*
 * Compressed data format (where {} means 0 or more occurrences, [] means
 * optional):
 * <24bits tag: (off_log2 rOffset| r_log2 rSize|nr_log2 nrSize)>
 * {<nrSize byte>}[<nr bytes>]{<rSize byte>}
 * <rSize byte> and <nrSize byte> bytes are terminated by byte != 255
 *
 */

inline static void  update_utag(
	uint_fast32_t r_bytes_max,
	uint_fast32_t *utag,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2)
{
	const uint_fast32_t r_mask = mask(TAG_BITS_MAX - (off_log2 + nr_log2));
	*utag |= likely(r_bytes_max - REPEAT_MIN < r_mask) ?
		 ((r_bytes_max - REPEAT_MIN) << off_log2) : (r_mask << off_log2);
}

inline static const uint8_t *hashed(
	const uint8_t *const in0,
	uint16_t *const ht,
	uint_fast32_t h,
	const uint8_t *r)
{
	const uint8_t *q = in0 + ht[h];
	ht[h] = (uint16_t)(r - in0);
	return q;
}

inline static const uint8_t *repeat_start(
	const uint8_t *q,
	const uint8_t *r,
	const uint8_t *const nr0,
	const uint8_t *const in0)
{
	for (; r > nr0 && likely(q > in0) && unlikely(q[-1] == r[-1]); --q, --r);
	return r;
} /* repeat_start */

int lz4k_out_tail(
	uint8_t *out_at,
	uint8_t *const out_end,
	const uint8_t *const out,
	const uint8_t *const nr0,
	const uint8_t *const in_end,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	bool check_out);

uint8_t *lz4k_out_non_repeat(
	uint8_t *out_at,
	uint8_t *const out_end,
	uint_fast32_t utag,
	const uint8_t *const nr0,
	const uint8_t *const r,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	bool check_out);

uint8_t *lz4k_out_r_bytes_left(
	uint8_t *out_at,
	uint8_t *const out_end,
	uint_fast32_t r_bytes_max,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	const bool check_out);

uint8_t *lz4k_out_repeat(
	uint8_t *out_at,
	uint8_t *const out_end,
	uint_fast32_t utag,
	uint_fast32_t r_bytes_max,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	const bool check_out);

const uint8_t *lz4k_repeat_end(
	const uint8_t *q,
	const uint8_t *r,
	const uint8_t *const in_end_safe,
	const uint8_t *const in_end);

#endif /* _LZ4K_ENCODE_PRIVATE_H */

