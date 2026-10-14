/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2022. All rights reserved.
 * Description: LZ4K compression algorithm with delta compression
 */

#ifndef _LZ4KD_H
#define _LZ4KD_H

/* file lz4kd.h
  This file contains the platform-independent API of LZ-class
  lossless codecs (compressors/decompressors) with complete
  in-place documentation.  The documentation is formatted
  in accordance with DOXYGEN mark-up format.  So, one can
  generate proper documentation, e.g. in HTML format, using DOXYGEN.

  Currently, LZ-class codecs, documented here, implement following
  algorithms for lossless data compression/decompression:
  \li "LZ" proprietary codec competing with LZ4 - lz4kd_encode(),
  lz4kd_encode_delta(), lz4kd_decode(), lz4kd_decode_delta()

  The LZ compressors accept any data as input and compress it
  without loss to a smaller size if possible.
  Compressed data produced by LZ compressor API lz4kd_encode*(),
  can be decompressed only by lz4kd_decode() API documented below.\n
  */

/*
  lz4kd_status defines simple set of status values returned by APIs
 */
typedef enum {
	LZ4K_STATUS_INCOMPRESSIBLE =  0, /* !< Return when data is incompressible */
	LZ4K_STATUS_FAILED         = -1, /* !< Return on general failure */
	LZ4K_STATUS_READ_ERROR =     -2, /* !< Return when data reading failed */
	LZ4K_STATUS_WRITE_ERROR =    -3  /* !< Return when data writing failed */
} lz4kd_status;

/*
  lz4kd_Version() returns static unmutable string with algorithm version
 */
const char *lz4kd_version(void);

/*
  lz4kd_encode_state_bytes_min() returns number of bytes for state parameter,
  supplied to lz4kd_encode(), lz4kd_encode_delta().
  So, state should occupy at least lz4kd_encode_state_bytes_min() for mentioned
  functions to work correctly.
 */
unsigned lz4kd_encode_state_bytes_min(void);

/*
  lz4kd_encode() encodes/compresses one input buffer at *in, places
  result of encoding into one output buffer at *out if encoded data
  size fits specified values of out_max and out_limit.
  It returs size of encoded data in case of success or value<=0 otherwise.
  The result of successful encoding is in proprietary format, that
  is the encoded data can be decoded only by lz4kd_decode().

  \return
    \li positive value\n
      if encoding was successful. The value returned is the size of encoded
      (compressed) data always <=out_max.
    \li non-positive value\n
      if in==0||in_max==0||out==0||out_max==0 or
      if out_max is less than needed for encoded (compressed) data.
    \li 0 value\n
      if encoded data size >= out_limit

  \param[in] state
    !=0, pointer to state buffer used internally by the function.  Size of
    state in bytes should be at least lz4kd_encode_state_bytes_min().  The content
    of state buffer will be changed during encoding.

  \param[in] in
    !=0, pointer to the input buffer to encode (compress).  The content of
    the input buffer does not change during encoding.

  \param[in] out
    !=0, pointer to the output buffer where to place result of encoding
    (compression).
    If encoding is unsuccessful, e.g. out_max or out_limit are less than
    needed for encoded data then content of out buffer may be arbitrary.

  \param[in] in_max
    !=0, size in bytes of the input buffer at *in

  \param[in] out_max
    !=0, size in bytes of the output buffer at *out

  \param[in] out_limit
    encoded data size soft limit in bytes. Due to performance reasons it is
    not guaranteed that
    lz4kd_encode will always detect that resulting encoded data size is
    bigger than out_limit.
    Hovewer, when reaching out_limit is detected, lz4kd_encode() returns
    earlier and spares CPU cycles.  Caller code should recheck result
    returned by lz4kd_encode() (value greater than 0) if it is really
    less or equal than out_limit.
    out_limit is ignored if it is equal to 0.
 */
int lz4kd_encode(
	void *const state,
	const void *const in,
	void *out,
	unsigned in_max,
	unsigned out_max,
	unsigned out_limit);

int lz4kd_encode2(
	void *const state,
	const void *const in,
	void *out,
	unsigned in_max,
	unsigned out_max,
	unsigned out_limit);

int lz4kd_encode_pattern(
	void *const state,
	const void *const in,
	void *out,
	unsigned in_max,
	unsigned out_max,
	unsigned out_limit);

/*
  lz4kd_encode_max_cr() encodes/compresses one input buffer at *in, places
  result of encoding into one output buffer at *out if encoded data
  size fits specified value of out_max.
  It returs size of encoded data in case of success or value<=0 otherwise.
  The result of successful encoding is in proprietary format, that
  is the encoded data can be decoded only by lz4kd_decode().

  \return
    \li positive value\n
      if encoding was successful. The value returned is the size of encoded
      (compressed) data always <=out_max.
    \li non-positive value\n
      if in==0||in_max==0||out==0||out_max==0 or
      if out_max is less than needed for encoded (compressed) data.

  \param[in] state
    !=0, pointer to state buffer used internally by the function.  Size of
    state in bytes should be at least lz4kd_encode_state_bytes_min().  The content
    of state buffer will be changed during encoding.

  \param[in] in
    !=0, pointer to the input buffer to encode (compress).  The content of
    the input buffer does not change during encoding.

  \param[in] out
    !=0, pointer to the output buffer where to place result of encoding
    (compression).
    If encoding is unsuccessful, e.g. out_max is less than
    needed for encoded data then content of out buffer may be arbitrary.

  \param[in] in_max
    !=0, size in bytes of the input buffer at *in

  \param[in] out_max
    !=0, size in bytes of the output buffer at *out

  \param[in] out_limit
    encoded data size soft limit in bytes. Due to performance reasons it is
    not guaranteed that
    lz4kd_encode will always detect that resulting encoded data size is
    bigger than out_limit.
    Hovewer, when reaching out_limit is detected, lz4kd_encode() returns
    earlier and spares CPU cycles.  Caller code should recheck result
    returned by lz4kd_encode() (value greater than 0) if it is really
    less or equal than out_limit.
    out_limit is ignored if it is equal to 0.
 */
