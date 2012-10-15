#!/usr/bin/env python

"""Provide crypto functionality"""

import os
import ark
import yaml
import logging

from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Cipher import AES
from Crypto import Random
from yaml import dump
from collections import OrderedDict
from functools import wraps


class ArkCrypt(object):
    def __init__(self, ark):
        self.ark = ark
        self.recipients = dict()
        self.rng = Random.new().read

    def add_recipient(self, user_id, key):
        """Add id to the list of recipients"""
        self.recipients[user_id] = key

    def remove_recipient(self, user_id):
        """Remove id from the list of recipients"""
        del self.recipients[user_id]

    def _create_bundle(self, start, end):
        """Bundles the associated Git repo and returns the path to the bundle

        The file is saved to ARK_PATH/ARK_NAME-START-END.bundle

        Arguments:
            start: At which commit will this bundle start?
            end: At which commit will this bundle end?
        """
        filename = "-".join([self.ark.name, start, end]) + ".bundle"
        filepath = os.path.join(self.ark.path, filename)
        self.ark.repo.git.bundle('create', filepath, "..".join([start, end]))
        return filepath

    def export(self, start, end):
        """Return itself encrypted

        Arguments:
            start: At which commit will this bundle start?
            end: At which commit will this bundle end?

        """
        # Create bundle
        bundle_path = self._create_bundle(start, end)

        # Encrypt bundle
        with open(bundle_path, "r") as source:
            # Compute message hash
            h = SHA256.new()
            for line in source:
                h.update(line)

            # Reset bundle file
            source.seek(0)

            # Encrypt file
            aes_cipher = AES.new(h.digest())
            size = os.path.getsize(bundle_path)
            target_path = bundle_path.rsplit(".", 1)[0]

            with open(target_path + ".ark", "wb") as target:
                for pos in xrange(0, size, 16):
                    line = source.read(16)
                    # TODO: use better padding algo
                    if len(line) < 16:
                        line = line + " " * (16 - len(line))
                    target.write(aes_cipher.encrypt(line))

        # Remove bundle file
        os.remove(bundle_path)

        # Encrypt hash for each recipient
        recipients = dict()
        for user_id, user_key in self.recipients.iteritems():
            user_rsa = RSA.importKey(user_key)
            recipients[user_id] = user_rsa.encrypt(h.digest(), self.rng)

        if not recipients:
            raise Exception('No recipients included!')

        with open(target_path + ".keys", "wb") as keys_file:
            dump(recipients, keys_file)


