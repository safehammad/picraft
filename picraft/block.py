# vim: set et sw=4 sts=4 fileencoding=utf-8:
#
# An alternate Python Minecraft library for the Rasperry-Pi
# Copyright (c) 2013-2015 Dave Jones <dave@waveform.org.uk>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the copyright holder nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""
The block module defines the :class:`Block` class, which is used to represent
the type of a block and any associated data it may have, and the
:class:`Blocks` class which is used to implement the
:attr:`~picraft.world.World.blocks` attribute on the
:class:`~picraft.world.World` class.

.. note::

    All items in this module are available from the :mod:`picraft` namespace
    without having to import :mod:`picraft.block` directly.

The following items are defined in the module:

Block
=====

.. autoclass:: Block(id, data)


BLOCK_COLORS
============

.. data:: BLOCK_COLORS

    A set of the available colors that can be used with
    :meth:`Block.from_color`.  Each color is represented as ``(red, green,
    blue)`` tuple where each component is an integer between 0 and 255.


Compatibility
=============

Finally, the module also contains compatibility values equivalent to those
in the mcpi.block module of the reference implementation. Each value represents
the type of a block with no associated data:

* AIR
* BED
* BEDROCK
* BEDROCK_INVISIBLE
* BOOKSHELF
* BRICK_BLOCK
* CACTUS
* CHEST
* CLAY
* COAL_ORE
* COBBLESTONE
* COBWEB
* CRAFTING_TABLE
* DIAMOND_BLOCK
* DIAMOND_ORE
* DIRT
* DOOR_IRON
* DOOR_WOOD
* FARMLAND
* FENCE
* FENCE_GATE
* FIRE
* FLOWER_CYAN
* FLOWER_YELLOW
* FURNACE_ACTIVE
* FURNACE_INACTIVE
* GLASS
* GLASS_PANE
* GLOWING_OBSIDIAN
* GLOWSTONE_BLOCK
* GOLD_BLOCK
* GOLD_ORE
* GRASS
* GRASS_TALL
* GRAVEL
* ICE
* IRON_BLOCK
* IRON_ORE
* LADDER
* LAPIS_LAZULI_BLOCK
* LAPIS_LAZULI_ORE
* LAVA
* LAVA_FLOWING
* LAVA_STATIONARY
* LEAVES
* MELON
* MOSS_STONE
* MUSHROOM_BROWN
* MUSHROOM_RED
* NETHER_REACTOR_CORE
* OBSIDIAN
* REDSTONE_ORE
* SAND
* SANDSTONE
* SAPLING
* SNOW
* SNOW_BLOCK
* STAIRS_COBBLESTONE
* STAIRS_WOOD
* STONE
* STONE_BRICK
* STONE_SLAB
* STONE_SLAB_DOUBLE
* SUGAR_CANE
* TNT
* TORCH
* WATER
* WATER_FLOWING
* WATER_STATIONARY
* WOOD
* WOOD_PLANKS
* WOOL
"""

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
try:
    from itertools import izip as zip
except ImportError:
    pass
str = type('')


import io
import warnings
from math import sqrt
from collections import namedtuple
from operator import itemgetter
try:
    # Py2 compat
    from itertools import izip_longest as zip_longest
except ImportError:
    from itertools import zip_longest

from pkg_resources import resource_stream
from .exc import EmptySliceWarning
from .vector import Vector, vector_range


def _read_block_data(filename_or_object):
    if isinstance(filename_or_object, str):
        stream = io.open(filename_or_object, 'rb')
    else:
        stream = filename_or_object
    for line in stream:
        line = line.decode('utf-8').strip()
        if line and not line.startswith('#'):
            id, data, pi, pocket, name, description = line.split(None, 5)
            yield int(id), int(data), bool(int(pi)), bool(int(pocket)), name, description

def _read_block_color(filename_or_object):
    if isinstance(filename_or_object, str):
        stream = io.open(filename_or_object, 'rb')
    else:
        stream = filename_or_object
    int2color = lambda n: ((n & 0xff0000) >> 16, (n & 0xff00) >> 8, n & 0xff)
    for line in stream:
        line = line.decode('utf-8').strip()
        if line and not line.startswith('#'):
            id, data, color = line.split(None, 2)
            yield int(id), int(data), int2color(int(color, 16))


_BLOCKS_DB = {
    (id, data): (pi, pocket, name, description)
    for (id, data, pi, pocket, name, description) in
        _read_block_data(resource_stream(__name__, 'block.data'))
    }

_BLOCKS_BY_ID = {
    id: (pi, pocket, name)
    for (id, data), (pi, pocket, name, description) in _BLOCKS_DB.items()
    if data == 0
    }

_BLOCKS_BY_NAME = {
    name: id
    for (id, data), (pi, pocket, name, description) in _BLOCKS_DB.items()
    if data == 0
    }

_BLOCKS_BY_COLOR = {
    color: (id, data)
    for (id, data, color) in
        _read_block_color(resource_stream(__name__, 'block.color'))
    }

BLOCK_COLORS = _BLOCKS_BY_COLOR.keys()


class Block(namedtuple('Block', ('id', 'data'))):
    """
    Represents a block within the Minecraft world.

    Blocks within the Minecraft world are represented by two values: an *id*
    which defines the type of the block (air, stone, grass, wool, etc.) and an
    optional *data* value (defaults to 0) which means different things for
    different block types (e.g.  for wool it defines the color of the wool).

    Blocks are represented by this library as a :func:`namedtuple` of the *id*
    and the *data*. Calculated properties are provided to look up the
    :attr:`name` and :attr:`description` of the block from a database derived
    from the Minecraft wiki, and classmethods are defined to construct a block
    definition from an :meth:`id <from_id>` or from alternate things like a
    :meth:`name <from_name>` or an :meth:`RGB color <from_color>`::

        >>> Block.from_id(0, 0)
        <Block "air" id=0 data=0>
        >>> Block.from_id(2, 0)
        <Block "grass" id=2 data=0>
        >>> Block.from_name('stone')
        <Block "stone" id=1 data=0>
        >>> Block.from_color('#ffffff')
        <Block "wool" id=35 data=0>

    The default constructor attempts to guess which classmethod to call based
    on the following rules (in the order given):

    1. If the constructor is passed a string beginning with '#' that is 7
       characters long, it calls :meth:`from_color`

    2. If the constructor is passed a tuple containing 3 values, it calls
       :meth:`from_color`

    3. If the constructor is passed a string (not matching the case above)
       it calls :meth:`from_name`

    4. Otherwise the constructor calls :meth:`from_id` with all given
       parameters

    This means that the examples above can be more easily written::

        >>> Block(0, 0)
        <Block "air" id=0 data=0>
        >>> Block(2, 0)
        <Block "grass" id=2 data=0>
        >>> Block('stone')
        <Block "stone" id=1 data=0>
        >>> Block('#ffffff')
        <Block "wool" id=35 data=0>

    Aliases are provided for compatibility with the official reference
    implementation (AIR, GRASS, STONE, etc)::

        >>> import picraft.block
        >>> picraft.block.WATER
        <Block "flowing_water" id=8 data=0>

    .. automethod:: from_color

    .. automethod:: from_id

    .. automethod:: from_name

    .. attribute:: id

        The "id" or type of the block. Each block type in Minecraft has a
        unique value. For example, air blocks have the id 0, stone, has id 1,
        and so forth. Generally it is clearer in code to refer to a block's
        :attr:`name` but it may be quicker to use the id.

    .. attribute:: data

        Certain types of blocks have variants which are dictated by the data
        value associated with them. For example, the color of a wool block
        is determined by the *data* attribute (e.g. white is 0, red is 14,
        and so on).

    .. autoattribute:: pi

    .. autoattribute:: pocket

    .. autoattribute:: name

    .. autoattribute:: description
    """

    def __new__(cls, *args, **kwargs):
        if len(args) >= 1:
            a = args[0]
            if isinstance(a, bytes):
                a = a.decode('utf-8')
            if isinstance(a, str) and len(a) == 7 and a.startswith('#'):
                return cls.from_color(*args, **kwargs)
            elif isinstance(a, tuple) and len(a) == 3:
                return cls.from_color(*args, **kwargs)
            elif isinstance(a, str):
                return cls.from_name(*args, **kwargs)
            else:
                return cls.from_id(*args, **kwargs)
        else:
            if 'id' in kwargs:
                return cls.from_id(**kwargs)
            elif 'name' in kwargs:
                return cls.from_name(**kwargs)
            elif 'color' in kwargs:
                return cls.from_color(**kwargs)
        raise TypeError('invalid combination of arguments for Block')

    @classmethod
    def from_string(cls, s):
        id, data = s.split(',', 1)
        return cls.from_id(int(id), int(data))

    @classmethod
    def from_id(cls, id, data=0):
        """
        Construct a :class:`Block` instance from an *id* integer. This may be
        used to construct blocks in the classic manner; by specifying a number
        representing the block's type, and optionally a data value. For
        example::

            >>> from picraft import *
            >>> Block.from_id(1)
            <Block "stone" id=1 data=0>
            >>> Block.from_id(2, 0)
            <Block "grass" id=2 data=0>

        The optional *data* parameter defaults to 0. Note that calling the
        default constructor with an integer parameter is equivalent to calling
        this method::

            >>> Block(1)
            <Block "stone" id=1" data=0>
        """
        return super(Block, cls).__new__(cls, id, data)

    @classmethod
    def from_name(cls, name, data=0):
        """
        Construct a :class:`Block` instance from a *name*, as returned by the
        :attr:`name` property. This may be used to construct blocks in a more
        "friendly" way within code. For example::

            >>> from picraft import *
            >>> Block.from_name('stone')
            <Block "stone" id=1 data=0>
            >>> Block.from_name('wool', data=2)
            <Block "wool" id=35 data=2>

        The optional *data* parameter can be used to specify the data component
        of the new :class:`Block` instance; it defaults to 0. Note that calling
        the default constructor with a string that doesn't start with "#" is
        equivalent to calling this method::

            >>> Block('stone')
            <Block "stone" id=1 data=0>
        """
        if isinstance(name, bytes):
            name = name.decode('utf-8')
        try:
            id = _BLOCKS_BY_NAME[name]
        except KeyError:
            raise ValueError('unknown name %s' % name)
        return cls(id, data)

    @classmethod
    def from_color(cls, color, exact=False):
        """
        Construct a :class:`Block` instance from a *color* which can be
        represented as:

        * A tuple of ``(red, green, blue)`` integer byte values between 0 and
          255
        * A tuple of ``(red, green, blue)`` float values between 0.0 and 1.0
        * A string in the format '#rrggbb' where rr, gg, and bb are hexadecimal
          representations of byte values.

        If *exact* is ``False`` (the default), and an exact match for the
        requested color cannot be found, the nearest color (determined simply
        by Euclidian distance) is returned. If *exact* is ``True`` and an exact
        match cannot be found, a :exc:`ValueError` will be raised::

            >>> from picraft import *
            >>> Block.from_color('#ffffff')
            <Block "wool" id=35 data=0>
            >>> Block.from_color('#ffffff', exact=True)
            Traceback (most recent call last):
              File "<stdin>", line 1, in <module>
              File "picraft/block.py", line 351, in from_color
                if exact:
            ValueError: no blocks match color #ffffff
            >>> Block.from_color((1, 0, 0))
            <Block "wool" id=35 data=14>

        Note that calling the default constructor with any of the formats
        accepted by this method is equivalent to calling this method::

            >>> Block('#ffffff')
            <Block "wool" id=35 data=0>
        """
        if isinstance(color, bytes):
            color = color.decode('utf-8')
        if isinstance(color, str):
            try:
                if not (color.startswith('#') and len(color) == 7):
                    raise ValueError()
                color = (
                        int(color[1:3], 16),
                        int(color[3:5], 16),
                        int(color[5:7], 16))
            except ValueError:
                raise ValueError('unrecognized color format: %s' % color)
        else:
            try:
                r, g, b = color
            except (TypeError, ValueError):
                raise ValueError('expected three values in color')
            if 0.0 <= r <= 1.0 and 0.0 <= g <= 1.0 and 0.0 <= b <= 1.0:
                color = tuple(int(n * 255) for n in color)
        try:
            id, data = _BLOCKS_BY_COLOR[color]
        except KeyError:
            r, g, b = color
            if exact:
                raise ValueError(
                    'no blocks match color #%06x' % (r << 16 | g << 8 | b))
            diff = lambda block_color: sqrt(
                    sum((c1 - c2) ** 2 for c1, c2 in zip(color, block_color)))
            matched_color, (id, data) = sorted(
                    _BLOCKS_BY_COLOR.items(), key=lambda i: diff(i[0]))[0]
        return cls(id, data)

    def __repr__(self):
        try:
            return '<Block "%s" id=%d data=%d>' % (self.name, self.id, self.data)
        except KeyError:
            return '<Block id=%d data=%d>' % (self.id, self.data)

    @property
    def pi(self):
        """
        Returns a bool indicating whether the block is present in the Pi
        Edition of Minecraft.
        """
        return _BLOCKS_BY_ID[self.id][0]

    @property
    def pocket(self):
        """
        Returns a bool indicating whether the block is present in the Pocket
        Edition of Minecraft.
        """
        return _BLOCKS_BY_ID[self.id][1]

    @property
    def name(self):
        """
        Return the name of the block. This is a unique identifier string which
        can be used to construct a :class:`Block` instance with
        :meth:`from_name`.
        """
        return _BLOCKS_BY_ID[self.id][2]

    @property
    def description(self):
        """
        Return a description of the block. This string is not guaranteed to be
        unique and is only intended for human use.
        """
        try:
            return _BLOCKS_DB[(self.id, self.data)][3]
        except KeyError:
            return _BLOCKS_DB[(self.id, 0)][3]


class Blocks(object):
    """
    This class implements the :attr:`~picraft.world.World.blocks` attribute.
    """
    def __init__(self, connection):
        self._connection = connection

    def __repr__(self):
        return '<Blocks>'

    def __getitem__(self, index):
        if isinstance(index, slice):
            vr = vector_range(index.start, index.stop, index.step)
            if not vr:
                warnings.warn(EmptySliceWarning(
                    "ignoring empty slice passed to blocks"))
            elif (
                    abs(vr.step) == Vector(1, 1, 1) and
                    self._connection.server_version == 'raspberry-juice'):
                return [
                    Block.from_string('%d,0' % int(i))
                    for i in self._connection.transact(
                        'world.getBlocks(%d,%d,%d,%d,%d,%d)' % (
                        vr.start.x, vr.start.y, vr.start.z,
                        vr.stop.x - vr.step.x, vr.stop.y - vr.step.y, vr.stop.z - vr.step.z)).split(',')
                    ]
            else:
                return [
                    Block.from_string(
                        self._connection.transact(
                            'world.getBlockWithData(%d,%d,%d)' % (v.x, v.y, v.z)))
                    for v in vector_range(index.start, index.stop, index.step)
                    ]
        else:
            return Block.from_string(
                self._connection.transact(
                    'world.getBlockWithData(%d,%d,%d)' % (index.x, index.y, index.z)))

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            vr = vector_range(index.start, index.stop, index.step)
            if not vr:
                warnings.warn(EmptySliceWarning(
                    "ignoring empty slice passed to blocks"))
            elif (
                    abs(vr.step) == Vector(1, 1, 1) and
                    hasattr(value, 'id') and
                    hasattr(value, 'data')):
                self._connection.send(
                    'world.setBlocks(%d,%d,%d,%d,%d,%d,%d,%d)' % (
                        vr.start.x, vr.start.y, vr.start.z,
                        vr.stop.x - vr.step.x, vr.stop.y - vr.step.y, vr.stop.z - vr.step.z,
                        value.id, value.data))
            else:
                for v, b in zip_longest(vr, value):
                    if v is None:
                        raise ValueError('too many blocks for vector range')
                    if b is None:
                        raise ValueError('not enough blocks for vector range')
                    self._connection.send(
                        'world.setBlock(%d,%d,%d,%d,%d)' % (
                            v.x, v.y, v.z, b.id, b.data))
        else:
            self._connection.send(
                'world.setBlock(%d,%d,%d,%d,%d)' % (
                    index.x, index.y, index.z, value.id, value.data))


AIR                 = Block(0)
STONE               = Block(1)
GRASS               = Block(2)
DIRT                = Block(3)
COBBLESTONE         = Block(4)
WOOD_PLANKS         = Block(5)
SAPLING             = Block(6)
BEDROCK             = Block(7)
WATER_FLOWING       = Block(8)
WATER               = WATER_FLOWING
WATER_STATIONARY    = Block(9)
LAVA_FLOWING        = Block(10)
LAVA                = LAVA_FLOWING
LAVA_STATIONARY     = Block(11)
SAND                = Block(12)
GRAVEL              = Block(13)
GOLD_ORE            = Block(14)
IRON_ORE            = Block(15)
COAL_ORE            = Block(16)
WOOD                = Block(17)
LEAVES              = Block(18)
GLASS               = Block(20)
LAPIS_LAZULI_ORE    = Block(21)
LAPIS_LAZULI_BLOCK  = Block(22)
SANDSTONE           = Block(24)
BED                 = Block(26)
COBWEB              = Block(30)
GRASS_TALL          = Block(31)
WOOL                = Block(35)
FLOWER_YELLOW       = Block(37)
FLOWER_CYAN         = Block(38)
MUSHROOM_BROWN      = Block(39)
MUSHROOM_RED        = Block(40)
GOLD_BLOCK          = Block(41)
IRON_BLOCK          = Block(42)
STONE_SLAB_DOUBLE   = Block(43)
STONE_SLAB          = Block(44)
BRICK_BLOCK         = Block(45)
TNT                 = Block(46)
BOOKSHELF           = Block(47)
MOSS_STONE          = Block(48)
OBSIDIAN            = Block(49)
TORCH               = Block(50)
FIRE                = Block(51)
STAIRS_WOOD         = Block(53)
CHEST               = Block(54)
DIAMOND_ORE         = Block(56)
DIAMOND_BLOCK       = Block(57)
CRAFTING_TABLE      = Block(58)
FARMLAND            = Block(60)
FURNACE_INACTIVE    = Block(61)
FURNACE_ACTIVE      = Block(62)
DOOR_WOOD           = Block(64)
LADDER              = Block(65)
STAIRS_COBBLESTONE  = Block(67)
DOOR_IRON           = Block(71)
REDSTONE_ORE        = Block(73)
SNOW                = Block(78)
ICE                 = Block(79)
SNOW_BLOCK          = Block(80)
CACTUS              = Block(81)
CLAY                = Block(82)
SUGAR_CANE          = Block(83)
FENCE               = Block(85)
GLOWSTONE_BLOCK     = Block(89)
BEDROCK_INVISIBLE   = Block(95)
STONE_BRICK         = Block(98)
GLASS_PANE          = Block(102)
MELON               = Block(103)
FENCE_GATE          = Block(107)
GLOWING_OBSIDIAN    = Block(246)
NETHER_REACTOR_CORE = Block(247)

