/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2022. All rights reserved.
 * Description: LZ4K compression algorithm with delta compression
 */

#ifndef _LZ4KD_PRIVATE_H
#define _LZ4KD_PRIVATE_H

#if !defined(__KERNEL__)

/* for userspace only */

#else /* __KERNEL__ */

#include <linux/lz4kd.h>
#define __STDC_WANT_LIB_EXT1__ 1
#include <linux/string.h> /* memcpy() */
#include <linux/types.h> /* uint8_t, int8_t, uint16_t, int16_t,
uint32_t, int32_t, uint64_t, int64_t */
#include <linux/stddef.h>

typedef uint64_t uint_fast32_t;
typedef int64_t int_fast32_t;

#endif /* __KERNEL__ */

#if defined(__GNUC__) && (__GNUC__>=4)
#define LZ4K_WITH_GCC_INTRINSICS
#endif

enum {
	BYTE_BITS = 8UL,
	WORD_BITS = 32U,
	DWORD_BITS = 64UL,
	BYTE_BITS_LOG2 = 3,
	BYTE_MAX = 255U,
	REPEAT_MIN = 4,
	TAG_BYTES_MAX = 3,
	TAG_BITS_MAX  = TAG_BYTES_MAX * 8,
	BLOCK_4KB_LOG2  = 12,
	BLOCK_8KB_LOG2  = 13,
	NR_8KB_LOG2 = 5, /* for encoded_bytes_max */
	NR_4KB_LOG2 = 6,
	PATTERN_BYTES_MAX = 8 /* 1 bytes for header, 8 bytes for pattern */
};

inline static uint32_t mask(uint_fast32_t log2)
{
	return (1U << log2) - 1U;
}

inline static uint64_t mask64(uint_fast32_t log2)
{
	return (1ULL << log2) - 1ULL;
}

#if defined LZ4K_WITH_GCC_INTRINSICS
inline static int most_significant_bit_of(uint64_t u)
{
	return (int)(__builtin_expect((u) == 0, false) ?
		     -1 : (int)((WORD_BITS - 1) ^ (uint32_t)__builtin_clz((unsigned)(u))));
}
#else /* #!defined LZ4K_WITH_GCC_INTRINSICS */
#error undefined most_significant_bit_of(unsigned u)
#endif /* #if defined LZ4K_WITH_GCC_INTRINSICS */

inline static uint64_t max_u64(uint64_t a, uint64_t b)
{
	return a > b ? a : b;
}

inline static uint64_t min_u64(uint64_t a, uint64_t b)
{
	return a < b ? a : b;
}

inline static void m_copy(void *dst, const void *src, size_t total)
{
#if defined(__STDC_LIB_EXT1__)
	(void)memcpy_s(dst, total, src, (total * 2) >> 1); /* *2 >> 1 to avoid bot errors */
#else
	(void)__builtin_memcpy(dst, src, total);
#endif
}

inline static void m_set(void *dst, uint8_t value, size_t total)
{
#if defined(__STDC_LIB_EXT1__)
	(void)memset_s(dst, total, value, (total * 2) >> 1); /* *2 >> 1 to avoid bot errors */
#else
	(void)__builtin_memset(dst, value, total);
#endif
}

inline static uint64_t round_down_to_log2(uint64_t u, uint8_t log2)
{
	return (uint64_t)(u & ~mask64(log2));
}

inline static uint64_t round_up_to_log2(uint64_t u, uint8_t log2)
{
	return (uint64_t)((u + mask64(log2)) & ~mask64(log2));
}

inline static uint64_t round_up_to_power_of2(uint64_t u)
{
	const int_fast32_t msb = most_significant_bit_of(u);
	return round_up_to_log2(u, (uint8_t)msb);
}

inline static void *align_pointer_up_to_log2(const void *p, uint8_t log2)
{
	return (void*)round_up_to_log2((uint64_t)p, log2);
}

inline static uint32_t read3_at(const void *p)
{
	uint32_t result = 0;
	m_copy(&result, p, 1 + 1 + 1);
	return result;
}

inline static uint32_t read4_at(const void *p)
{
	uint32_t result;
	m_copy(&result, p, sizeof(result));
	return result;
}

inline static uint64_t read8_at(const void *p)
{
	uint64_t result;
	m_copy(&result, p, sizeof(result));
	return result;
}

inline static bool equal3(const uint8_t *const q, const uint8_t *const r)
{
	return (read4_at(q) << BYTE_BITS) == (read4_at(r) << BYTE_BITS);
}

inline static bool equal3pv(const uint8_t *const q, const uint64_t rv)
{
	return (read4_at(q) << BYTE_BITS) == ((uint32_t)rv << BYTE_BITS);
}

inline static bool equal4(const uint8_t *const q, const uint8_t *const r)
{
	return read4_at(q) == read4_at(r);
}

inline static bool equal4pv(const uint8_t *const q, const uint64_t rv)
{
	return read4_at(q) == (uint32_t)rv;
}

