"""IL2CPP global-metadata.dat (v39, Unity 6) string-literal helpers.

Layout facts verified on the shipped file (see meta_hdr.py):
  header: uint32 sanity (0xFAB11BAF), uint32 version (39), then 31 x (offset, size, count) uint32 triplets (header = 380 bytes)
  triplet 0 : string-literal OFFSET table   (offset 380,   size 4*(N+1), count N+1)   uint32 offsets into the data blob, last entry = blob size
  triplet 1 : string-literal DATA blob      (offset 88880, size 742704,  count N)     UTF-8, literal i = blob[off[i] : off[i+1]]
  all sections are contiguous, 4-byte aligned; the last section ends at the end of the file.
"""
import os, struct
from lib_su import *

MD_REL = os.path.join("Suzerain_Data", "il2cpp_data", "Metadata", "global-metadata.dat")
MD_GAME = os.path.join(GAME, MD_REL)
SANITY = 0xFAB11BAF
VERSION = 39
N_TRIPLETS = 31


class Meta:
    def __init__(self, b):
        self.b = b
        san, ver = struct.unpack_from("<II", b, 0)
        if san != SANITY or ver != VERSION:
            raise ValueError(f"unexpected metadata header: sanity {san:#x} version {ver}")
        words = struct.unpack_from("<%dI" % (2 + 3 * N_TRIPLETS), b, 0)
        self.trip = [tuple(words[2 + 3 * k: 5 + 3 * k]) for k in range(N_TRIPLETS)]
        self.hdr_size = 4 * (2 + 3 * N_TRIPLETS)
        (o0, s0, c0), (o1, s1, c1) = self.trip[0], self.trip[1]
        assert o0 == self.hdr_size, (o0, self.hdr_size)
        assert o0 + s0 == o1, "literal offset table must be followed directly by the data blob"
        assert s0 == 4 * c0 and c0 == c1 + 1, (s0, c0, c1)
        self.off_tab, self.n_lit = o0, c1
        self.data_off, self.data_size = o1, s1
        self.offs = struct.unpack_from("<%dI" % c0, b, o0)
        assert self.offs[0] == 0 and self.offs[-1] == s1, (self.offs[0], self.offs[-1], s1)
        assert all(a <= b_ for a, b_ in zip(self.offs, self.offs[1:])), "offsets not monotonic"
        self._lits = None

    def raw(self, i):
        return self.b[self.data_off + self.offs[i]: self.data_off + self.offs[i + 1]]

    @property
    def lits(self):
        """all literals as bytes"""
        if self._lits is None:
            self._lits = [self.raw(i) for i in range(self.n_lit)]
        return self._lits

    def text(self, i):
        return self.raw(i).decode("utf-8", "replace")


def load(path=MD_GAME):
    with open(lp(path), "rb") as f:
        return Meta(f.read())
