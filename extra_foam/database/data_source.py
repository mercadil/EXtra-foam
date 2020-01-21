"""
Distributed under the terms of the BSD 3-Clause License.

The full license is in the file LICENSE, distributed with this software.

Author: Jun Zhu <jun.zhu@xfel.eu>
Copyright (C) European X-Ray Free-Electron Laser Facility GmbH.
All rights reserved.
"""
from collections import abc, namedtuple

from ..algorithms import OrderedSet
from ..config import config


# category: source category, e.g., Motor, DSSC, LPD
# name: source name, usually the Karabo device ID
# modules: a list of module indices
# slicer: pulse slicer for pulse-resolved data
# vrange: value range
SourceItem = namedtuple(
    'SourceItem',
    ['category', 'name', 'modules', 'property', 'slicer', 'vrange'])


class SourceCatalog(abc.Collection):
    """SourceCatalog class.

    Served as a catalog for searching data sources.
    """
    def __init__(self):
        # key: source name, value: SourceItem
        self._items = dict()
        # key: data category, value: a OrderedSet of source name
        self._categories = dict()

        self._main_detector_category = config["DETECTOR"]
        self._main_detector = ''

    def __contains__(self, item):
        """Override."""
        return self._items.__contains__(item)

    def __len__(self):
        """Override."""
        return self._items.__len__()

    def __iter__(self):
        """Override."""
        return self._items.__iter__()

    def items(self):
        return self._items.items()

    @property
    def main_detector(self):
        return self._main_detector

    def get_category(self, src):
        return self._items[src].category

    def get_slicer(self, src):
        return self._items[src].slicer

    def get_vrange(self, src):
        return self._items[src].vrange

    def from_category(self, ctg):
        return self._categories.get(ctg, OrderedSet())

    def add_item(self, item):
        """Add a source item to the catalog.

        :param SourceItem item: new source item.
        """
        src = f"{item.name} {item.property}"
        self._items[src] = item

        ctg = item.category
        if ctg not in self._categories:
            self._categories[ctg] = OrderedSet()
        self._categories[ctg].add(src)

        if ctg == self._main_detector_category:
            self._main_detector = src

    def remove_item(self, src):
        """Remove an item from the catalog.

        :param str src: source name - <device ID>< ><property>.
        """
        ctg = self._items.__getitem__(src).category
        self._items.__delitem__(src)
        self._categories[ctg].remove(src)
        if not self._categories[ctg]:
            # avoid category with empty set
            self._categories.__delitem__(ctg)

        if ctg == self._main_detector_category:
            self._main_detector = ''

    def clear(self):
        self._items.clear()
        self._categories.clear()
        self._main_detector = ''


class DataTransformer:
    """DataTransformer class.

    Transform external data format to EXtra-foam compatible data
    format for further processing.
    """
    @classmethod
    def transform_euxfel(cls, raw, meta, *, catalog=None, source_type=None):
        """Transform European XFEL data.

        :param dict raw: raw data.
        :param dict meta: meta data.
        :param SourceCatalog catalog: catalog for data source items.
        :param DataSource source_type: the format of the main detector
            source.

        FIXME: I hate weak language and use dictionary without
               encapsulation to store these read-only data. This is
               the source of imperceptible bugs.

        :raises: this method should not raise!!!
        """
        new_raw, new_meta = dict(), dict()
        removed = []
        for src, item in catalog.items():
            ctg, src_name, modules, src_ppt = \
                item.category, item.name, item.modules, item.property

            if modules:
                prefix, suffix = src_name.split("*")
                new_raw[src] = dict()
                module_data = new_raw[src]
                n_found = 0
                i_found = None
                for idx in modules:
                    module_name = f"{prefix}{idx}{suffix}"
                    if module_name in raw:
                        module_data[module_name] = raw[module_name]
                        n_found += 1
                        i_found = module_name

                if n_found == 0:
                    # there is no module data
                    removed.append(src)
                    continue
                else:
                    new_meta[src] = {
                        'tid': meta[i_found]['timestamp.tid'],
                        'source_type': source_type,
                    }
            else:
                try:
                    # caveat: the sequence matters because of property
                    try:
                        new_raw[src] = raw[src_name][src_ppt]
                    except KeyError:
                        new_raw[src] = raw[src_name][f"{src_ppt}.value"]
                except KeyError:
                    # if the requested source or property is not in the data
                    removed.append(src)
                    continue

                new_meta[src] = {
                    'tid': meta[src_name]['timestamp.tid'],
                    'source_type': source_type,
                }

        for src in removed:
            # It ensures that if the source can be found in categories,
            # it must be able to be found in raw and meta.
            catalog.remove_item(src)

        return new_raw, new_meta
