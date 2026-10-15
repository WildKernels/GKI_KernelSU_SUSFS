/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2022. All rights reserved.
 * Description: LZ4K compression algorithm with delta compression
 */

#if !defined(__KERNEL__)
#include "lz4kd.h"
#else
#include <linux/lz4kd.h>
#include <linux/module.h>
#endif

#include "lz4kd_private.h"
#include "lz4kd_encode_private.h"

enum {
	HT_LOG2 = 12, /* ==11 #3 max drop in CR */
	STEP_LOG2 = 5 /* ==3 #2 avg drop in CR */
};

static unsigned encode_state_bytes_min(void)
{
	enum {
		BYTES_LOG2 = HT_LOG2 + 1
	};
	const unsigned bytes_total = (1U << BYTES_LOG2);
	return bytes_total;
}

#if !defined(LZ4K_DELTA) && !defined(LZ4K_MAX_CR)

unsigned lz4kd_encode_state_bytes_min(void)
{
	return encode_state_bytes_min();
}
EXPORT_SYMBOL(lz4kd_encode_state_bytes_min);

#endif /* !defined(LZ4K_DELTA) && !defined(LZ4K_MAX_CR) */

/* minimum encoded size for non-compressible data */
inline static uint_fast32_t encoded_bytes_min(
	uint_fast32_t nr_log2,
	uint_fast32_t in_max)
{
	return in_max < mask(nr_log2) ?
		TAG_BYTES_MAX + in_max :
		TAG_BYTES_MAX + size_bytes_count(in_max - mask(nr_log2)) + in_max;
}

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

inline static uint8_t *out_size_bytes(uint8_t *out_at, uint_fast32_t u)
{
	for (; u >= BYTE_MAX; *out_at++ = (uint8_t)BYTE_MAX, u -= BYTE_MAX);
	*out_at++ = (uint8_t)u;
	return out_at;
}

inline static uint8_t *out_utag_then_bytes_left(
	uint8_t *out_at,
	uint_fast32_t utag,
	uint_fast32_t bytes_left)
{
	m_copy(out_at, &utag, TAG_BYTES_MAX);
	return out_size_bytes(out_at + TAG_BYTES_MAX, bytes_left);
}

static int out_tail(
	uint8_t *out_at,
	uint8_t *const out_end,
	const uint8_t *const out,
	const uint8_t *const nr0,
	const uint8_t *const in_end,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2)
{
	const uint_fast32_t nr_mask = mask(nr_log2);
	const uint_fast32_t r_log2 = TAG_BITS_MAX - (off_log2 + nr_log2);
	const uint_fast32_t nr_bytes_now = u_32(in_end - nr0);
	if (encoded_bytes_min(nr_log2, nr_bytes_now) > u_32(out_end - out_at))
		return LZ4K_STATUS_INCOMPRESSIBLE;
	if (nr_bytes_now < nr_mask) {
		/* caller guarantees at least one nr-byte */
		uint_fast32_t utag = (nr_bytes_now << (off_log2 + r_log2));
		m_copy(out_at, &utag, TAG_BYTES_MAX);
		out_at += TAG_BYTES_MAX;
	} else { /* nr_bytes_now>=nr_mask */
		uint_fast32_t bytes_left = nr_bytes_now - nr_mask;
		uint_fast32_t utag = (nr_mask << (off_log2 + r_log2));
		out_at = out_utag_then_bytes_left(out_at, utag, bytes_left);
	} /* if (nr_bytes_now<nr_mask) */
	m_copy(out_at, nr0, nr_bytes_now);
	return (int)(out_at + nr_bytes_now - out);
}

inline static int out_tail2(
	uint8_t *out_at,
	uint8_t *const out_end,
	const uint8_t *const out,
	const uint8_t *const r,
	const uint8_t *const in_end,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2)
{
	return r == in_end ? (int)(out_at - out) :
		out_tail(out_at, out_end, out, r, in_end,
			 nr_log2, off_log2);
}

