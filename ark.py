#!/usr/bin/env python
# encoding: utf-8
"""
models.py

*Copyright (c) 2012 Vincent Ahrend. All rights reserved.*
"""
import os
import yaml

from git import Repo, NoSuchPathError
from collections import OrderedDict

ELEMENTS = ('image', 'link')
META_FILENAME = 'meta.yaml'
DATA_DIRECTORY = '/Users/vahrend/Projects/Arche/v1/src/data/'

os.environ['GIT_PYTHON_TRACE'] = 'true'


def create_path(t, n):
    """Return a path string for a given subfolder of the data directory. Create folder if necessary.

    Arguments:
        t: Subdirectory A: Type of the thing to be stored in the path (identity, planet, ...)

        n: Subdirectory B: Name of the thing to be stored.
    """

    # Map object type to data directory names
    type_to_dirname = {
        'identity': 'identities',
        'planet':   'planets',
        'misc':     'misc',
    }

    try:
        data_dir = os.path.join(DATA_DIRECTORY, type_to_dirname[t])
    except KeyError:
        data_dir = os.path.join(DATA_DIRECTORY, 'misc')

    name = create_title(n)
    full_path = os.path.join(data_dir, name)

    # Create folders if necessary
    if not os.path.exists(full_path):
        os.makedirs(full_path)

    return full_path


def create_title(t):
    """Create a filename-safe string from the given name."""

    filename_allowed = '-_.()abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return "".join(c for c in t if c in filename_allowed)


class Particle(yaml.YAMLObject):

    """
    Baseclass for things that will be stored YAML-encoded.

    A Particle provides an ordered dictionary which makes diffing of the created
    YAML files easier.

    Arguments:
        contents: Dictionary of contents for this particle.
            Can be a file or string.

    Example:
        >>> p = Particle()
        >>> p.contents['Name'] = 'funky_pine'
        >>> p.contents['Age'] = '900 years'
        >>> print p.yaml()

        Output:

        >>> !Particle
        >>> contents: !!python/object/apply:collections.OrderedDict
        >>>   - - [Age, 900 years]
        >>>     - [Name, funky_pine]

    """

    yaml_tag = u'!Particle'

    def __init__(self, contents=None):
        #: Stores the OrderedDict with the contents of this Particle
        self.contents = OrderedDict(contents) if contents else OrderedDict()

    def __repr__(self):
        return "%s(contents=%r)" % (
             self.__class__.__name__, self.contents)

    def yaml(self):
        """Return this Particle in YAML-encoding."""

        from yaml import dump
        return dump(self)


class DictDiffer(object):
    """
    Calculate the difference between two dictionaries as:
    (1) items added
    (2) items removed
    (3) keys same in both but changed values
    (4) keys same in both and unchanged values
    """
    def __init__(self, current_dict, past_dict):
        self.current_dict, self.past_dict = current_dict, past_dict
        self.set_current, self.set_past = set(
            current_dict.keys()), set(past_dict.keys())
        self.intersect = self.set_current.intersection(self.set_past)
        self.modes = ['added', 'removed', 'changed']

    def added(self):
        return self.set_current - self.intersect

    def removed(self):
        return self.set_past - self.intersect

    def changed(self):
        return set(o for o in self.intersect
                    if self.past_dict[o] != self.current_dict[o])

    def unchanged(self):
        return set(o for o in self.intersect
                    if self.past_dict[o] == self.current_dict[o])

    def enum(self, mode):
        return ",".join([str(x) for x in getattr(self, mode)()])


