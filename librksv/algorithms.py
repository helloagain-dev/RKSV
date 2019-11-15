###########################################################################
# Copyright 2017 ZT Prentner IT GmbH (www.ztp.at)
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
###########################################################################

"""
This module abstracts an algorithm class used for creating and verifying
receipts. The available algorithms are stored in the ALGORITHMS dictionary which
is indexed by the algorithm codes specified in the regulation.
"""
from builtins import int
from builtins import range

from .gettext_helper import _

import base64
import jwt
import jwt.algorithms

from six import binary_type

from . import utils

class AlgorithmI(object):
    """
    The base class for algorithms. It contains functions every algorithm must
    implement. Do not use this directly.
    """

    def id(self):
        """
        The algorithm's code as specified in the regulation.
        :return: Returns the algorithm code as a string.
        """
        raise NotImplementedError("Please implement this yourself.")

    def jwsHeader(self):
        """
        The header to use when signing a receipt with JWS.
        :return: Returns the header as a string.
        """
        raise NotImplementedError("Please implement this yourself.")

    def sigAlgo(self):
        """
        The JWS signature algorithm used.
        :return: Returns the JWS signature algorithm as a string.
        """
        raise NotImplementedError("Please implement this yourself.")

    def chainBytes(self):
        """
        The number of bytes of the hash of the previous receipt used in the
        chaining value.
        :return: Returns the expected number of bytes.
        """
        raise NotImplementedError("Please implement this yourself.")

    def hash(self, data):
        """
        Hashes the given data with the hash algorithm specified for the
        algorithm class.
        :param data: The data to hash as a string.
        :return: The hash value as a byte list.
        """
        raise NotImplementedError("Please implement this yourself.")

    def chain(self, receipt, previousJwsString):
        """
        Creates the chaining value to incorporate into a new receipt according
        to the algorithm class specification.
        :param receipt: The current receipt object into which the chaining value
        has to be incorporated.
        :param previousJwsString: The previous receipt as JWS string or None if
        this is the initial receipt.
        :return: The chaining value to incorporate into the receipt as byte
        list.
        """
        raise NotImplementedError("Please implement this yourself.")

    def sign(self, payload, privKey):
        """
        Signs the given payload with the private key and returns the signature.
        :param payload: The payload to sign as a string.
        :param privKey: The private key as a PEM formatted string.
        :return: The JWS encoded signature string.
        """
        raise NotImplementedError("Please implement this yourself.")

    def verify(self, jwsString, pubKey):
        """
        Verifies the given JWS signature with the public key.
        :param jwsString: The receipt as JWS string.
        :param pubKey: The public key to use in cryptography's own format.
        :return: True if the signature is valid, False otherwise.
        """
        raise NotImplementedError("Please implement this yourself.")

    def verifyKey(self, key):
        """
        Checks if the given key is valid for encrypting/decrypting the
        turnover counter.
        :param key: The key as a byte list.
        :return:  True if the key is valid, False otherwise.
        """
        raise NotImplementedError("Please implement this yourself.")

    def encryptTurnoverCounter(self, receipt, turnoverCounter, key, size):
        """
        Encrypts the given turnover counter for the given receipt with the key.
        :param receipt: The receipt object in which the encrypted turnover
        counter will be used.
        :param turnoverCounter: The turnover counter as an int.
        :param key: The key as a byte list.
        :param size: The number of bytes used to represent the turnover
        counter as an int. Must be between 5 and 16 (inclusive).
        :return: The encrypted turnover counter as a byte list.
        """
        raise NotImplementedError("Please implement this yourself.")

    def decryptTurnoverCounter(self, receipt, encTurnoverCounter, key):
        """
        Decrypts the given turnover counter for the receipt with the key.
        :param receipt: The receipt object in which the encrypted turnover
        counter is located.
        :param encTurnoverCounter: The encrypted turnover counter as a byte
        list.
        :param key: The key as a byte list.
        :return: The turnover counter as an int.
        """
        raise NotImplementedError("Please implement this yourself.")

class R1(AlgorithmI):
    """
    This is the implementation of the \"R1\" algorithm.
    """
    def id(self):
        return "R1"

    def jwsHeader(self):
        return '{"alg":"%s"}' % self.sigAlgo()

    def sigAlgo(self):
        return "ES256"

    def chainBytes(self):
        return 8

    def hash(self, data):
        return utils.sha256(data.encode("utf-8"))

    def chain(self, receipt, previousJwsString):
        chainingValue = None
        if previousJwsString:
            chainingValue = utils.sha256(previousJwsString.encode("utf-8"))
        else:
            chainingValue = utils.sha256(receipt.registerId.encode("utf-8"))
        return chainingValue[0:8]

    def sign(self, payload, privKey):
        algo = jwt.algorithms.get_default_algorithms()['ES256']

        alg = self.jwsHeader().encode("utf-8")
        alg = base64.urlsafe_b64encode(alg).replace(b'=', b'')

        payload = base64.urlsafe_b64encode(payload.encode(
            "utf-8")).replace(b'=', b'')

        key = algo.prepare_key(privKey)
        sig = algo.sign(alg + b'.' + payload, key)

        sig = base64.urlsafe_b64encode(sig).replace(b'=', b'')

        return sig

    def verify(self, jwsString, pubKey):
        payload = None
        try:
            payload = jwt.PyJWS().decode(jwsString, pubKey)
        except jwt.exceptions.DecodeError as e:
            pass

        if payload:
            return True
        return False

    def verifyKey(self, key):
        if not isinstance(key, bytes):
            return False
        if len(key) != 32:
            return False
        return True

    def encryptTurnoverCounter(self, receipt, turnoverCounter, key, size):
        iv = utils.sha256(receipt.registerId.encode("utf-8")
                + receipt.receiptId.encode("utf-8"))[0:16]

        pt = turnoverCounter.to_bytes(size, byteorder='big', signed=True)

        return utils.aes256ctr(iv, key, pt)

    def decryptTurnoverCounter(self, receipt, encTurnoverCounter, key):
        iv = utils.sha256(receipt.registerId.encode("utf-8")
                + receipt.receiptId.encode("utf-8"))[0:16]
        decCtr = utils.aes256ctr(iv, key, encTurnoverCounter)

        return int.from_bytes(decCtr, byteorder='big', signed=True)

ALGORITHMS = { 'R1': R1() }
