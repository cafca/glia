import json
import datetime
import iso8601

from hashlib import sha256
from keyczar.keys import AesKey
from uuid import uuid4

from nucleus import InvalidSignatureError, PersonaNotFoundError
from glia import app, db
from glia.models import DBVesicle, Persona

VESICLE_VERSION = "0.1"
DEFAULT_ENCODING = VESICLE_VERSION + "-plain"
SYNAPSE_PORT = None
AES_BYTES = 256


class Vesicle(object):
    """
    Container for peer messages

    see https://github.com/ciex/souma/wiki/Vesicle

    """

    def __init__(self, message_type, id=None, data=None, payload=None, signature=None, author_id=None, created=None, keycrypt=None, enc=DEFAULT_ENCODING, reply_to=SYNAPSE_PORT, souma_id=None):
        self.id = id if id is not None else uuid4().hex
        self._hashcode = None
        self.created = created
        self.data = data
        self.enc = enc
        self.keycrypt = keycrypt
        self.message_type = message_type
        self.payload = payload
        self.send_attributes = set(["message_type", "id", "payload", "enc", "soma_id"])
        self.signature = signature
        self.author_id = author_id
        self.souma_id = souma_id

    def __str__(self):
        """
        Return string identifier
        """

        if hasattr(self, "author_id") and self.author_id is not None:
            p = Persona.query.get(self.author_id)
            if p is not None and p.username is not None:
                author = p.username
            else:
                author = "<[{}]>".format(self.author_id[:6])
        else:
            author = "anon"
        return "<vesicle {type} by {author} [{id}]>".format(
            type=self.message_type,
            author=author,
            id=self.id[:6])

    def encrypt(self, author, recipients):
        """
        Encrypt the vesicle's data field into the payload field and set the data field to None

        @param author The persona whose encrypting key is used
        @param recipients A list of recipient personas who will be added to the keycrypt
        """

        # Validate state
        if self.data == "" or self.data is None:
            raise ValueError("Cannot encrypt empty vesicle {} (empty data field)".format(self))

        # Generate a string representation of the message data
        data = json.encode(self.data)

        # Compute its SHA256 hash code
        self._hashcode = sha256(data)

        # Generate an AES key with key=h
        key = AesKey(self._hashcode, author.hmac_key, AES_BYTES)

        # Encrypt data using the AES key
        payload = key.encrypt(data)

        self.payload = payload
        self.data = None
        self.author_id = author.id
        self.enc = self.enc.split("-")[0] + "-AES" + AES_BYTES
        self.send_attributes.union({"author_id", "keycrypt"})

        for r in recipients:
            self.add_recipient(r)

    def encrypted(self):
        return self.payload is not None and self.enc.split("-")[1] != "plain"

    def decrypt(self, reader_persona):
        """
        Decrypt the vesicle's payload field into the data field.

        This method does not remove the ciphertext from the payload field, so that encrypted() still returns True.

        Args:
            reader_persona (Persona): Persona instance used to retrieve the hash key

        Raises:
            ValueError: If this Vesice is already plaintext
            KeyError: If not Key was found for decrypting
        """

        # Validate state
        if not self.encrypted():
            raise ValueError("Cannot decrypt {}: Already plaintext.".format(self))

        if not reader_persona.id in self.keycrypt.keys():
            raise KeyError("No key found decrypting {} for {}".format(self, reader_persona))

        # Retrieve hashcode
        if self._hashcode:
            h = self._hashcode
        else:
            h = reader_persona.decrypt(self.keycrypt[reader_persona.id])
            self._hashcode = h

        # Generate the AES key
        key = AesKey(h, author.hmac_key, AES_BYTES)

        # Decrypt the data
        data = key.decrypt(self.payload)

        # Decode JSON
        self.data = json.loads(data)

    def decrypted(self):
        return self.data is not None

    def sign(self, author):
        """
        Sign a vesicle

        @param author Persona instance used to created the signature
        """

        if self.author_id is not None and self.author_id != author.id:
            raise ValueError("Signing author {} does not match existing author {}".format(author, self.author_id[:6]))

        if not self.encrypted():
            self.payload = json.dumps(self.data)
            self.data = None
            self.enc = self.enc.split("-")[0] + "plain"

        self.signature = author.sign(self.payload)
        self.author_id = author.id
        self.send_attributes.union({"signature", "author_id"})

    def signed(self):
        """
        Return true if vesicle has a signature and it is valid

        Raises:
            PersonaNotFoundError: The signature can't be verified because the author is not known
        """

        if not hasattr(self, "signature"):
            return False

        author = Persona.query.get(self.author_id)
        if not author:
            raise PersonaNotFoundError("Signature of {} could not be verified: author not found.".format(self))

        return author.verify(self.payload, self.signature)

    def add_recipient(self, recipient):
        """
        Add a persona to the keycrypt

        @param recipient Persona instance to be added
        """
        if not self.encrypted():
            raise Exception("Can not add recipients to plaintext vesicles")

        if not self.decrypted():
            raise Exception("Vesicle must be decrypted for adding recipients")

        if recipient.id in self.keycrypt.keys():
            raise KeyError("Persona {} is already a recipient of {}".format(recipient, self))

        if not self._hashcode:
            raise KeyError("Hashcode not found")

        key = recipient.encrypt(self._hashcode)
        self.keycrypt[recipient.id] = key

    def remove_recipient(self, recipient):
        """
        Remove a persona from the keycrypt

        @param recipient Persona instance to be removed from the keycrypt
        """
        del self.keycrypt[recipient.id]

    def json(self):
        """
        Return JSON representation
        """

        # Temporarily encode data if this is a plaintext message
        if self.payload is None:
            plainenc = True
            self.payload = json.dumps(self.data)
        else:
            plainenc = False

        message = dict()
        for attr in self.send_attributes:
            message[attr] = getattr(self, attr)
        message["created"] = datetime.datetime.now().isoformat()
        r = json.dumps(message)

        if plainenc:
            self.payload = None
        return r

    @staticmethod
    def read(data):
        """
        Create a vesicle instance from its JSON representation

        @param data JSON representation obtained from a vesicle instance's json() method
        """

        msg = json.loads(data)

        version, encoding = msg["enc"].split("-", 1)
        if version != VESICLE_VERSION:
            raise ValueError("Unknown protocol version: {} \nExpecting: {}".format(version, VESICLE_VERSION))
        try:
            if encoding == "plain":
                vesicle = Vesicle(
                    message_type=msg["message_type"],
                    id=msg["id"],
                    payload=msg["payload"],
                    signature=msg["signature"] if "signature" in msg else None,
                    author_id=msg["author_id"] if "signature" in msg else None,
                    created=iso8601.parse_date(msg["created"]),
                    enc=msg["enc"])
            else:
                vesicle = Vesicle(
                    message_type=msg["message_type"],
                    id=msg["id"],
                    payload=msg["payload"],
                    signature=msg["signature"],
                    author_id=msg["author_id"],
                    keycrypt=msg["keycrypt"],
                    created=iso8601.parse_date(msg["created"]),
                    enc=msg["enc"])

            if "signature" in msg:
                vesicle.signature = msg["signature"]
                vesicle.author_id = msg["author_id"]
        except KeyError, e:
            app.logger.error("Vesicle malformed: missing key\n{}".format(e))
            return KeyError(e)

        # Verify signature
        try:
            if vesicle.signature is not None and not vesicle.signed():
                raise InvalidSignatureError(
                    "Invalid signature on {}\nAuthor ID: '{}'\nSignature: '{}'\nPayload: '{}'".format(
                        vesicle, vesicle.author_id, vesicle.signature, vesicle.payload))
        except PersonaNotFoundError:
            raise PersonaNotFoundError("Can not verify Vesicle signature because author [{}] is not known".format(vesicle.author_id))

        return vesicle

    @staticmethod
    def load(self, id):
        """Read a Vesicle back from the local database"""
        v_json = DBVesicle.query.get(id)
        if v_json:
            return Vesicle.read(v_json)
        else:
            raise KeyError("<Vesicle [{}]> could not be found".format(id[:6]))

    def save(self, vesicle_json=None):
        """
        Save this Vesicle to the local Database, overwriting any previous versions

        Parameters:
            vesicle_json (String): Value to store as JSON instead of automatically generated JSON
        """

        if self.payload is None:
            raise TypeError("Cannot store Vesicle without payload ({}). Please encrypt or sign.".format(self))

        if vesicle_json is None:
            vesicle_json = self.json()

        v = DBVesicle.query.get(self.id)
        if v is None:
            app.logger.info("Storing {} in database".format(self))
            created = datetime.datetime.now()
            v = DBVesicle(
                id=self.id,
                json=vesicle_json,
                author_id=self.author_id if 'author_id' in dir(self) else None,
                created=created,
                modified=created
            )
        else:
            v.json = vesicle_json
            v.modified = datetime.datetime.now()
            app.logger.info("Storing updated version of {}, modified {} in database".format(self, v.modified))

        # Update recipients
        if self.keycrypt is not None:
            del v.recipients[:]
            keycrypt = json.loads(self.keycrypt)
            for r_id in keycrypt.keys():
                # Don't add author as recipient
                if r_id == v.author_id:
                    continue

                r = Persona.query.get(r_id)
                if r is None:
                    # TODO: Return error when this happens
                    app.logger.error("Could not find <Persona [{}]> while registring recipients for {}".format(
                        r_id, self))
                else:
                    v.recipients.append(r)
                    db.session.add(r)

        db.session.add(v)
        db.session.commit()