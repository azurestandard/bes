"""
Log events to Elastic Search via bulk upload
"""

import datetime as _datetime
import json as _json
import logging as _logging
import socket as _socket


__version__ = '0.1'

LOG = _logging.getLogger(__name__)


DEFAULT = {
    'host': 'localhost',
    'port': 9700,
    'protocol': 'UDP',
    'index': 'log',
    'datestamp_index': False,
    }


class Connection(object):
    """A socket connecting to Elastic Search

    Use a context manager for PEP 343's 'with' syntax:

    >>> with Connection(host='localhost', port=1234) as c:
    ...     c.send(message='hello!')
    """
    def __init__(self, host=None, port=None, protocol=None):
        if host is None:
            host = DEFAULT['host']
        if port is None:
            port = DEFAULT['port']
        if protocol is None:
            protocol = DEFAULT['protocol']
        self.host = host
        self.port = port
        if protocol == 'UDP':
            self.socket_type = _socket.SOCK_DGRAM
        else:
            raise NotImplementedError(protocol)
        self._sock = None

    def __enter__(self):
        self._sock = _socket.socket(_socket.AF_INET, self.socket_type)
        return self

    def __exit__(self, *exc_info):
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def send(self, message):
        LOG.debug(message)
        self._sock.sendto(message, (self.host, self.port))


def log(type, index=None, sort_keys=False, **kwargs):
    """Log an arbitrary payload dictionary to Elastic Search

    Uses the default connection configuration.  If you need to
    override any of them, build your payload dict by hand and use
    emit() instead.

    The type of message is required it is sent to ElasticSearch as the
    message type. Fields within a type should be of a consistent data
    type, though it is acceptible to add additional fields.

    You can optionally override the index of payload, for later
    filtering in Elastic Search.  This means that `index` is not
    available as payload key.

    """
    # @timestamp and @version to match Logstash's messsage format
    # https://logstash.jira.com/browse/LOGSTASH-675
    # Kibana automatically recognizes @timestamp
    kwargs['@timestamp'] = _datetime.datetime.utcnow().isoformat()
    kwargs['@version'] = 1
    return emit(type=type, payload=kwargs, index=index, sort_keys=sort_keys)


def emit(type, payload, index=None, datestamp_index=None, 
         sort_keys=False, connection_class=Connection, **kwargs):
    """Send bulk-upload data to Elastic Search

    Uses the 'index' action to add or replace a document as necessary.

    http://www.elasticsearch.org/guide/reference/api/bulk/
    http://www.elasticsearch.org/guide/reference/api/bulk-udp/
    """
    if index is None:
        index = DEFAULT['index']
    if datestamp_index is None:
        datestamp_index = DEFAULT['datestamp_index']
    if datestamp_index:
        index = '-'.join([
            index,
            _datetime.date.today().strftime('%Y.%m.%d'),
            ])

    index_data = {
        'index': {
            '_index': index,
            '_type': type,
            },
        }
    message = '\n'.join([
        _json.dumps(index_data, sort_keys=sort_keys),
        _json.dumps(payload, sort_keys=sort_keys),
        '',
        ])

    if hasattr(message, 'encode'):
        message = message.encode('utf-8')  # convert str to bytes for Python 3

    with connection_class(**kwargs) as connection:
        connection.send(message)

    return message