class Ark(object):

    """
    Baseclass for all things that have their own Git repository.

    An Ark always has some meta information with it that it can store on its
    own. It also creates a Git repository for itself at a path which is
    created according to the Ark type and name.

    Attributes:
        _meta_attributes: Contains a set of names of attributes of the Ark
            object. These will be extracted from the object and stored in the
            Git-Repository when the entity is saved.

    Arguments:
        t: Type of the Ark (eg. identity, planet)

        n: Display name of the Ark

    """

    default_meta_attributes = set(['name', 'object_type', 'path', 'created', 'created_offset', '_meta_attributes'])

    def __init__(self, t, n):
        self.object_type = t

        #: Created datetime stores the timestamp of creation.
        #: It is recorded on creation of a git repo.
        self.created = None

        #: The offset depends on the local time of the machine used for creation
        self.created_offset = None

        if len(n) > 160:
            raise ValueError("Name of a %s must be longer than 160 characters" % self.type)

        #: The name of an Ark is used as the diplay name, it must contain
        #: less then 160 characters
        self.name = n

        #: Path records the location of the Git repository
        self.path = create_path(self.object_type, self.name)

        try:
            #: Repo contains the Git repository as a GitPython instance
            self.repo = Repo(self.path)
            self.load_metafile()
            log.msg("Loaded repo %s from %s" % (self.name, self.path))
        except NoSuchPathError:
            # Repo is not callable, create it
            self._init_repo()

    def _init_repo(self):
        """Initialize the Git repository for this Ark with basic metadata."""
        # Create a repository

        # TODO: check if the folder already exists
        try:
            os.mkdir(self.path)
        except OSError:
            raise Exception("Could not create directory '%s'" % self.path)

        # Create an empty repository in the new folder
        self.repo = Repo.init(self.path)

        # Create initial commit
        self.repo.index.commit("Created repository '%s'" % self.name)

        # Read out created date
        self.created, self.created_offset = self.repo.head.log()[0][3]

        #: meta_attributes is stored by store_metafile() in the Git repo as
        #: a Metaparticle
        self._meta_attributes = set()
        self._meta_attributes |= self.default_meta_attributes
        self.store_metafile('Init attribute store')

        log.msg("Created repo %s in %s" % (self.name, self.path))

    def store_metafile(self, commit_message='Updated meta information'):
        """Store metadata specified by self.meta_attributes in a YAML encoded file / Metaparticle """

        # Read meta attributes by extracting attributes named in self._meta_attributes from self

        try:
            meta_contents = dict(zip(self._meta_attributes,
                [getattr(self, attribute_name) for attribute_name in self._meta_attributes]))
        except AttributeError:
            raise KeyError('Specified meta-attribute %s is not supplied by "%s"' % (attribute_name, self))

        # Write data to disk in a Metaparticle
        with open(os.path.join(self.path, META_FILENAME), 'w') as f:
            f.write(yaml.dump(
                Particle(meta_contents), default_flow_style=False))

        if self.repo.is_dirty():
            # Read old metadata for comparison
            with open(os.path.join(self.path, META_FILENAME), 'r') as f:
                old_meta_particle = yaml.load(f.read())

            # Create commit message diff
            # This describes all changes made to attributes listed in
            # _meta_attributes
            diff = DictDiffer(old_meta_particle.contents, meta_contents)
            commit_message += " ".join(["%s:%s" % (mode, items) for mode, items in
                zip(diff.modes, [diff.enum(mode) for mode in diff.modes])
                    if len(items) > 0])

            # Create new commit
            self.repo.index.add([META_FILENAME])
            self.repo.index.commit(commit_message)

    def load_metafile(self):
        """Load metadata from meta.yaml and assign it to self."""
        with open(os.path.join(self.path, META_FILENAME), 'r') as f:
            meta_particle = yaml.load(f.read())

        for key, value in meta_particle.contents.iteritems():
            self.__setattr__(key, value)


class Identity(Ark):

    """
    Class for a single identity

    Arguments:
        name: Display name for this Identity.

    Example:
        >>> p = Identity('Sam')
        >>> p.pin(my_star)

    """

    def __init__(self, name, email=''):
        super(Identity, self).__init__('identity', name)

        #: starmap contains the set of Stars which are pinned to this Identity
        #: They are visible to anyone who can see this Identity's profile page
        self.starmap = set()

        # Add Identity specific meta attributes
        self._meta_attributes.add('starmap')
        self._meta_attributes.add('email')
        self.store_metafile('Add starmap to Identity')

    def pin(self, star):
        """Add a star to this Identity's starmap."""

        if not isinstance(star, Star):
            raise TypeError('"%r" can not be pinned to "%r" as it is not a Star' % (star, self))
        self.starmap.add(star)
        self.store_metafile('Pin new Star')

    def unpin(self, star):
        """Remove a star from this Identity's starmap."""

        if not isinstance(star, Star):
            raise TypeError("Tried to remove '%s' from '%s's starmap but it is not a star!" % (star, self))

        try:
            self.starmap.remove(star)
        except KeyError:
            raise KeyError("Tried to remove star '%s' from '%s's starmap but it is not there." % (star, self))


