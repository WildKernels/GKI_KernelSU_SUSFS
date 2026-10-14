/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
 * Description: LZ4K compression algorithm
 * Author: Aleksei Romanovskii aleksei.romanovskii@huawei.com
 * Created: 2020-03-25
 */

#if !defined(__KERNEL__)
#include "lz4k.h"
#else
#include <linux/lz4k.h>
#include <linux/module.h>
#endif

#include "lz4k_private.h"
#include "lz4k_encode_private.h"

static uint8_t *out_size_bytes(uint8_t *out_at, uint_fast32_t u)
{
	for (; unlikely(u >= BYTE_MAX); u -= BYTE_MAX)
		*out_at++ = (uint8_t)BYTE_MAX;
	*out_at++ = (uint8_t)u;
	return out_at;
} /* out_size_bytes */

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
	const uint_fast32_t off_log2,
	bool check_out)
{
	const uint_fast32_t nr_mask = mask(nr_log2);
	const uint_fast32_t r_log2 = TAG_BITS_MAX - (off_log2 + nr_log2);
	const uint_fast32_t nr_bytes_max = u_32(in_end - nr0);
	if (encoded_bytes_min(nr_log2, nr_bytes_max) > u_32(out_end - out_at))
		return check_out ? LZ4K_STATUS_WRITE_ERROR :
				   LZ4K_STATUS_INCOMPRESSIBLE;
	if (nr_bytes_max < nr_mask) {
		/* caller guarantees at least one nr-byte */
		uint_fast32_t utag = (nr_bytes_max << (off_log2 + r_log2));
		m_copy(out_at, &utag, TAG_BYTES_MAX);
		out_at += TAG_BYTES_MAX;
	} else { /* nr_bytes_max>=nr_mask */
		uint_fast32_t bytes_left = nr_bytes_max - nr_mask;
		uint_fast32_t utag = (nr_mask << (off_log2 + r_log2));
		out_at = out_utag_then_bytes_left(out_at, utag, bytes_left);
	} /* if (nr_bytes_max<nr_mask) */
	m_copy(out_at, nr0, nr_bytes_max);
	return (int)(out_at + nr_bytes_max - out);
} /* out_tail */

int lz4k_out_tail(
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
			nr_log2, off_log2, check_out);
}

static uint8_t *out_non_repeat(
	uint8_t *out_at,
	uint8_t *const out_end,
	uint_fast32_t utag,
	const uint8_t *const nr0,
	const uint8_t *const r,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	bool check_out)
{
	const uint_fast32_t nr_bytes_max = u_32(r - nr0);
	const uint_fast32_t nr_mask = mask(nr_log2),
		r_log2 = TAG_BITS_MAX - (off_log2 + nr_log2);
	if (likely(nr_bytes_max < nr_mask)) {
		if (unlikely(check_out &&
		    TAG_BYTES_MAX + nr_bytes_max > u_32(out_end - out_at)))
			return NULL;
		utag |= (nr_bytes_max << (off_log2 + r_log2));
		m_copy(out_at, &utag, TAG_BYTES_MAX);
		out_at += TAG_BYTES_MAX;
	} else { /* nr_bytes_max >= nr_mask */
		uint_fast32_t bytes_left = nr_bytes_max - nr_mask;
		if (unlikely(check_out &&
		    TAG_BYTES_MAX + size_bytes_count(bytes_left) + nr_bytes_max >
		    u_32(out_end - out_at)))
			return NULL;
		utag |= (nr_mask << (off_log2 + r_log2));
		out_at = out_utag_then_bytes_left(out_at, utag, bytes_left);
	} /* if (nr_bytes_max<nr_mask) */
	if (unlikely(check_out))
		m_copy(out_at, nr0, nr_bytes_max);
	else
		copy_x_while_total(out_at, nr0, nr_bytes_max, NR_COPY_MIN);
	out_at += nr_bytes_max;
	return out_at;
} /* out_non_repeat */

uint8_t *lz4k_out_non_repeat(
	uint8_t *out_at,
	uint8_t *const out_end,
	uint_fast32_t utag,
	const uint8_t *const nr0,
	const uint8_t *const r,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	bool check_out)
{
	 return out_non_repeat(out_at, out_end, utag, nr0, r,
				nr_log2, off_log2, check_out);
}

static uint8_t *out_r_bytes_left(
	uint8_t *out_at,
	uint8_t *const out_end,
	uint_fast32_t r_bytes_max,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	const bool check_out) /* =false when
out_max>=encoded_bytes_max(in_max), =true otherwise */
{
	const uint_fast32_t r_mask = mask(TAG_BITS_MAX - (off_log2 + nr_log2));
	if (unlikely(r_bytes_max - REPEAT_MIN >= r_mask)) {
		uint_fast32_t bytes_left = r_bytes_max - REPEAT_MIN - r_mask;
		if (unlikely(check_out &&
		    size_bytes_count(bytes_left) > u_32(out_end - out_at)))
			return NULL;
		out_at = out_size_bytes(out_at, bytes_left);
	}
	return out_at; /* SUCCESS: continue compression */
} /* out_r_bytes_left */