int lz4kd_out_tail(
	uint8_t *out_at,
	uint8_t *const out_end,
	const uint8_t *const out,
	const uint8_t *const nr0,
	const uint8_t *const in_end,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	bool check_out)
{
	return out_tail(out_at, out_end, out, nr0, in_end,
			nr_log2, off_log2);
}

static uint8_t *out_non_repeat(
	uint8_t *out_at,
	uint8_t *const out_end,
	uint_fast32_t utag,
	const uint8_t *const nr0,
	const uint8_t *const r,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2)
{
	const uint_fast32_t nr_bytes_max = u_32(r - nr0);
	const uint_fast32_t nr_mask = mask(nr_log2),
		r_log2 = TAG_BITS_MAX - (off_log2 + nr_log2);
	if (likely(nr_bytes_max < nr_mask)) {
		utag |= (nr_bytes_max << (off_log2 + r_log2));
		m_copy(out_at, &utag, TAG_BYTES_MAX);
		out_at += TAG_BYTES_MAX;
	} else { /* nr_bytes_max >= nr_mask */
		uint_fast32_t bytes_left = nr_bytes_max - nr_mask;
		utag |= (nr_mask << (off_log2 + r_log2));
		out_at = out_utag_then_bytes_left(out_at, utag, bytes_left);
	} /* if (nr_bytes_max<nr_mask) */
	copy_x_while_total(out_at, nr0, nr_bytes_max, NR_COPY_MIN);
	out_at += nr_bytes_max;
	return out_at;
}

inline static uint8_t *out_r_bytes_left(
	uint8_t *out_at,
	uint_fast32_t r_bytes_max,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2)
{
	const uint_fast32_t r_mask = mask(TAG_BITS_MAX - (off_log2 + nr_log2));
	return likely(r_bytes_max - REPEAT_MIN < r_mask) ?
		out_at : out_size_bytes(out_at, r_bytes_max - REPEAT_MIN - r_mask);
}

static uint8_t *out_repeat(
	uint8_t *out_at,
	uint_fast32_t utag,
	uint_fast32_t r_bytes_max,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2)
{
	const uint_fast32_t r_mask = mask(TAG_BITS_MAX - (off_log2 + nr_log2));
	if (likely(r_bytes_max - REPEAT_MIN < r_mask)) {
		utag |= ((r_bytes_max - REPEAT_MIN) << off_log2);
		m_copy(out_at, &utag, TAG_BYTES_MAX);
		out_at += TAG_BYTES_MAX;
	} else {
		uint_fast32_t bytes_left = r_bytes_max - REPEAT_MIN - r_mask;
		utag |= (r_mask << off_log2);
		out_at = out_utag_then_bytes_left(out_at, utag, bytes_left);
	}
	return out_at; /* SUCCESS: continue compression */
}

uint8_t *lz4kd_out_repeat(
	uint8_t *out_at,
	uint8_t *const out_end,
	uint_fast32_t utag,
	uint_fast32_t r_bytes_max,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	const bool check_out)
{
	return out_repeat(out_at, utag, r_bytes_max, nr_log2, off_log2);
}

inline static uint8_t *out_tuple(
	uint8_t *out_at,
	uint8_t *const out_end,
	uint_fast32_t utag,
	const uint8_t *const nr0,
	const uint8_t *const r,
	uint_fast32_t r_bytes_max,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2)
{
	update_utag(r_bytes_max, &utag, nr_log2, off_log2);
	out_at = out_non_repeat(out_at, out_end, utag, nr0, r, nr_log2, off_log2);
	return out_r_bytes_left(out_at, r_bytes_max, nr_log2, off_log2);
}

uint8_t *lz4kd_out_tuple(
	uint8_t *out_at,
	uint8_t *const out_end,
	uint_fast32_t utag,
	const uint8_t *const nr0,
	const uint8_t *const r,
	uint_fast32_t r_bytes_max,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	bool check_out)
{
	return out_tuple(out_at, out_end, utag, nr0, r, r_bytes_max,
				nr_log2, off_log2);
}

