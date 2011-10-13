"""An only semi-dumb DBM.

This module is an attempt to do slightly better than the
standard library's dumbdbm.  It's still not that great, but
it does attempt to fix some of the problems that the existing
dumbdbm currently has.

"""
import os
import __builtin__

_open = __builtin__.open
_DELETED = -1


# This basically works by keeping two files, one that only contains the data of
# the values associated with keys, and one which stores the offsets in the
# data file for the keys.  To add a new value to the db, the value is written
# to the data file and the index file is appended with the key name, the offset
# into the data file where the associated data was written, and the size of the
# value.  The format of the index is a very simple format: <size>:<item> where
# <size> is the length of  the item, and <item> is either the key, the offset, or
# the size of the value.  For example, adding a new entry in the index might
# look like this:
# 3:foo3:1242:12
# This will be read in as the tuple ('foo', '124', '12') which is interpreted
# as the value for the key 'foo' is located 124 bytes into the data file and is
# 12 bytes long.

class _SemiDBM(object):
    def __init__(self, filename):
        self._data_filename = filename
        self._index_filename = filename + os.extsep + 'idx'
        self._index = self._load_index(self._index_filename)
        # buffering=0 makes the file objects unbuffered.
        self._index_file = _open(self._index_filename, 'ab', buffering=0)
        self._data_file = _open(self._data_filename, 'ab+', buffering=0)

    def _load_index(self, filename):
        # This method is only used upon instantiation to populate
        # the in memory index.
        if not os.path.exists(filename):
            return {}
        contents = _open(filename, 'r').read()
        index = {}
        start = 0
        items = self._items_in_index(contents)
        for key_name, offset, size in self._read_index(contents):
            if int(size) == _DELETED:
                # This is a deleted item so we need to make sure
                # that this value is not in the index.  We know
                # that the key is already in the index, because
                # a delete is only written to the index if the
                # key already exists in the db.
                del index[key_name]
            else:
                index[key_name] = (int(offset), int(size))
        return index

    def _read_index(self, contents):
        # contents is the raw contents of the index file.
        # This method will read in the contents of the index
        # file and will yield the items in the index in groups
        # of three.  This makes is easier for the calling code
        # to process the items, because one entry requires
        # three items in the index (name, offset, size).
        items = []
        for item in self._items_in_index(contents):
            items.append(item)
            # Only yield in groups of three.  The index is
            # formatted such that one entry has three elements:
            # keyname, offset in the file, size of the value.
            if len(items) == 3:
                yield items
                items = []

    def _items_in_index(self, contents):
        start = 0
        length = len(contents)
        while start < length:
            end = contents.find(':', start)
            item_length = int(contents[start:end])
            yield contents[end + 1:end + item_length + 1]
            start = end + item_length + 1

    def __getitem__(self, key):
        offset, size = self._index[key]
        self._data_file.seek(offset)
        data = self._data_file.read(size)
        self._data_file.seek(0, 2)
        return data

    def __setitem__(self, key, value):
        offset = self._write_to_data_file(value)
        value_length = len(value)
        self._add_item_to_index(key, offset, value_length)

    def _add_item_to_index(self, key, offset, value_length):
        self._index_file.write('%s:%s%s:%s%s:%s' % (
            len(str(key)), key, len(str(offset)), offset,
            len(str(value_length)), value_length))
        self._index[key] = (offset, value_length)

    def _write_to_data_file(self, value):
        # Write the new data out at the end of the file.
        # Returns the offset of where this data is located
        # in the file.
        offset = self._data_file.tell()
        self._data_file.write(value)
        return offset

    def __contains__(self, key):
        return key in self._index

    def __delitem__(self, key):
        offset, value = self._index[key]
        self._add_item_to_index(key, offset, _DELETED)
        del self._index[key]

    def close(self):
        self._index_file.close()
        self._data_file.close()


def open(filename, flag=None, mode=0666):
    return _SemiDBM(filename)