uint8_t *lz4k_out_r_bytes_left(
	uint8_t *out_at,
	uint8_t *const out_end,
	uint_fast32_t r_bytes_max,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	const bool check_out)
{
	return out_r_bytes_left(out_at, out_end, r_bytes_max,
				nr_log2, off_log2, check_out);
}

static uint8_t *out_repeat(
	uint8_t *out_at,
	uint8_t *const out_end,
	uint_fast32_t utag,
	uint_fast32_t r_bytes_max,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	const bool check_out) /* =false when
out_max>=encoded_bytes_max(in_max), =true otherwise */
{
	const uint_fast32_t r_mask = mask(TAG_BITS_MAX - (off_log2 + nr_log2));
	if (likely(r_bytes_max - REPEAT_MIN < r_mask)) {
		if (unlikely(check_out && TAG_BYTES_MAX > u_32(out_end - out_at)))
			return NULL;
		utag |= ((r_bytes_max - REPEAT_MIN) << off_log2);
		m_copy(out_at, &utag, TAG_BYTES_MAX);
		out_at += TAG_BYTES_MAX;
	} else {
		uint_fast32_t bytes_left = r_bytes_max - REPEAT_MIN - r_mask;
		if (unlikely(check_out &&
		    TAG_BYTES_MAX + size_bytes_count(bytes_left) >
		    u_32(out_end - out_at)))
			return NULL;
		utag |= (r_mask << off_log2);
		out_at = out_utag_then_bytes_left(out_at, utag, bytes_left);
	}
	return out_at; /* SUCCESS: continue compression */
} /* out_repeat */

uint8_t *lz4k_out_repeat(
	uint8_t *out_at,
	uint8_t *const out_end,
	uint_fast32_t utag,
	uint_fast32_t r_bytes_max,
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	const bool check_out)
{
	return out_repeat(out_at, out_end, utag, r_bytes_max,
			  nr_log2, off_log2, check_out);
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
		/* some bytes differ:+ count of trailing 0-bits/bytes */
		q += sizeof(uint64_t), r += sizeof(uint64_t);
	} while (likely(r <= in_end_safe)); /* once, at input block end */
	do {
		if (*q != *r) return r;
		++q;
		++r;
	} while (r < in_end);
	return r;
} /* repeat_end */

const uint8_t *lz4k_repeat_end(
	const uint8_t *q,
	const uint8_t *r,
	const uint8_t *const in_end_safe,
	const uint8_t *const in_end)
{
	return repeat_end(q, r, in_end_safe, in_end);
}

enum {
	HT_BYTES_LOG2 = HT_LOG2 + 1
};

inline unsigned encode_state_bytes_min(void)
{
	unsigned bytes_total = (1U << HT_BYTES_LOG2);
	return bytes_total;
} /* encode_state_bytes_min */

#if !defined(LZ4K_DELTA) && !defined(LZ4K_MAX_CR)

unsigned lz4k_encode_state_bytes_min(void)
{
	return encode_state_bytes_min();
} /* lz4k_encode_state_bytes_min */
/*lint -e580*/
EXPORT_SYMBOL(lz4k_encode_state_bytes_min);
/*lint +e580*/

#endif /* !defined(LZ4K_DELTA) && !defined(LZ4K_MAX_CR) */

/* CR increase order: +STEP, have OFFSETS, use _5b */
/* *_6b to compete with LZ4 */
inline static uint_fast32_t hash0_v(const uint64_t r, uint32_t shift)
{
	return hash64v_6b(r, shift);
}

