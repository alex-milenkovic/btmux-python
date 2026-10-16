# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# MT19937 retains its separate terms in notices/MT19937.txt.
# General sources:
#   btech/mech.stat.c
#   mt19937ar.c

"""Source-compatible MT19937, translated from the supplied mt19937ar.c.

   A C-program for MT19937, with initialization improved 2002/1/26.
   Coded by Takuji Nishimura and Makoto Matsumoto.

   Before using, initialize the state by using init_genrand(seed)
   or init_by_array(init_key, key_length).

   Copyright (C) 1997 - 2002, Makoto Matsumoto and Takuji Nishimura,
   All rights reserved.
   Copyright (C) 2005, Mutsuo Saito,
   All rights reserved.

   Redistribution and use in source and binary forms, with or without
   modification, are permitted provided that the following conditions
   are met:

     1. Redistributions of source code must retain the above copyright
        notice, this list of conditions and the following disclaimer.

     2. Redistributions in binary form must reproduce the above copyright
        notice, this list of conditions and the following disclaimer in the
        documentation and/or other materials provided with the distribution.

     3. The names of its contributors may not be used to endorse or promote
        products derived from this software without specific prior written
        permission.

   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
   "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
   LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
   A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
   CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
   EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
   PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
   PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
   LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
   NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
   SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


   Any feedback is very welcome.
   http://www.math.sci.hiroshima-u.ac.jp/~m-mat/MT/emt.html
   email: m-mat @ math.sci.hiroshima-u.ac.jp (remove space)

"""

MASK32 = 0xffffffff


class MT19937:
    """One independent 624-word state, with source initialization and tempering."""

    def __init__(self, seed=None):
        self.state = [0] * 624
        self.index = 625
        self.words_consumed = 0
        self.raw_words = None
        if seed is not None:
            self.seed(seed)

    def seed(self, seed):
        if not isinstance(seed, int):
            raise ValueError('MT seed must be an integer')
        self.state[0] = seed & MASK32
        for i in range(1, 624):
            prior = self.state[i-1]
            self.state[i] = (1812433253 * (prior ^ (prior >> 30)) + i) & MASK32
        self.index = 624
        self.words_consumed = 0
        self.raw_words = None

    def use_words(self, words):
        words = list(words)
        if any(not isinstance(word, int) or not 0 <= word <= MASK32 for word in words):
            raise ValueError('raw MT words must be unsigned32 integers')
        self.raw_words = words
        self.words_consumed = 0

    def init_by_array(self, keys):
        keys = list(keys)
        if not keys or any(not isinstance(key, int) for key in keys):
            raise ValueError('MT array seed requires nonempty integer keys')
        self.seed(19650218)
        i, j = 1, 0
        for _ in range(max(624, len(keys))):
            prior = self.state[i-1]
            self.state[i] = ((self.state[i] ^ ((prior ^ (prior >> 30)) * 1664525)) + keys[j] + j) & MASK32
            i += 1
            j = (j + 1) % len(keys)
            if i >= 624:
                self.state[0] = self.state[623]
                i = 1
        for _ in range(623):
            prior = self.state[i-1]
            self.state[i] = ((self.state[i] ^ ((prior ^ (prior >> 30)) * 1566083941)) - i) & MASK32
            i += 1
            if i >= 624:
                self.state[0] = self.state[623]
                i = 1
        self.state[0] = 0x80000000

    def int32(self):
        if self.raw_words is not None:
            if self.words_consumed >= len(self.raw_words):
                raise ValueError('exhausted raw32 input stream')
            word = self.raw_words[self.words_consumed]
            self.words_consumed += 1
            return word
        if self.index >= 624:
            if self.index == 625:
                self.seed(5489)
            # The second part deliberately reads already-twisted entries.
            for i in range(624):
                y = (self.state[i] & 0x80000000) | (self.state[(i+1) % 624] & 0x7fffffff)
                self.state[i] = self.state[(i+397) % 624] ^ (y >> 1) ^ (0x9908b0df if y & 1 else 0)
            self.index = 0
        y = self.state[self.index]
        self.index += 1
        self.words_consumed += 1
        y ^= y >> 11
        y ^= (y << 7) & 0x9d2c5680
        y ^= (y << 15) & 0xefc60000
        y ^= y >> 18
        return y & MASK32

    def int31(self):
        return self.int32() >> 1

    def real1(self):
        return self.int32() * (1.0 / 4294967295.0)

    def real2(self):
        return self.int32() * (1.0 / 4294967296.0)

    def real3(self):
        return (self.int32() + 0.5) * (1.0 / 4294967296.0)

    def res53(self):
        first, second = self.int32() >> 5, self.int32() >> 6
        return (first * 67108864.0 + second) * (1.0 / 9007199254740992.0)
