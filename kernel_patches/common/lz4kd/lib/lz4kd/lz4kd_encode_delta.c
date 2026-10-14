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
	HT_LOG2 = 13,
	OFF_LOG2 = 13 /* 13 for 8KB */
};

static unsigned ht_bytes_max(void)
{
	return (1 << HT_LOG2) * sizeof(uint16_t);
}

static unsigned encode_state_bytes_min(void)
{
	return ((1 << HT_LOG2) + (1 << OFF_LOG2)) * sizeof(uint16_t);
}

#ifdef LZ4K_DELTA

unsigned lz4kd_encode_state_bytes_min(void)
{
	return encode_state_bytes_min();
}
EXPORT_SYMBOL(lz4kd_encode_state_bytes_min);

#endif /* LZ4K_DELTA */

inline static uint_fast32_t hashv(const uint64_t v, uint32_t shift)
{
	return hash32v(v, shift);
}

inline static uint_fast32_t hash(const uint8_t *r, uint32_t shift)
{
	return hashv(*((const uint64_t*)r), shift);
}

static void fill_ht_offsets_s(
	const uint_fast32_t off0,
	uint16_t *const ht,
	uint16_t *const past_offset,
	uint64_t s)
{
	static const uint_fast32_t off1 = 1;
	static const uint_fast32_t off2 = 2;
	static const uint_fast32_t off3 = 3;
	uint_fast32_t h0 = hashv(s,                       HT_LOG2);
	uint_fast32_t h1 = hashv(s >> (off1 * BYTE_BITS), HT_LOG2);
	uint_fast32_t h2 = hashv(s >> (off2 * BYTE_BITS), HT_LOG2);
	uint_fast32_t h3 = hashv(s >> (off3 * BYTE_BITS), HT_LOG2);
	past_offset[off0 + 0] = ht[h0];
	ht[h0] = (uint16_t)(off0 + 0);
	past_offset[off0 + off1] = ht[h1];
	ht[h1] = (uint16_t)(off0 + off1);
	past_offset[off0 + off2] = ht[h2];
	ht[h2] = (uint16_t)(off0 + off2);
	past_offset[off0 + off3] = ht[h3];
	ht[h3] = (uint16_t)(off0 + off3);
}

static void update_hash_table(
	uint16_t *const ht,
	const uint8_t *const in1,
	const uint8_t *const in_end)
{
	static const uint64_t read_bytes = 8;
	uint64_t a = 0;
	const uint8_t *const in0 = in1 - 1;
	const uint8_t *r = in1;
	uint16_t *const past_offset = ht + (1 << HT_LOG2);
	m_set(ht, 0, ht_bytes_max());
	past_offset[0] = 0; /* stopper in encode_any2() */
	while (likely(r + read_bytes <= in_end)) {
		a = read8_at(r);
		fill_ht_offsets_s((uint16_t)(r - in0), ht, past_offset, a);
		r += REPEAT_MIN;
	}
	for (; likely(r < in_end); ++r) { /* here in_end=start of the ref block */
		uint_fast32_t off0 = (uint16_t)(r - in0);
		uint_fast32_t h = hash(r, HT_LOG2);
		past_offset[off0] = ht[h];
		ht[h] = (uint16_t)(off0);
	}
}

static void hash_repeat_tail(
	uint16_t *const ht,
	uint16_t *const past_offset,
	const uint8_t *const in0,
	const uint8_t *const r)
{
	const uint8_t *s = r - 1 - 1 - 1;
	uint_fast32_t h = hash(s, HT_LOG2);
	past_offset[s - in0] = ht[h];
	ht[h] = (uint16_t)(s - in0);
	++s;
	h = hash(s, HT_LOG2);
	past_offset[s - in0] = ht[h];
	ht[h] = (uint16_t)(s - in0);
	++s;
	h = hash(s, HT_LOG2);
	past_offset[s - in0] = ht[h];
	ht[h] = (uint16_t)(s - in0);
}

enum {
	STEP_LOG2 = 5, /* increase for better CR */
	Q_MAX = 4, /* 2 for "dump" benchmark: increase for better CR */
	MATCH_MAX = 160
};