int lz4kd_encode_max_cr(
	void *const state,
	const void *const in,
	void *out,
	unsigned in_max,
	unsigned out_max,
	unsigned out_limit);

/*
  lz4kd_encode_delta() encodes (compresses) data from one input buffer
  using one reference buffer as dictionary and places the result of
  compression into one output buffer.
  The result of successful compression is in proprietary format, so
  that compressed data can be decompressed only by lz4kd_decode_delta().
  Reference/dictionary buffer and input buffer should be contiguous in
  memory.

  \return
    \li positive value\n
      if encoding was successful. The value returned is the size of encoded
      (compressed) data.
    \li non-positive value\n
      if state==0||in0==0||in==0||in_max==0||out==0||out_max==0 or
      if out_max is less than needed for encoded (compressed) data.

  \param[in] state
    !=0, pointer to state buffer used internally by the function.  Size of
    state in bytes should be at least lz4kd_encode_state_bytes_min().
    The content of state buffer is zeroed at the beginning of
    lz4kd_encode_delta().
    The content of state will be changed during encoding.

  \param[in] in0
    !=0, pointer to the reference/dictionary input buffer that was used as
    input to preceding call of lz4kd_encode().
    The content of the reference/dictionary input buffer does not change
    during encoding.

  \param[in] in
    !=0, pointer to the input buffer to encode (compress).  The input buffer
    is compressed using content of the reference/dictionary input buffer at
    in0. The content of the input buffer does not change during encoding.
    The two buffers - at *in0 and at *in - should be contiguous in memory.
    That is, the last byte of buffer at *in0 is located exactly before byte
    at *in.

  \param[in] out
    !=0, pointer to the output buffer where to place result of encoding
    (compression). If compression is unsuccessful then content of out
    buffer may be arbitrary.

  \param[in] in_max
    !=0, size in bytes of the input buffer at *in

  \param[in] out_max
    !=0, size in bytes of the output buffer at *out.
 */
int lz4kd_encode_delta(
	void *const state,
	const void *const in0,
	const void *const in,
	void *out,
	unsigned in_max,
	unsigned out_max,
	unsigned out_limit);

/*
  lz4kd_decode() decodes (decompresses) data from one input buffer and places
  the result of decompression into one output buffer.  The encoded data in input
  buffer should be in proprietary format, produced by lz4kd_encode()
  or by lz4kd_encode_delta().

  \return
    \li positive value\n
      if decoding was successful. The value returned is the size of decoded
      (decompressed) data.
    \li non-positive value\n
      if in==0||in_max==0||out==0||out_max==0 or
      if out_max is less than needed for decoded (decompressed) data or
      if input encoded data format is corrupted.

  \param[in] in
    !=0, pointer to the input buffer to decode (decompress).  The content of
    the input buffer does not change during decoding.

  \param[in] out
    !=0, pointer to the output buffer where to place result of decoding
    (decompression). If decompression is unsuccessful then content of out
    buffer may be arbitrary.

  \param[in] in_max
    !=0, size in bytes of the input buffer at in

  \param[in] out_max
    !=0, size in bytes of the output buffer at out
 */
int lz4kd_decode(
	const void *const in,
	void *const out,
	unsigned in_max,
	unsigned out_max);

/*
  lz4kd_decode_delta() decodes (decompresses) data from one input buffer
  and places the result of decompression into one output buffer.  The
  compressed data in input buffer should be in format, produced by
  lz4kd_encode_delta().

  Example sequence of calls for lz4kd_decode and lz4kd_decode_delta:
//dictionary (1st) block
    int result0=lz4kd_decode(in0, out0, in_max0, out_max0);
//delta (2nd) block
    int result1=lz4kd_decode_delta(in, out0, out, in_max, out_max);

  \return
    \li positive value\n
      if decoding was successful. The value returned is the size of decoded
      (decompressed) data.
    \li non-positive value\n
      if in==0||in_max==0||out==0||out_max==0 or
      if out_max is less than needed for decoded (decompressed) data or
      if input data format is corrupted.

  \param[in] in
    !=0, pointer to the input buffer to decode (decompress).  The content of
    the input buffer does not change during decoding.

  \param[in] out0
    !=0, pointer to the dictionary input buffer that was used as in0 input to
    lz4kd_encode_delta().  The content
    of the dictionary input buffer does not change during decoding.

  \param[in] out
    !=0, pointer to the output buffer where to place result of decoding
    (decompression). If decompression is unsuccessful then content of out
    buffer may be arbitrary.
    The two buffers - at *out0 and at *out - should be contiguous in memory.
    That is, the last byte of buffer at *out0 is located exactly before byte
    at *out.

  \param[in] in_max
    !=0, size in bytes of the input buffer at *in

  \param[in] out_max
    !=0, size in bytes of the output buffer at *out
 */
int lz4kd_decode_delta(
	const void *in,
	const void *const out0,
	void *const out,
	unsigned in_max,
	unsigned out_max);


#endif /* _LZ4KD_H */