static const uint8_t *repeat_end(
	const uint8_t *q,
	const uint8_t *r,
	const uint8_t *const in_end_safe,
	const uint8_t *const in_end)
{
	q += REPEAT_MIN;
	r += REPEAT_MIN;
	/* caller guarantees r+12<=in_end */
	do {
		const uint64_t x = read8_at(q) ^ read8_at(r);
		if (x) {
			const uint16_t ctz = (uint16_t)__builtin_ctzl(x);
			return r + (ctz >> BYTE_BITS_LOG2);
		}
		/* some bytes differ: count of trailing 0-bits/bytes */
		q += sizeof(uint64_t);
		r += sizeof(uint64_t);
	} while (likely(r <= in_end_safe)); /* once, at input block end */
	while (r < in_end) {
		if (*q != *r) return r;
		++q;
		++r;
	}
	return r;
}

const uint8_t *lz4kd_repeat_end(
	const uint8_t *q,
	const uint8_t *r,
	const uint8_t *const in_end_safe,
	const uint8_t *const in_end)
{
	return repeat_end(q, r, in_end_safe, in_end);
}

/* CR increase order: +STEP, have OFFSETS, use _5b(most impact) */
/* *_6b to compete with LZ4 */
inline static uint_fast32_t hash(const uint8_t *r)
{
	return hash64_5b(r, HT_LOG2);
}

/*
 * Proof that 'r' increments are safe-NO pointer overflows are possible:
 *
 * While using STEP_LOG2=5, step_start=1<<STEP_LOG2 == 32 we increment s
 * 32 times by 1, 32 times by 2, 32 times by 3, and so on:
 * 32*1+32*2+32*3+...+32*31 == 32*SUM(1..31) == 32*((1+31)*15+16).
 * So, we can safely increment s by at most 31 for input block size <=
 * 1<<13 < 15872.
 *
 * More precisely, STEP_LIMIT == x for any input block  calculated as follows:
 * 1<<off_log2 >= (1<<STEP_LOG2)*((x+1)(x-1)/2+x/2) ==>
 * 1<<(off_log2-STEP_LOG2+1) >= x^2+x-1 ==>
 * x^2+x-1-1<<(off_log2-STEP_LOG2+1) == 0, which is solved by standard
 * method.
 * To avoid overhead here conservative approximate value of x is calculated
 * as average of two nearest square roots, see STEP_LIMIT above.
 */

static int encode_any(
	uint16_t *const ht,
	const uint8_t *const in0,
	const uint8_t *const in_end,
	uint8_t *const out,
	uint8_t *const out_end)
{
	enum {
		NR_LOG2 = NR_4KB_LOG2,
		OFF_LOG2 = BLOCK_4KB_LOG2
	};
	const uint8_t *const in_end_safe = in_end - NR_COPY_MIN;
	const uint8_t *r = in0;
	const uint8_t *nr0 = r++;
	uint8_t *out_at = out + 1; /* +1 for header */
	for (; ; nr0 = r) {
		const uint8_t *q = 0;
		uint_fast32_t step = 1 << STEP_LOG2;
		uint_fast32_t utag = 0;
		const uint8_t *r_end = 0;
		uint_fast32_t r_bytes_max = 0;
		while (true) {
			if (equal4(q = hashed(in0, ht, hash(r), r), r))
				break;
			++r;
			if (equal4(q = hashed(in0, ht, hash(r), r), r))
				break;
			if (unlikely((r += (++step >> STEP_LOG2)) > in_end_safe))
				return out_tail(out_at, out_end, out, nr0, in_end,
						NR_LOG2, OFF_LOG2);
		}
		utag = u_32(r - q);
		r_end = repeat_end(q, r, in_end_safe, in_end);
		r_bytes_max = u_32(r_end - r);
		if (unlikely(nr0 == r))
			out_at = out_repeat(out_at, utag, r_bytes_max,
					    NR_LOG2, OFF_LOG2);
		else
			out_at = out_tuple(out_at, out_end, utag, nr0, r, r_bytes_max,
					    NR_LOG2, OFF_LOG2);
		if (unlikely((r += r_bytes_max) > in_end_safe))
			return out_tail2(out_at, out_end, out, r, in_end,
					 NR_LOG2, OFF_LOG2);
		ht[hash(r - 1)] = (uint16_t)(r - 1 - in0);
	}
}

