/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2022. All rights reserved.
 * Description: LZ4K compression algorithm with delta compression
 */

#ifndef _LZ4KD_ENCODE_PRIVATE_H
#define _LZ4KD_ENCODE_PRIVATE_H

#include "lz4kd_private.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
	GAIN_BYTES_LOG2 = 6,
	GAIN_BYTES_MAX = 1 << GAIN_BYTES_LOG2,
	NR_COPY_LOG2 = 4,
	NR_COPY_MIN = 1 << NR_COPY_LOG2
};

inline static uint32_t u_32(int64_t i)
{
	return (uint32_t)i;
}

/*
 * Compressed data format (where {} means 0 or more occurrences, [] means
 * optional)
 * <24bits tag: (off_log2 rOffset| r_log2 rSize|nr_log2 nrSize)>
 * {<nrSize byte>}[<nr bytes>]{<rSize byte>}
 * <rSize byte> and <nrSize byte> sequences are terminated by byte != 255
 *
 * <nrSize bytes for whole block>+<1 terminating 0 byte>
 */
inline static uint_fast32_t size_bytes_count(uint_fast32_t u)
{
	return ((u + BYTE_MAX) >> BYTE_BITS) + 1; /* (u + BYTE_MAX - 1) / BYTE_MAX; */
}

/* maximum encoded size for non-compressible data if "fast" encoder is used */
inline static uint_fast32_t nr_encoded_bytes_max(
	uint_fast32_t nr_max,
	uint_fast32_t nr_log2)
{
	uint_fast32_t r = 1 + TAG_BYTES_MAX + (uint32_t)round_up_to_log2(nr_max, NR_COPY_LOG2);
	return nr_max < mask(nr_log2) ? r : r + size_bytes_count(nr_max - mask(nr_log2));
}

/* maximum encoded size for repeat and non-repeat data if "fast" encoder is used */
uint_fast32_t lz4kd_encoded_bytes_max(
	uint_fast32_t nr_max,
	uint_fast32_t r_max,
	uint_fast32_t nr_log2,
	uint_fast32_t off_log2);

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
}

static inline bool match_max(
		const uint8_t *q,
		const uint8_t *s,
		const uint_fast32_t r_max)
{
	return equal4(q + r_max - REPEAT_MIN, s + r_max - REPEAT_MIN) &&
		equal4(q, s);
}

int lz4kd_out_tail(
	uint8_t *out_at,
	uint8_t *const out_end,
	const uint8_t *const out,
	const uint8_t *const nr0,
	const uint8_t *const in_end,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	bool check_out);

uint8_t *lz4kd_out_tuple(
	uint8_t *out_at,
	uint8_t *const out_end,
	uint_fast32_t utag,
	const uint8_t *const nr0,
	const uint8_t *const r,
	uint_fast32_t r_bytes_max,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	bool check_out);

uint8_t *lz4kd_out_repeat(
	uint8_t *out_at,
	uint8_t *const out_end,
	uint_fast32_t utag,
	uint_fast32_t r_bytes_max,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	const bool check_out);

const uint8_t *lz4kd_repeat_end(
	const uint8_t *q,
	const uint8_t *r,
	const uint8_t *const in_end_safe,
	const uint8_t *const in_end);

int lz4kd_encode_fast(
	void *const state,
	const uint8_t *const in,
	uint8_t *const out,
	const uint_fast32_t in_max,
	const uint_fast32_t out_max);

#ifdef __cplusplus
}
#endif

#endif /* _LZ4KD_ENCODE_PRIVATE_H */

