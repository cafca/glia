import json
import datetime

from hashlib import sha256
from keyczar.keys import AesKey
from web_ui.models import Persona

VESICLE_VERSION = 0.1
SYNAPSE_PORT = None
AES_BYTES = 256


class Vesicle(object):
    """
    Container for peer messages
    """

    def __init__(self, message_type, data=None, cipher=None, signature=None, version=VESICLE_VERSION, reply_to=SYNAPSE_PORT):
        self.message_type = message_type
        self.data = data
        self.cipher = cipher
        self.created = None
        self.send_attributes = ["message_type", "cipher", "data", "signature", "reply_to", "version"]
        self.reply_to = reply_to

    def __str__(self):
        """
        Return string identified
        """

        if hasattr(self, "author_id"):
            p = Persona.query.get(self.author_id)
            if p:
                author = p.username
            else:
                author = author_id[:6]
        else:
            author = "anon"
        return "<vesicle {id}@{author}>".format(id=self.id[:6], author=author)

    def encrypt(self, author):
        """
        Encrypt the vesicle's data field into the cipher field
        """

        # Generate a string representation of the message data
        data = json.encode(self.data)

        # Compute its SHA256 hash code
        h = sha256(data)

        # Generate an AES key with key=h
        key = AesKey(h, author.hmac_key, AES_BYTES)

        # Encrypt data using the AES key
        cipher = key.encrypt(data)

        self.cipher = cipher
        self.author_id = author.id

    def encrypted(self):
        return self.cipher is not None

    def decrypt(self, reader_persona):
        """
        Decrypt the vesicle's cipher field into the data field
        """

        # Retrieve author persona
        author = Persona.query.get(self.author_id)
        if not author:
            raise NameError("Author of vesicle {} could not be found: Decryption failed.".format(self))

        # Check permissions
        if not reader_persona.id in self.keyring.keys():
            raise KeyError("No key found for decrypting {} for {}".format(self, reader_persona))

        # Decrypt hash key
        h = reader_persona.decrypt(self.keyring[reader_persona.id])

        # Generate the AES key
        key = AesKey(h, author.hmac_key, AES_BYTES)

        # Decrypt the data
        data = key.decrypt(self.cipher)

        # Decode JSON
        self.data = json.loads(data)

    def decrypted(self):
        return self.data is not None

    def json(self):
        """
        Return JSON representation
        """

        message = dict()
        for attr in self.send_attributes:
            message[attr] = getattr(self, attr)
        message["timestamp"] = datetime.datetime.now().isoformat()
        return json.dumps(message)

    @staticmethod
    def read(data):
        """Create a vesicle instance from its JSON representation"""

        # TODO Catch errors
        msg = json.loads(data)
        vesicle = Vesicle(
            message_type=msg["message_type"],
            cipher=msg["cipher"],
            data=msg["data"],
            signature=msg["signature"],
            reply_to=msg["reply_to"],
            version=msg["version"])

        return vesicle