inline static bool equal8(const uint8_t *const q, const uint8_t *const r)
{
	return read8_at(q) == read8_at(r);
}

inline static uint_fast32_t hash24v(const uint64_t r, uint32_t shift)
{
	const uint32_t hash24_factor = 3266489917U;
	return (((uint32_t)r << BYTE_BITS) * hash24_factor) >> (WORD_BITS - shift);
}

inline static uint_fast32_t hash24(const uint8_t *r, uint32_t shift)
{
	return hash24v(read4_at(r), shift);
}

inline static uint_fast32_t hash32v_2(const uint64_t r, uint32_t shift)
{
	const uint32_t hash32_2_factor = 3266489917U;
	return ((uint32_t)r * hash32_2_factor) >> (WORD_BITS - shift);
}

inline static uint_fast32_t hash32_2(const uint8_t *r, uint32_t shift)
{
	return hash32v_2(read4_at(r), shift);
}

inline static uint_fast32_t hash32v(const uint64_t r, uint32_t shift)
{
	const uint32_t hash32_factor = 2654435761U;
	return ((uint32_t)r * hash32_factor) >> (WORD_BITS - shift);
}

inline static uint_fast32_t hash32(const uint8_t *r, uint32_t shift)
{
	return hash32v(read4_at(r), shift);
}

inline static uint_fast32_t hash64v_5b(const uint64_t r, uint32_t shift)
{
	const uint64_t m = 889523592379ULL;
	const uint64_t up_shift = 24;
	return (uint32_t)(((r << up_shift) * m) >> (DWORD_BITS - shift));
}

inline static uint_fast32_t hash64_5b(const uint8_t *r, uint32_t shift)
{
	return hash64v_5b(read8_at(r), shift);
}

inline static uint_fast32_t hash64v_6b(const uint64_t r, uint32_t shift)
{
	const uint64_t m = 227718039650203ULL;
	const uint64_t up_shift = 16;
	return (uint32_t)(((r << up_shift) * m) >> (DWORD_BITS - shift));
}

inline static uint_fast32_t hash64_6b(const uint8_t *r, uint32_t shift)
{
	return hash64v_6b(read8_at(r), shift);
}

inline static uint_fast32_t hash64v_7b(const uint64_t r, uint32_t shift)
{
	const uint64_t m = 58295818150454627ULL;
	const uint64_t up_shift = 8;
	return (uint32_t)(((r << up_shift) * m) >> (DWORD_BITS - shift));
}

inline static uint_fast32_t hash64_7b(const uint8_t *r, uint32_t shift)
{
	return hash64v_7b(read8_at(r), shift);
}

inline static uint_fast32_t hash64v_8b(const uint64_t r, uint32_t shift)
{
	const uint64_t m = 2870177450012600261ULL;
	return (uint32_t)((r * m) >> (DWORD_BITS - shift));
}

inline static uint_fast32_t hash64_8b(const uint8_t *r, uint32_t shift)
{
	return hash64v_8b(read8_at(r), shift);
}

inline static void while_lt_copy_x(
	uint8_t *dst,
	const uint8_t *src,
	const uint8_t *dst_end,
	const size_t copy_min)
{
	for (; dst < dst_end; dst += copy_min, src += copy_min)
		m_copy(dst, src, copy_min);
}

inline static void copy_x_while_lt(
	uint8_t *dst,
	const uint8_t *src,
	const uint8_t *dst_end,
	const size_t copy_min)
{
	m_copy(dst, src, copy_min);
	while (dst + copy_min < dst_end)
		m_copy(dst += copy_min, src += copy_min, copy_min);
}

inline static void copy_x_while_total(
	uint8_t *dst,
	const uint8_t *src,
	size_t total,
	const size_t copy_min)
{
	m_copy(dst, src, copy_min);
	for (; total > copy_min; total -= copy_min)
		m_copy(dst += copy_min, src += copy_min, copy_min);
}

inline static void copy_2x(
	uint8_t *dst,
	const uint8_t *src,
	const size_t copy_min)
{
	m_copy(dst, src, copy_min);
	m_copy(dst + copy_min, src + copy_min, copy_min);
}

inline static void copy_2x_as_x2_while_lt(
	uint8_t *dst,
	const uint8_t *src,
	const uint8_t *dst_end,
	const size_t copy_min)
{
	copy_2x(dst, src, copy_min);
	while (dst + (copy_min << 1) < dst_end)
		copy_2x(dst += (copy_min << 1), src += (copy_min << 1), copy_min);
}

inline static void while_lt_copy_2x_as_x2(
	uint8_t *dst,
	const uint8_t *src,
	const uint8_t *dst_end,
	const size_t copy_min)
{
	for (; dst < dst_end; dst += (copy_min << 1), src += (copy_min << 1))
		copy_2x(dst, src, copy_min);
}

#endif /* _LZ4KD_PRIVATE_H */