/* not static for inlining optimization */
int lz4kd_encode_fast(
	void *const state,
	const uint8_t *const in,
	uint8_t *const out,
	const uint_fast32_t in_max,
	const uint_fast32_t out_max)
{
	return encode_any((uint16_t*)state, in, in + in_max, out, out + out_max);
}

int lz4kd_encode(
	void *const state,
	const void *const in,
	void *out,
	unsigned in_max,
	unsigned out_max,
	unsigned out_limit)
{
	const uint64_t io_min = min_u64(in_max, out_max);
	const uint64_t gain_max = max_u64(GAIN_BYTES_MAX, (io_min >> GAIN_BYTES_LOG2));
	/* ++use volatile pointers to prevent compiler optimizations */
	const uint8_t *volatile in_end = (const uint8_t*)in + in_max;
	const uint8_t *volatile out_end = (uint8_t*)out + out_max;
	const void *volatile state_end =
		(uint8_t*)state + encode_state_bytes_min();
	if (unlikely(state == NULL))
		return LZ4K_STATUS_FAILED;
	if (unlikely(in == NULL || out == NULL))
		return LZ4K_STATUS_FAILED;
	if (unlikely(out_max <= gain_max))
		return LZ4K_STATUS_FAILED;
	if (unlikely((const uint8_t*)in >= in_end || (uint8_t*)out >= out_end))
		return LZ4K_STATUS_FAILED;
	if (unlikely(state >= state_end))
		return LZ4K_STATUS_FAILED; /* pointer overflow */
	if (in_max > (1 << BLOCK_4KB_LOG2))
		return LZ4K_STATUS_FAILED;
	if (unlikely(!out_limit || out_limit > io_min))
		out_limit = (unsigned)io_min;
	m_set(state, 0, encode_state_bytes_min());
	*((uint8_t*)out) = 0; /* lz4kd header */
	if (unlikely(nr_encoded_bytes_max(in_max, NR_4KB_LOG2) > out_max))
		return 0;
	return lz4kd_encode_fast(state, (const uint8_t*)in, (uint8_t*)out,
			in_max, out_limit);
}
EXPORT_SYMBOL(lz4kd_encode);

/* maximum encoded size for repeat and non-repeat data if "fast" encoder is used */
uint_fast32_t lz4kd_encoded_bytes_max(
	uint_fast32_t nr_max,
	uint_fast32_t r_max,
	uint_fast32_t nr_log2,
	uint_fast32_t off_log2)
{
	uint_fast32_t r = 1 + TAG_BYTES_MAX +
		(uint32_t)round_up_to_log2(nr_max, NR_COPY_LOG2);
	uint_fast32_t r_log2 = TAG_BITS_MAX - (off_log2 + nr_log2);
	if (nr_max >= mask(nr_log2))
		r += size_bytes_count(nr_max - mask(nr_log2));
	if (r_max >= mask(r_log2)) {
		r_max -= mask(r_log2);
		r += (uint_fast32_t)max_u64(size_bytes_count(r_max),
					r_max - r_max / REPEAT_MIN); /* worst case: one tag for each REPEAT_MIN */
	}
	return r;
}
EXPORT_SYMBOL(lz4kd_encoded_bytes_max);

const char *lz4kd_version(void)
{
	static const char *version = "2022.03.20";
	return version;
}
EXPORT_SYMBOL(lz4kd_version);

MODULE_LICENSE("Dual BSD/GPL");
MODULE_DESCRIPTION("LZ4K encoder");
