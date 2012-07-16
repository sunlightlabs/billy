import re
import urlparse
import datetime
from django.template.defaultfilters import truncatewords

from .base import db, feeds_db, Document
from .metadata import Metadata


class FeedEntry(Document):
    collection = feeds_db.entries

    def __init__(self, *args, **kw):
        super(FeedEntry, self).__init__(*args, **kw)

    def _build(self, billy_db=db):
        '''Mutate the feed entry with hyperlinked entities. Add tagging
        data and other template context values, including source.
        '''
        self_legislator = self.legislator
        entity_types = {'L': 'legislator',
                        'C': 'committee',
                        'B': 'bill'}
        entry = self

        summary = truncatewords(entry['summary'], 50)
        entity_strings = entry['entity_strings']
        entity_ids = entry['entity_ids']

        _entity_strings = []
        _entity_ids = []
        _entity_urls = []
        _done = []
        if entity_strings:
            data = zip(entity_strings, entity_ids)
            data = sorted(data, key=lambda t: len(t[0]), reverse=True)
            hyperlinked_spans = []
            for entity_string, _id in data:
                if entity_string in _done:
                    continue
                else:
                    _done.append(entity_string)
                    _entity_strings.append(entity_string)
                    _entity_ids.append(_id)

                # Get this entity's url.
                collection_name = entity_types[_id[2]] + 's'
                collection = getattr(billy_db, collection_name)
                instance = collection.find_one(_id)
                url = instance.get_absolute_url()
                _entity_urls.append(url)

                # This is tricky. Need to hyperlink the entity without mangling
                # other previously hyperlinked strings, like Fiona Ma and
                # Mark Leno.
                matches = re.finditer(entity_string, summary)
                if _id != self_legislator.id:
                    # For other entities, add a hyperlink.
                    replacer = lambda m: '<a href="%s">%s</a>' % (url, entity_string)
                else:
                    # If this id refers to the related legislator, bold it.
                    replacer = lambda m: '<strong>%s</strong>' % (entity_string)

                for match in matches:

                    # Only hyperlink if no previous hyperlink has been added
                    # in the same span.
                    if any((start <= n < stop) for n in match.span()
                           for (start, stop) in hyperlinked_spans):
                        continue

                    summary = re.sub(entity_string, replacer, summary)
                    hyperlinked_spans.append(match.span())

            # For entity_strings, us modelinstance.display_name strings.
            _entity_display_names = []
            for _id in _entity_ids:
                collection_name = entity_types[_id[2]] + 's'
                collection = getattr(billy_db, collection_name)
                instance = collection.find_one(_id)
                string = instance.display_name()
                _entity_display_names.append(string)

            entity_data = zip(_entity_strings, _entity_display_names,
                              _entity_ids, _entity_urls)

            _entity_data = []
            seen_display_names = []
            for string, display_name, _id, url in entity_data:
                if display_name not in seen_display_names:
                    _entity_data.append((string, display_name, _id, url))
                    seen_display_names.append(display_name)

            entry['summary'] = summary
            entry['entity_data'] = _entity_data

        entry['id'] = entry['_id']
        urldata = urlparse.urlparse(entry['link'])
        entry['source'] = urldata.scheme + urldata.netloc
        entry['host'] = urldata.netloc

        # Prevent obfuscation of `published` method in template rendering.
        del entry['published']

    def display(self):
        self._build()
        return self['summary']

    def published(self):
        return datetime.datetime.fromtimestamp(self['published_parsed'])

    @property
    def metadata(self):
        return Metadata.get_object(self['state'])
