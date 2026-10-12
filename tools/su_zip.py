"""usage: python su_zip.py PACK_DIR [PACK_DIR ...]  -> writes PACK_DIR.zip next to each folder (deflate, folder name kept as the top-level entry)"""
import sys, os
import su_pack

for d in sys.argv[1:]:
    zp = su_pack.zip_pack(os.path.abspath(d))
    print(zp, os.path.getsize(zp))
