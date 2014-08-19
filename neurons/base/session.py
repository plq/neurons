# encoding: utf8
#
# This file is part of the Neurons project.
# Copyright (c), Arskom Ltd. (arskom.com.tr),
#                Burak Arslan <burak.arslan@arskom.com.tr>.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the Arskom Ltd. nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#


import os
import hmac
import hashlib
import uuid

import msgpack
import neurons

from time import time
from Crypto.Cipher import AES

from neurons.base.error import TamperedCookieError, SessionExpiredError
from spyne.error import ValidationError
from spyne.util.six import PY3

SESSION_LIFETIME = 15 * 60


def pad(data, length):
    """
    PKCS #7-style padding with the given block length
    """
    assert length < 256
    assert length > 0
    padlen = length - len(data) % length
    assert padlen <= length
    assert padlen > 0
    return data + padlen * chr(padlen)


def unpad(data, length):
    """
    PKCS #7-style unpadding with the given block length
    """
    assert length < 256
    assert length > 0
    padlen = ord(data[-1])
    assert padlen <= length
    assert padlen > 0
    assert data[-padlen:] == padlen * chr(padlen)
    return data[:-padlen]


def encode(data, secret, salt=None):
    """Encode and return the data as a random-IV-prefixed AES-encrypted
    HMAC-SHA1-authenticated padded message corresponding to the given
    data string and secret, which should be at least 36 randomly
    chosen bytes agreed upon by the encoding and decoding parties.
    """

    assert len(secret) >= 36
    if salt is None:
        salt = os.urandom(16)

    aes = AES.new(secret[:16], AES.MODE_CBC, salt)
    padded_data = pad(20 * '\0' + data, 16)[20:]
    mac = hmac.new(key=secret[16:], msg=padded_data, digestmod=hashlib.sha1).digest()
    encrypted = aes.encrypt(mac + padded_data)

    return salt + encrypted


def decode(data, secret):
    """Decode and return the data from random-IV-prefixed AES-encrypted
    HMAC-SHA1-authenticated padded message corresponding to the given
    data string and secret, which should be at least 36 randomly
    chosen bytes agreed upon by the encoding and decoding parties.
    """

    assert len(secret) >= 36

    if len(data) < 16:
        raise ValidationError(data, "Invalid session value. Please sign out "
                            "and delete cookies and try again.\nData: '%s'")
    salt = data[:16]

    encrypted = data[16:]
    aes = AES.new(secret[:16], AES.MODE_CBC, salt)
    decrypted = aes.decrypt(encrypted)

    mac = decrypted[:20]
    padded_data = decrypted[20:]
    mac2 = hmac.new(key=secret[16:], msg=padded_data, digestmod=hashlib.sha1).digest()

    if mac != mac2:
        raise TamperedCookieError()

    return unpad(20 * '\0' + padded_data, 16)[20:]


class SessionObject(object):
    def __init__(self, shash, user, domain, ttl):
        """
        :param shash: Session hash: Unique session identifier.
        :param user: Kullanıcı adı.
        :param domain: Alan adı.
        :param ttl: Time-to-live -- eldeki session stringinin geçerlilik
               süresi.
        """

        object.__init__(self)
        self.shash = shash
        self.user = user
        self.domain = domain
        self.ttl = ttl


def get_du_from_sid(sid):
    """Session-ID stringini decrypt ederek içindeki domain_name / user_name
    bilgisini döndürür."""

    session = get_session_data(sid)
    return session.domain, session.user


def get_data(data, cls):
    dec = decode(''.join(data), neurons.secret)
    dec_data = msgpack.loads(dec)
    dec_data = cls(*dec_data)

    if dec_data.ttl <= time():
        raise SessionExpiredError()
    else:
        return dec_data


def get_session_data(sid):
    return get_data(sid, SessionObject)


def hashpass(password):
    salt = os.urandom(32)
    s = hashlib.sha1()
    s.update(password)
    s.update(salt)
    hash = s.digest() + salt
    phash = '{SSHA}' + hash

    return phash


def replenish_sid(sid):
    s = get_session_data(sid)

    return replenish_session(s.domain, s.user, s.shash)[0]


def replenish_sid_ttl(sid):
    s = get_session_data(sid)

    return replenish_session(s.domain, s.user, s.shash)


def put_data(seconds, *args):
    ttl = time() + seconds
    data = msgpack.dumps( args + (ttl,) )
    enc = encode(data, neurons.secret)

    return enc, ttl


def replenish_session(domain, user, session_id):
    return put_data(SESSION_LIFETIME, session_id, user, domain)


def gen_session_hash(user):
    salt = os.urandom(16)
    if PY3:
        key = b''.join([uuid.getnode().to_bytes(), user, time().to_bytes()])
    else:
        key = b''.join([str(uuid.getnode()), user, str(time())])

    s = hashlib.sha1()
    s.update(key)
    s.update(salt)

    return s.digest()


def verify_hash(clear_password, password_hash):
    if password_hash.startswith("{SSHA}"):
        digest = password_hash[6:26]
        salt = password_hash[26:]

        hr = hashlib.sha1(clear_password.encode('utf8'))
        hr.update(salt)

        return digest == hr.digest()

    raise NotImplementedError(password_hash[:password_hash.find('}')+1])