class KeyBook(yaml.YAMLObject):
    """
    A KeyBook collects RSA keys and can be YAML-encoded.

    Keybook contents are encrypted with a passphrase which must be
    passed to Constructor.

    Arguments:
        passphrase: Passphrase to derive an encryption key from

    """

    yaml_tag = u'!KeyBook'

    def __init__(self, contents=None):
        self.contents = OrderedDict(contents) if contents else OrderedDict()

    def __repr__(self):
        return "%s(contents=%r)" % (
             self.__class__.__name__, self.contents)

    def sealed(fn):
        """ Wrapper that checks if this KeyBook is decrypted. """

        @wraps(fn)
        def wrapper(*args, **kwargs):
            # args[0] == self
            if hasattr(args[0], 'passphrase'):
                return fn(*args, **kwargs)
            else:
                raise Exception('KeyBook is sealed! Call KeyBook.decrypt(passphrase).')
        return wrapper

    def decrypt(self, passphrase):
        """ Set passphrase for decrypting the KeyBook. """

        self.passphrase = passphrase

    @sealed
    def generate_key(self, bits=2048):
        """
        Generate a new UUID / key pair and return it

        Arguments:
            bits: Key length in bits. Must be >1024 and %256==0.
        """
        from uuid import uuid4

        # New UUID for this key
        name = uuid4().hex[:20]

        try:
            key = RSA.generate(bits)
        except Exception as e:
            raise Exception("Problem during generation of new RSA key:", e)

        self.add_key(name, key)
        return name, key

    @sealed
    def add_key(self, name, key):
        """
        Store an existing key in the KeyBook.

        Arguments:
            name: The name used to retrieve the key again
            key: A pycrypto RSA key object

        """

        try:
            key_enc = key.exportKey(passphrase=self.passphrase)
        except AttributeError:
            raise TypeError("Key '%s' is not a valid RSA key object." % str(key))

        if name in self.contents  and self.contents[name] != key_enc:
            raise KeyError("A different key is already stored as '%s'" % name)

        self.contents[name] = key_enc

    @sealed
    def get_key(self, name):
        """
        Return the Key object for name

        Arguments:
            name: The name under which the key is stored in the KeyBook

        """

        try:
            k = RSA.importKey(self.contents[name], passphrase=self.passphrase)
        except KeyError:
            raise KeyError("Key '%s' does not exist in the KeyBook" % name)

        return k

    @sealed
    def get_or_create_key(self, name):
        """
        Return the key object for name. Create a new key if it doesn't exist.

        Arguments:
            name: The name under which the key is to be stored in the KeyBook.
        """
        try:
            return self.get_key(self, name)
        except KeyError:
            return self.generate_key()

    @sealed
    def remove_key(self, name):
        """
        Remove this key from the KeyBook

        Arguments:
            name: The name under which the key is stored in the KeyBook

        """

        try:
            del self.contents[name]
        except KeyError:
            raise KeyError("Key '%s' not found in KeyBook." % name)

    @sealed
    def _yaml(self):
        """ Export YAML-encoded KeyBook contents, excluding the passphrase. """

        from yaml import dump
        p = self.passphrase
        del self.passphrase
        r = dump(self)
        self.passphrase = p
        return r

    @classmethod
    def load_from(cls, f):
        """Load KeyBook contents from the file f or create new KeyBook if empty."""

        kb_enc = f.read()
        if len(kb_enc) == 0:
            logging.warning('Loaded KeyBook file is empty. Generating new instance.')
            return cls()
        else:
            return yaml.load(kb_enc)

    def save_to(self, f):
        """ Save KeyBook contents to the file f """

        f.write(kb._yaml())


def touchopen(filename, *args, **kwargs):
    """
    From Stackoverflow[1]: touch file, then open() it.

    [1] http://stackoverflow.com/questions/10349781/how-to-open-read-write-or-create-a-file-with-truncation-possible

    """

    open(filename, "a").close()  # "touch" file
    return open(filename, *args, **kwargs)

if __name__ == "__main__":
    from uuid import uuid4
    logging.basicConfig(level=logging.DEBUG)

    # Load existing Keybook
    keybook_location = os.path.join(ark.create_path('misc', 'keybook'), 'keybook.yaml')

    with touchopen(keybook_location, 'r') as f:
        kb = KeyBook.load_from(f)

    kb.decrypt('password1')
    bob = kb.generate_key

    # Test generate new key and save contents back to file
    with open(keybook_location, 'w') as f:
        kb.save_to(f)
    quit()

    # Get an Identity object (which is an Ark object)
    pv = ark.Identity('pv')
    print "pv", pv

    # Put it into an ArkCrypt container
    a = ArkCrypt(pv)
    print "ark", a

    # Generate a contact for our identity, Bob
    # Also generate a public RSA key for Bob to which we can then address
    # the message.
    bob_contact_id = uuid4().hex[:20]
    print "bob", bob_contact_id
    bob_key = RSA.generate(2048)
    bob_pubkey = bob_key.publickey().exportKey()

    # Add Bob and his key to the list of recipients
    a.add_recipient(bob_contact_id, bob_pubkey)
    print "recipients", a.recipients

    # Create an Ark for Bob, containing pv's Identity history between the two
    # specified commit objects
    a.export("6c048e4d08d3f09637a86d001d78bfd993524c42", "HEAD")