inline static uint_fast32_t hash0(const uint8_t *r, uint32_t shift)
{
	return hash64_6b(r, shift);
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

enum {
	STEP_LOG2 = 5 /* increase for better CR */
};

static int encode_any(
	uint16_t *const ht0,
	const uint8_t *const in0,
	uint8_t *const out,
	const uint8_t *const in_end,
	uint8_t *const out_end, /* ==out_limit for !check_out */
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2,
	const bool check_out)
{   /* caller guarantees off_log2 <=16 */
	uint8_t *out_at = out;
	const uint8_t *const in_end_safe = in_end - NR_COPY_MIN;
	const uint8_t *r = in0;
	const uint8_t *nr0 = r++;
	uint_fast32_t step = 1 << STEP_LOG2;
	for (;;) {
		uint_fast32_t utag = 0;
		const uint8_t *r_end = 0;
		uint_fast32_t r_bytes_max = 0;
		const uint8_t *const q = hashed(in0, ht0, hash0(r, HT_LOG2), r);
		if (!equal4(q, r)) {
			r += (++step >> STEP_LOG2);
			if (unlikely(r > in_end_safe))
				return out_tail(out_at, out_end, out, nr0, in_end,
						nr_log2, off_log2, check_out);
			continue;
		}
		utag = u_32(r - q);
		r_end = repeat_end(q, r, in_end_safe, in_end);
		r = repeat_start(q, r, nr0, in0);
		r_bytes_max = u_32(r_end - r);
		if (nr0 == r) {
			out_at = out_repeat(out_at, out_end, utag, r_bytes_max,
					    nr_log2, off_log2, check_out);
		} else {
			update_utag(r_bytes_max, &utag, nr_log2, off_log2);
			out_at = out_non_repeat(out_at, out_end, utag, nr0, r,
						nr_log2, off_log2, check_out);
			if (unlikely(check_out && out_at == NULL))
				return LZ4K_STATUS_WRITE_ERROR;
			out_at = out_r_bytes_left(out_at, out_end, r_bytes_max,
						  nr_log2, off_log2, check_out);
		}
		if (unlikely(check_out && out_at == NULL))
			return LZ4K_STATUS_WRITE_ERROR;
		nr0 = (r += r_bytes_max);
		if (unlikely(r > in_end_safe))
			return r == in_end ? (int)(out_at - out) :
				out_tail(out_at, out_end, out, r, in_end,
					 nr_log2, off_log2, check_out);
		ht0[hash0(r - 1 - 1, HT_LOG2)] = (uint16_t)(r - 1 - 1 - in0);
		step = 1 << STEP_LOG2;
	} /* for */
} /* encode_any */

static int encode_fast(
	uint16_t *const ht,
	const uint8_t *const in,
	uint8_t *const out,
	const uint8_t *const in_end,
	uint8_t *const out_end, /* ==out_limit for !check_out */
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2)
{ /* caller guarantees off_log2 <=16 */
	return encode_any(ht, in, out, in_end, out_end, nr_log2, off_log2,
		false); /* !check_out */
} /* encode_fast */

static int encode_slow(
	uint16_t *const ht,
	const uint8_t *const in,
	uint8_t *const out,
	const uint8_t *const in_end,
	uint8_t *const out_end, /* ==out_limit for !check_out */
	const uint_fast32_t nr_log2,
	const uint_fast32_t off_log2)
{ /* caller guarantees off_log2 <=16 */
	return encode_any(ht, in, out, in_end, out_end, nr_log2, off_log2,
		true); /* check_out */
} /* encode_slow */

static int encode4kb(
	uint16_t *const state,
	const uint8_t *const in,
	uint8_t *out,
	const uint_fast32_t in_max,
	const uint_fast32_t out_max,
	const uint_fast32_t out_limit)
{
	enum {
		NR_LOG2 = 6
	};
	const int result = (encoded_bytes_max(NR_LOG2, in_max) > out_max) ?
		encode_slow(state, in, out, in + in_max, out + out_max,
			NR_LOG2, BLOCK_4KB_LOG2) :
		encode_fast(state, in, out, in + in_max, out + out_limit,
			NR_LOG2, BLOCK_4KB_LOG2);
	return result <= 0 ? result : result + 1; /* +1 for in_log2 */
}

static int encode8kb(
	uint16_t *const state,
	const uint8_t *const in,
	uint8_t *out,
	const uint_fast32_t in_max,
	const uint_fast32_t out_max,
	const uint_fast32_t out_limit)
{
	enum {
		NR_LOG2 = 5
	};
	const int result = (encoded_bytes_max(NR_LOG2, in_max) > out_max) ?
		encode_slow(state, in, out, in + in_max, out + out_max,
			NR_LOG2, BLOCK_8KB_LOG2) :
		encode_fast(state, in, out, in + in_max, out + out_limit,
			NR_LOG2, BLOCK_8KB_LOG2);
	return result <= 0 ? result : result + 1; /* +1 for in_log2 */
}

static int encode16kb(
	uint16_t *const state,
	const uint8_t *const in,
	uint8_t *out,
	const uint_fast32_t in_max,
	const uint_fast32_t out_max,
	const uint_fast32_t out_limit)
{
	enum {
		NR_LOG2 = 5
	};
	const int result = (encoded_bytes_max(NR_LOG2, in_max) > out_max) ?
		encode_slow(state, in, out, in + in_max, out + out_max,
			NR_LOG2, BLOCK_16KB_LOG2) :
		encode_fast(state, in, out, in + in_max, out + out_limit,
			NR_LOG2, BLOCK_16KB_LOG2);
	return result <= 0 ? result : result + 1; /* +1 for in_log2 */
}

static int encode32kb(
	uint16_t *const state,
	const uint8_t *const in,
	uint8_t *out,
	const uint_fast32_t in_max,
	const uint_fast32_t out_max,
	const uint_fast32_t out_limit)
{
	enum {
		NR_LOG2 = 4
	};
	const int result = (encoded_bytes_max(NR_LOG2, in_max) > out_max) ?
		encode_slow(state, in, out, in + in_max, out + out_max,
			NR_LOG2, BLOCK_32KB_LOG2) :
		encode_fast(state, in, out, in + in_max, out + out_limit,
			NR_LOG2, BLOCK_32KB_LOG2);
	return result <= 0 ? result : result + 1; /* +1 for in_log2 */
}

static int encode64kb(
	uint16_t *const state,
	const uint8_t *const in,
	uint8_t *out,
	const uint_fast32_t in_max,
	const uint_fast32_t out_max,
	const uint_fast32_t out_limit)
{
	enum {
		NR_LOG2 = 4
	};
	const int result = (encoded_bytes_max(NR_LOG2, in_max) > out_max) ?
		encode_slow(state, in, out, in + in_max, out + out_max,
			NR_LOG2, BLOCK_64KB_LOG2) :
		encode_fast(state, in, out, in + in_max, out + out_limit,
			NR_LOG2, BLOCK_64KB_LOG2);
	return result <= 0 ? result : result + 1; /* +1 for in_log2 */
}

static int encode(
	uint16_t *const state,
	const uint8_t *const in,
	uint8_t *out,
	uint_fast32_t in_max,
	uint_fast32_t out_max,
	uint_fast32_t out_limit)
{
	const uint8_t in_log2 = (uint8_t)(most_significant_bit_of(
		round_up_to_power_of2(in_max - REPEAT_MIN)));
	m_set(state, 0, encode_state_bytes_min());
	*out = in_log2 > BLOCK_4KB_LOG2 ? (uint8_t)(in_log2 - BLOCK_4KB_LOG2) : 0;
	++out;
	--out_max;
	--out_limit;
	if (in_log2 < BLOCK_8KB_LOG2)
		return encode4kb(state, in, out, in_max, out_max, out_limit);
	if (in_log2 == BLOCK_8KB_LOG2)
		return encode8kb(state, in, out, in_max, out_max, out_limit);
	if (in_log2 == BLOCK_16KB_LOG2)
		return encode16kb(state, in, out, in_max, out_max, out_limit);
	if (in_log2 == BLOCK_32KB_LOG2)
		return encode32kb(state, in, out, in_max, out_max, out_limit);
	if (in_log2 == BLOCK_64KB_LOG2)
		return encode64kb(state, in, out, in_max, out_max, out_limit);
	return LZ4K_STATUS_FAILED;
}

int lz4k_encode(
	void *const state,
	const void *const in,
	void *out,
	unsigned in_max,
	unsigned out_max,
	unsigned out_limit)
{
	const unsigned gain_max = 64 > (in_max >> 6) ? 64 : (in_max >> 6);
	const unsigned out_limit_min = in_max < out_max ? in_max : out_max;
	const uint8_t *volatile in_end = (const uint8_t*)in + in_max;
	const uint8_t *volatile out_end = (uint8_t*)out + out_max;
	const void *volatile state_end =
		(uint8_t*)state + encode_state_bytes_min();
	if (unlikely(state == NULL))
		return LZ4K_STATUS_FAILED;
	if (unlikely(in == NULL || out == NULL))
		return LZ4K_STATUS_FAILED;
	if (unlikely(in_max <= gain_max))
		return LZ4K_STATUS_INCOMPRESSIBLE;
	if (unlikely(out_max <= gain_max)) /* need 1 byte for in_log2 */
		return LZ4K_STATUS_FAILED;
	/* ++use volatile pointers to prevent compiler optimizations */
	if (unlikely((const uint8_t*)in >= in_end || (uint8_t*)out >= out_end))
		return LZ4K_STATUS_FAILED;
	if (unlikely(state >= state_end))
		return LZ4K_STATUS_FAILED; /* pointer overflow */
	if (!out_limit || out_limit >= out_limit_min)
		out_limit = out_limit_min - gain_max;
	return encode((uint16_t*)state, (const uint8_t*)in, (uint8_t*)out,
		      in_max, out_max, out_limit);
} /* lz4k_encode */
/*lint -e580*/
EXPORT_SYMBOL(lz4k_encode);
/*lint +e580*/

const char *lz4k_version(void)
{
	static const char *version = "2020.07.07";
	return version;
}
/*lint -e580*/
EXPORT_SYMBOL(lz4k_version);
/*lint +e580*/

MODULE_LICENSE("Dual BSD/GPL");
MODULE_DESCRIPTION("LZ4K encoder");