static int encode_any2(
	uint16_t *const ht,
	const uint8_t *const in1,
	const uint8_t *const in,
	const uint8_t *const in_end,
	uint8_t *const out,
	uint8_t *const out_end, /* ==out_limit for !check_out */
	const uint_fast32_t nr_log2,
	const bool check_out)
{
	uint8_t *out_at = out + 1; /* +1 for header */
	const uint8_t *const in_end_safe = in_end - NR_COPY_MIN;
	const uint8_t *const in0 = in1 - 1;
	const uint8_t *r = in;
	const uint8_t *nr0 = in;
	uint_fast32_t r_bytes_max = 0;
	uint16_t *const past_offset = ht + (1 << HT_LOG2);
	update_hash_table(ht, in1, in1 + (in - in1));
	while (true) {
		uint_fast32_t off0 = 0;
		uint_fast32_t utag = 0;
		const uint8_t *q = 0;
		const uint8_t *r_end = 0;
		const uint8_t *s = r;
		uint_fast32_t step = 1 << STEP_LOG2;
		while (true) {
			uint64_t sv = read8_at(s);
			uint_fast32_t h = hashv(sv, HT_LOG2);
			off0 = past_offset[s - in0] = ht[h];
			ht[h] = (uint16_t)(s - in0);
			for (; off0 && !equal4pv((q = in0 + off0), sv); off0 = past_offset[off0]);
			if (off0 != 0)
				break; /* repeat found */
			if (unlikely((s += (++step >> STEP_LOG2)) > in_end_safe))
				return lz4kd_out_tail(out_at, out_end, out, nr0,
					 in_end, nr_log2, OFF_LOG2, check_out);
		} /* for */
		utag = (uint_fast32_t)(s - q);
		r_end = lz4kd_repeat_end(q, s, in_end_safe, in_end);
		r_bytes_max = (uint_fast32_t)(r_end - (r = repeat_start(q, s, nr0, in1)));
		if (s + r_bytes_max >= in_end) /* see the bottom of while() below */
			goto REPEAT_DONE; /* match_max(q, s, r_bytes_max + 1) below */
		step = Q_MAX - 1;
		while ((off0 = past_offset[off0]) && (q >= in || step > 0)) {
			const uint8_t *r_start = 0;
			--step;
			if (!match_max((q = in0 + off0), s, r_bytes_max + 1))
				continue;
			r_end = lz4kd_repeat_end(q, s, in_end_safe, in_end);
			r_start = repeat_start(q, s, nr0, in1);
			if (r_bytes_max > (uint_fast32_t)(r_end - r_start))
				continue;
			r_bytes_max = (uint_fast32_t)(r_end - r_start);
			r = r_start;
			utag = (uint_fast32_t)(s - q);
			if (s + r_bytes_max >= in_end ||
			    (q < in && r_bytes_max >= MATCH_MAX))
				goto REPEAT_DONE;
		}
REPEAT_DONE:
		out_at = lz4kd_out_tuple(out_at, out_end, utag, nr0, r,
				r_bytes_max, nr_log2, OFF_LOG2, check_out);
		if (unlikely(check_out && out_at == NULL))
			return LZ4K_STATUS_WRITE_ERROR;
		if (unlikely((r += r_bytes_max) > in_end_safe))
			return r == in_end ? (int)(out_at - out) :
				lz4kd_out_tail(out_at, out_end, out, r, in_end,
					nr_log2, OFF_LOG2, check_out);
		hash_repeat_tail(ht, past_offset, in0, r);
		nr0 = r;
	} /* for */
}

static int encode_delta_fast(
	uint16_t *const ht,
	const uint8_t *const in0,
	const uint8_t *const in,
	uint8_t *const out,
	const uint_fast32_t in_max,
	const uint_fast32_t out_max,
	const uint_fast32_t nr_log2)
{
	return encode_any2(ht, in0, in, in + in_max, out, out + out_max,
			 nr_log2, false); /* !check_out */
}

int lz4kd_encode_delta_slow(
	uint16_t *const ht,
	const uint8_t *const in0,
	const uint8_t *const in,
	uint8_t *const out,
	const uint_fast32_t in_max,
	const uint_fast32_t out_max,
	const uint_fast32_t nr_log2)
{
	return encode_any2(ht, in0, in, in + in_max, out, out + out_max,
			 nr_log2, true); /* check_out */
}

inline static uint64_t u64_diff(const void *a, const void *b)
{
	return (uint64_t)((const uint8_t*)a - (const uint8_t*)b);
}

int lz4kd_encode_delta(
	void *const state,
	const void *const in0,
	const void *const in,
	void *out,
	unsigned in_max,
	unsigned out_max,
	unsigned out_limit)
{
	const unsigned io_min = in_max < out_max ? in_max : out_max;
	if (unlikely(state == NULL))
		return LZ4K_STATUS_FAILED;
	if (unlikely(in0 == NULL || in == NULL || out == NULL))
		return LZ4K_STATUS_FAILED;
	if (unlikely(in0 >= in))
		return LZ4K_STATUS_FAILED;
	if (unlikely(u64_diff(in, in0) + in_max > (1U << BLOCK_8KB_LOG2)))
		return LZ4K_STATUS_FAILED;
	if (!out_limit || out_limit > io_min)
		out_limit = io_min;
	*((uint8_t*)out) = 0; /* header */
	return unlikely(nr_encoded_bytes_max(in_max, NR_8KB_LOG2) > out_max) ?
		lz4kd_encode_delta_slow((uint16_t*)state, (const uint8_t*)in0, (const uint8_t*)in,
			(uint8_t*)out, in_max, out_max, NR_8KB_LOG2) :
		encode_delta_fast((uint16_t*)state, (const uint8_t*)in0, (const uint8_t*)in,
			(uint8_t*)out, in_max, out_limit, NR_8KB_LOG2);
}
EXPORT_SYMBOL(lz4kd_encode_delta);

MODULE_LICENSE("Dual BSD/GPL");
MODULE_DESCRIPTION("LZ4K encoder delta");
