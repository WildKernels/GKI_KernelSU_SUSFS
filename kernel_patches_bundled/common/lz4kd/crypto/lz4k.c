/*
 * Copyright (c) Huawei Technologies Co., Ltd. 2012-2020. All rights reserved.
 * Description: LZ4K compression algorithm for ZRAM
 * Author: Arkhipov Denis arkhipov.denis@huawei.com
 * Create: 2020-03-25
 */

#include <linux/init.h>
#include <linux/module.h>
#include <linux/crypto.h>
#include <linux/vmalloc.h>
#include <linux/lz4k.h>
#include <crypto/algapi.h>
#include <crypto/internal/scompress.h>


struct lz4k_ctx {
	void *lz4k_comp_mem;
};

static int lz4k_init(struct crypto_tfm *tfm)
{
	struct lz4k_ctx *ctx = crypto_tfm_ctx(tfm);

	ctx->lz4k_comp_mem = vmalloc(lz4k_encode_state_bytes_min());
	if (!ctx->lz4k_comp_mem)
		return -ENOMEM;

	return 0;
}

static void lz4k_exit(struct crypto_tfm *tfm)
{
	struct lz4k_ctx *ctx = crypto_tfm_ctx(tfm);
	vfree(ctx->lz4k_comp_mem);
}

static int lz4k_compress_crypto(struct crypto_tfm *tfm, const u8 *src, unsigned int slen, u8 *dst, unsigned int *dlen)
{
	struct lz4k_ctx *ctx = crypto_tfm_ctx(tfm);
	int ret;

	ret = lz4k_encode(ctx->lz4k_comp_mem, src, dst, slen, *dlen, 0);

	if (ret < 0) {
		return -EINVAL;
	}

	if (ret)
		*dlen = ret;

	return 0;
}

static int lz4k_decompress_crypto(struct crypto_tfm *tfm, const u8 *src, unsigned int slen, u8 *dst, unsigned int *dlen)
{
	int ret;

	ret = lz4k_decode(src, dst, slen, *dlen);

	if (ret <= 0)
		return -EINVAL;
	*dlen = ret;
	return 0;
}

static struct crypto_alg alg_lz4k = {
	.cra_name		= "lz4k",
	.cra_driver_name	= "lz4k-generic",
	.cra_flags		= CRYPTO_ALG_TYPE_COMPRESS,
	.cra_ctxsize		= sizeof(struct lz4k_ctx),
	.cra_module		= THIS_MODULE,
	.cra_init		= lz4k_init,
	.cra_exit		= lz4k_exit,
	.cra_u			= { .compress = {
	.coa_compress		= lz4k_compress_crypto,
	.coa_decompress		= lz4k_decompress_crypto } }
};

static int __init lz4k_mod_init(void)
{
	return crypto_register_alg(&alg_lz4k);
}

static void __exit lz4k_mod_fini(void)
{
	crypto_unregister_alg(&alg_lz4k);
}

subsys_initcall(lz4k_mod_init);
module_exit(lz4k_mod_fini);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("LZ4K Compression Algorithm");
MODULE_ALIAS_CRYPTO("lz4k");