class Star(yaml.YAMLObject):

    """
    A Star is a single post. It may have planets containing media
    attached to it.

    Arguments:
        creator: Identity instance (or path) which casts this Star.

        title: Optional title field with <160 chars

        text: Optional text field

    """

    yaml_tag = u'!Star'

    def __init__(self, creator, title=None, text=None, planets=None):
        if isinstance(creator, Identity):
            #: Creator is the path of the identity instance that cast this Star
            self.creator = creator.path
        else:
            self.creator = creator

        #: Optional title of the Star
        self.title = title

        if text is not None and len(text) > 160:
            raise ValueError("Text description of a Star must be shorter than 160 characters")
        #: Optional text field with <160 characters
        self.text = text

        if planets is not None:
            #: Contains the set of planets
            self.planets = planets
        else:
            self.planets = dict()

    def __repr__(self):
        return "%s(creator=%r,title=%r,text=%r,planets=%r)" % (
             self.__class__.__name__, self.creator.path, self.title,
                self.text, self.planets)

    def addPlanet(self, planet, creator=None, author=None):
        """Add a Planet (attachment) to this Star.

        Arguments:
            planet: A Planet instance which contains an attachment.
        """

        meta = dict()

        if not isinstance(planet, Planet):
            # import pdb; pdb.set_trace()
            raise TypeError('Tried to add "%r" as a Planet to Star "%r"' (planet, self))

        # Validate creator argument
        if creator:
            if isinstance(creator, basestring) and len(creator) > 160:
                raise ValueError("Author name must be less than 160 characters long")
            meta['creator'] = creator
        else:
            meta['creator'] = self.creator

        # Validate author argument
        if author:
            if isinstance(author, basestring) and len(author) > 160:
                raise ValueError("Author name must be less than 160 characters long")
            meta['author'] = author
        else:
            meta['author'] = self.creator

        self.planets[planet.path] = meta

    def removePlanet(self, planet):
        """Remove a Planet from this Star.

        Arguments:
            planet: A Planet instance that should be removed.
        """

        if not isinstance(planet, Planet):
            raise TypeError('Tried to remove "%r" as a Planet from Star "%r"' (planet, self))
        try:
            self.planets[planet.path] = None
        except KeyError:
            raise KeyError('Planet "%r" can not be removed from Star "%r" as it is not part of it.' % (planet, self))


class Planet(Ark):

    """
    A Planet describes an attachment to a Star.

    It can contain media files and/or other attachments and is
    stored in a Git repository. Currently it is referenced by its local path
    but eventually that should be replaced by a hash for the contents which is
    the same when a Planet is created from the same media files on a different
    client.

    Arguments:
        content: Contents of the planet.
            This should only include the part of the content that is expected
            to be repeatly added across the network ie. no additional metadata,
            etc

    """

    def __init__(self, content, meta=None):
        import hashlib

        # TODO: Support list of filenames

        #: SHA-256 representation of the content used to create the Planet
        self.hash = hashlib.sha256()

        if isinstance(content, file):
            self.hash.update(content.read())
        elif isinstance(content, basestring):
            self.hash.update(content)
        else:
            raise TypeError("Need string or filelike, received %r" % content)

        # Prepend planet hash with classname
        title = "-".join([self.__class__.__name__, self.get_hash(short=True)])

        # TODO: Whap happens on hash abbrev collision?

        super(Planet, self).__init__('planet', title)

        #: Stores meta information about the contained media
        self.element_meta = dict()
        self.element_meta['kind'] = self.__class__.__name__

        if isinstance(content, file):
            # Copy file to planet path
            from shutil import copy

            filepath = content.name
            filename = os.path.basename(filepath)

            self.element_meta['filename'] = filename

            # Copy original file into working directory
            copy(filepath, self.path)

            # Add new file to index
            self.repo.index.add([filename])
        else:
            if meta is None:
                raise KeyError('Meta argument must be supplied if content' +
                    'is no file.')

            self.element_meta = dict(self.element_meta.items() + meta.items())

        self._meta_attributes.add('element_meta')
        self.store_metafile('Add Planet')

    def __repr__(self):

        return "%s (%s)" % (self.path, self.hash(short=True))

    def get_hash(self, short=False):
        """Return this planet's hash

        Arguments:

            short: Return a 7-digit abbreviation if True

        """
        h = self.hash.hexdigest()
        return h if not short else h[:7]


class Image(Planet):

    """
    Class for pictures that can be attached to a Star.

    Arguments:
        filepath: Path to the picture file on the local filesystem

        creator: Identity instance of the creator of this attachment

        author: Either an Identity instance or a character string
            description of the original author of this image.

    """

    def __init__(self, filepath):
        with open(filepath, 'r') as f:
            super(Image, self).__init__(f)


class Link(Planet):

    """
    Class for URL link that can be attached to a Star.

    Arguments:
        creator: Identity instance of the creator of this attachment

        url: URL of the content to be linked

    """

    def __init__(self, url):
        import requests
        from bs4 import BeautifulSoup as BS

        # Retrieve information about the link
        r = requests.get(url)
        soup = BS(r.text)
        site_title = soup.title.text

        super(Link, self).__init__(r.url, {
            "html_title": site_title,
            "url": r.url,
            })


if __name__ == "__main__":
    pv = Identity('pv')
    tr = Identity('Trami')

    s = Star(pv, "Coole Internetseite")
    s.addPlanet(Link("http://www.vincentahrend.com/"))
    s.addPlanet(Image('/Users/vahrend/Pictures/kinderkram1.jpeg'))
    pv.pin(s)
