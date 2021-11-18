"""
Kypher backend support for the KGTK browser.
"""

import datetime
import hashlib
from http import HTTPStatus
import math
import os
import os.path
import random
import sys
import traceback
import typing
import urllib.parse

import re
import flask
import pandas as pd
from collections import defaultdict
import browser.backend.kypher as kybe

from kgtk.kgtkformat import KgtkFormat
from kgtk.value.kgtkvalue import KgtkValue, KgtkValueFields

# map moral foundation Qnode ids to labels
scores_mapping = {
    'Q00_authorityvice': 'authority/vice',
    'Q00_authorityvirtue': 'authority/virtue',
    'Q00_fairnessvice': 'fairness/vice',
    'Q00_fairnessvirtue': 'fairness/virtue',
    'Q00_harmvice': 'harm/vice',
    'Q00_harmvirtue': 'harm/virtue',
    'Q00_ingroupvice': 'ingroup/vice',
    'Q00_ingroupvirtue': 'ingroup/virtue',
    'Q00_purityvice': 'purity/vice',
    'Q00_purityvirtue': 'purity/virtue',
    'Q00_concreteness': 'concreteness',
}

# How to run for local-system access:
# > export FLASK_APP=kgtk_browser_app.py
# > export FLASK_ENV=development
# > export KGTK_BROWSER_CONFIG=$PWD/kgtk_browser_config.py
# > flask run

# Example URLs for local server access:
# http://127.0.0.1:5000/kgtk/browser/backend/get_all_node_data?node=Q5
# http://127.0.0.1:5000/kgtk/kb
# http://127.0.0.1:5000/kgtk/kb/Q42

# How to run as a more general server (but please use nginx for
# deployment)::
# > export FLASK_APP=kgtk_browser_app.py
# > export FLASK_ENV=development
# > export KGTK_BROWSER_CONFIG=$PWD/kgtk_browser_config.py
# > flask run --host 0.0.0.0 --port 1234

# Example URL for named server access:
# http://ckg07.isi.edu:1234/kgtk/browser/backend/get_all_node_data?node=Q5
# http://ckg07.isi.edu:1234/kb
# http://ckg07.isi.edu:1234/kb/Q42


### Flask application

app = flask.Flask(__name__,
                  static_url_path='/browser',
                  static_folder='app/build',
                  template_folder='web/templates')
app.config.from_envvar('KGTK_BROWSER_CONFIG')

# Allow urls with trailing slashes
app.url_map.strict_slashes = False

DEFAULT_SERVICE_PREFIX = '/kgtk/'
DEFAULT_LANGUAGE = 'en'
ID_SEARCH_THRESHOLD: int = 40
ID_SEARCH_USING_IN: bool = False

DEFAULT_MATCH_ITEM_EXACTLY: bool = True
DEFAULT_MATCH_ITEM_PREFIXES: bool = True
DEFAULT_MATCH_ITEM_PREFIXES_LIMIT: int = 20
DEFAULT_MATCH_ITEM_IGNORE_CASE: bool = True

DEFAULT_MATCH_LABEL_EXACTLY: bool = True
DEFAULT_MATCH_LABEL_PREFIXES: bool = True
DEFAULT_MATCH_LABEL_PREFIXES_LIMIT: int = 20
DEFAULT_MATCH_LABEL_IGNORE_CASE: bool = True

DEFAULT_PROPLIST_MAX_LEN: int = 2000
DEFAULT_VALUELIST_MAX_LEN: int = 20
DEFAULT_QUAL_PROPLIST_MAX_LEN: int = 50
DEFAULT_QUAL_VALUELIST_MAX_LEN: int = 20
DEFAULT_QUERY_LIMIT: int = 300000
DEFAULT_QUAL_QUERY_LIMIT: int = 300000
DEFAULT_VERBOSE: bool = False


# List the properties in the order that you want them to appear.  All unlisted
# properties will appear after these.
rb_property_priority_list: typing.List[str] = [
    "P31", # instance of
    "P279", # subclass of
    "P21", # sex or gender
    "P2561*", # name
    "P138", # named after
    "P580*", # start time
    "P582*", # end time
    "P509", # cause of death
    "P1196", # manner of death
    "P20", # place of death
    "P1038*", # relative
    "P3342*", # significant person
]

rb_qualifier_priority_list: typing.List[str] = [
    "P585", # point in time
    "P580", # start time
    "P582", # end time
]

app.config['SERVICE_PREFIX'] = app.config.get('SERVICE_PREFIX', DEFAULT_SERVICE_PREFIX)
app.config['DEFAULT_LANGUAGE'] = app.config.get('DEFAULT_LANGUAGE', DEFAULT_LANGUAGE)

app.config['MATCH_ITEM_EXACTLY'] = app.config.get('MATCH_ITEM_EXACTLY', DEFAULT_MATCH_ITEM_EXACTLY)
app.config['MATCH_ITEM_PREFIXES'] = app.config.get('MATCH_ITEM_PREFIXES', DEFAULT_MATCH_ITEM_PREFIXES)
app.config['MATCH_ITEM_PREFIXES_LIMIT'] = app.config.get('MATCH_ITEM_PREFIXES_LIMIT', DEFAULT_MATCH_ITEM_PREFIXES_LIMIT)
app.config['MATCH_ITEM_IGNORE_CASE'] = app.config.get('MATCH_ITEM_IGNORE_CSE', DEFAULT_MATCH_ITEM_IGNORE_CASE)

app.config['MATCH_LABEL_EXACTLY'] = app.config.get('MATCH_LABEL_EXACTLY', DEFAULT_MATCH_LABEL_EXACTLY)
app.config['MATCH_LABEL_PREFIXES'] = app.config.get('MATCH_LABEL_PREFIXES', DEFAULT_MATCH_LABEL_PREFIXES)
app.config['MATCH_LABEL_PREFIXES_LIMIT'] = app.config.get('MATCH_LABEL_PREFIXES_LIMIT', DEFAULT_MATCH_LABEL_PREFIXES_LIMIT)
app.config['MATCH_LABEL_IGNORE_CASE'] = app.config.get('MATCH_LABEL_IGNORE_CASE', DEFAULT_MATCH_LABEL_IGNORE_CASE)

app.config['PROPLIST_MAX_LEN'] = app.config.get('PROPLIST_MAX_LEN', DEFAULT_PROPLIST_MAX_LEN)
app.config['VALUELIST_MAX_LEN'] = app.config.get('VALUELIST_MAX_LEN', DEFAULT_VALUELIST_MAX_LEN)
app.config['QUAL_PROPLIST_MAX_LEN'] = app.config.get('QUAL_PROPLIST_MAX_LEN', DEFAULT_QUAL_PROPLIST_MAX_LEN)
app.config['QUAL_VALUELIST_MAX_LEN'] = app.config.get('QUAL_VALUELIST_MAX_LEN', DEFAULT_QUAL_VALUELIST_MAX_LEN)
app.config['QUERY_LIMIT'] = app.config.get('QUERY_LIMIT', DEFAULT_QUERY_LIMIT)
app.config['QUAL_QUERY_LIMIT'] = app.config.get('QUAL_QUERY_LIMIT', DEFAULT_QUAL_QUERY_LIMIT)
app.config['VERBOSE'] = app.config.get('VERBOSE', DEFAULT_VERBOSE)

app.kgtk_backend = kybe.BrowserBackend(app)

def get_backend(app):
    return app.kgtk_backend


### Multi-threading

# Proper locking is now supported by the backend like this:

"""
with get_backend(app) as backend:
    edges = backend.get_node_edges(node)
    ...
"""


@app.route('/kb/info', methods=['GET'])
def get_info():
    """
    Returns project configuration information
    """
    info = {
        'graph_id': app.config.get('GRAPH_ID'),
        'version': app.config.get('VERSION'),
    }
    return flask.jsonify(info), 200


@app.route('/browser', methods=['GET'])
@app.route('/browser/<string:node>', methods=['GET'])
def rb_get_kb(node=None):
    """This is the basic entrypoint for starting the KGTK browser.
       It sends the initial HTML file, "kb.html".
    """
    return flask.send_from_directory('app/build', 'index.html')

def rb_is_true(value: str)->bool:
    """String to bool conversion function for use with args.get(...).
    """
    return value.lower() == "true"

def rb_sort_query_results(results: typing.List[typing.List[str]])->typing.List[typing.List[str]]:
    """If the database holds a large number of candidate matches and we want to
    limit the number of returned matches, there may be a performance problem
    because the database will first collect all candidate metches, then sort,
    then limit.

    Instead, we ask the database for unordered results.  We'll sort them ourselves.

    Since we're sorting the results ourselves, let's assume that item names
    take the form "[PQ]\d+".  We'd like to sort Q42 before Q102.  This also
    has the beneficial side-effect of putting most-wanted search results
    first, assuming that most-wanted results have a lower Q or P number.

    Note: We assume that each item name appears at most once in the results.

    TODO: Generalize this to allow any alpha+ digit+ sequence, and fallback to
    an alpha sort when the pattern fails.

    TODO: Add a parameter to the query that controls whether or not the
    results are sorted in this fancy way.

    """
    # Optimize the common cases of empty or singleton results:
    if len(results) <= 1:
        return results

    result_map: typing.MutableMapping[str, typing.List[str]] = dict()

    # Determine the maximum number of digits per item name in the results:
    maxdigits: int = 0
    result: typing.List[str]
    for result in results:
        digits: str = result[0][1:]
        if len(digits) > maxdigits:
            maxdigits = len(digits)

    # Build a map from the zero-filled item name to each result pair:
    for result in results:
        item: str = result[0]
        label: str = result[1]
        key: str = item[0] + item[1:].zfill(maxdigits)
        result_map[key] = result

    # Sort and return the results.
    sorted_results: typing.List[typing.List[str]] = list()
    key: str
    for key in sorted(result_map.keys()):
        sorted_results.append(result_map[key])
    return sorted_results


@app.route('/kb/query', methods=['GET'])
def rb_get_kb_query():
    """This API is used to generate lists of items (Qnodes od Pnodes) that
    match a query string.  Depending upon the parameter settings, the search
    string may make an exact and/or prefix match against an item name
    (P#### or Q####) or an item label (e.g., "Douglas Adams").

    Parameter Usage
    ========= ==================================================================================
    q         this is the search string, e.g. "Q42" or "Douglas Adams"

    verbose   This debugging parameter controls debugging output on the server.  The default is False.

    lang      This controls the language code of matching labels.  The default is "en",

    match_item_exactly This controls whether or not to perform an exact-length item match.
                       Item names are assumed to be stored in upper-case in the database.
                       The default is True.
                       Example: http://kgtk.isi.edu/kb/query/q=Q42&match_item_exactly=True

    match_item_prefixes This controls whether or not to return item prefix matches.
                        Item names are assumed to be stored in upper-case in the database.
                        Prefix matching is slower than exact matching.
                       The default is True.

    match_item_prefixes_limit Limit the number of item prefix match results that will
                              be presented.

    match_item_ignore_case When true, ignore case when matching labels.  This applies
                           to both exact-length item searches and item prefix searches.
                           The default is True.

    match_label_exactly This controls whether or not to perform an exact-length label match.
                        Labels are assumed to be stored in mixed case in the database. The
                        "match_label_ignore_case" parameter(see below) determines whether
                        the match is case sensitive or case insensitive.
                        The default is True.
                        Example: kttp:/kgtk.isi.edu//kb/query/q=Douglas Adams&match_label_exactly=True

    match_label_prefixes This controls whether or not to return label prefix matches.
                        Prefix matching is slower than exact matching.
                        Labels are assumed to be stored in mixed case in the database. The
                        "match_label_ignore_case" parameter(see below) determines whether
                        the match is case sensitive or case insensitive.
                        The default is True.

    match_label_prefixes_limit Limit the number of label prefix match results that will
                               be presented.

    match_label_ignore_case When true, ignore case when matching labels.  This applies
                            to both exact-length label searches and label prefix searches.
                            The default is True.

    The result returned is:

    [
        {
            "ref: "QNODE",
            "text"; "QNODE",
            "description": "LABEL"
        } ,
        ...
    ]

    where QNODE is the Q### or P### item identifier and LABEL is the
    label value corresponding to that identifier.

    "ref": "QNODE" This provides the identifier used to retrieve the
                   full details of an item using:
                   http://hostname/kb/item?q=QNODE

    "text": "QNODE" This provides the identifier that is displayed to
                    the user.

    "description": "LABEL" This provides the descriptive text for the item.
                           The KGTK browser server currently sends the items's
                           label as a description.  This response should be short
                           as it will probably be used to generate a pop-up/pull-down menu.
    """
    args = flask.request.args
    q = args.get('q')

    verbose: bool = args.get("verbose", default=app.config['VERBOSE'], type=rb_is_true)
    if verbose:
        print("rb_get_kb_query: " + q)

    lang: str = args.get("lang", app.config['DEFAULT_LANGUAGE'])

    match_item_exactly: bool = args.get("match_item_exactly", type=rb_is_true,
                                        default=app.config['MATCH_ITEM_EXACTLY'])
    match_item_prefixes: bool = args.get("match_item_prefixes", type=rb_is_true,
                                         default=app.config['MATCH_ITEM_PREFIXES'])
    match_item_prefixes_limit: int = args.get("match_item_prefixes_limit", type=int,
                                              default=app.config['MATCH_ITEM_PREFIXES_LIMIT'])
    match_item_ignore_case: bool = args.get("match_item_ignore_case", type=rb_is_true,
                                            default=app.config['MATCH_ITEM_IGNORE_CASE'])

    match_label_exactly: bool = args.get("match_label_exactly", type=rb_is_true,
                                         default=app.config['MATCH_LABEL_EXACTLY'])
    match_label_prefixes: bool = args.get("match_label_prefixes", type=rb_is_true,
                                          default=app.config['MATCH_LABEL_PREFIXES'])
    match_label_prefixes_limit: int = args.get("match_label_prefixes_limit", type=int,
                                               default=int(os.environ.get("KGTK_BROWSER_MATCH_LABEL_PREFIXES_LIMIT", "20")))
    match_label_ignore_case: bool = args.get("match_label_ignore_case", type=rb_is_true,
                                             default=app.config['MATCH_LABEL_IGNORE_CASE'])

    try:
        with get_backend(app) as backend:
            matches = [ ]

            # We keep track of the matches we've seen and produce only one match per node.
            items_seen: typing.Set[str] = set()

            # We will look for matches in the following order.  Each
            # match category may be discabled by a parameter.
            #
            # 1) exact length match on the node name
            # 2) exact length match on the label
            # 3) prefix match (startswith) on the node name
            # 4) prefix match on the label
            #
            # node name matches are always case-insensitive, because we know that
            # node names in the database are upper-case, and we raise the case
            # of the q parameter in the search routine.
            #
            # Label matches may be case-sensitive or case-insensitive,
            # according to "match_label_ignore_case".

            if match_item_exactly:
                # We don't explicitly limit the number of results from this
                # query.  Should we?  The underlying code imposes a default
                # limit, currently 1000.
                if verbose:
                    print("Searching for node %s" % repr(q), file=sys.stderr, flush=True)
                # Look for an exact match for the node name:
                results = backend.rb_get_node_labels(q,
                                                     lang=lang,
                                                     ignore_case=match_item_ignore_case)
                if verbose:
                    print("Got %d matches" % len(results), file=sys.stderr, flush=True)
                for result in rb_sort_query_results(results):
                    item = result[0]
                    if item in items_seen:
                        continue
                    items_seen.add(item)
                    label = KgtkFormat.unstringify(result[1])
                    matches.append(
                        {
                            "ref": item,
                            "text": item,
                            "description": label
                        }
                    )

            if match_label_exactly:
                # Query the labels, looking for an exact length match. The
                # search may be case-sensitive or case-insensitive, according
                # to "match_label_ignore_case".
                #
                # We don't explicitly limit the number of results from this
                # query.  Should we?  The underlying code imposes a default
                # limit, currently 1000.

                # The simple approach, using stringify, will not work when
                # "lang" is "any"!  We will have to do a prefix match
                # including the initial and final "'" delimiters, but
                # excluding the "@lang" suffix.
                if lang == "any":
                    # Labels are assumed to be encoded as language-qualified
                    # strings in the database.  We want to do a match that excludes the
                    # language encoding, to support lang=="any", so
                    # we stringify to a plain string and replace the leading and trailing '"' with
                    # "'".
                    #
                    # TODO: create a KgtkFormat method for this this transformation.
                    prefix: str = "'" + KgtkFormat.stringify(q)[1:-1] + "'"
                    if verbose:
                        print("Searching for label %s (ignore_case=%s)" % (repr(prefix), repr(match_label_ignore_case)), file=sys.stderr, flush=True)
                    results = backend.rb_get_nodes_with_labels_starting_with(prefix,
                                                                             lang=lang,
                                                                             ignore_case=match_label_ignore_case,
                                                                             limit=match_label_prefixes_limit)
                else:
                    # Labels are assumed to be encoded as language-qualified
                    # strings in the database.  We want to do an exact match, so
                    # we stringify.
                    l: str = KgtkFormat.stringify(q, language=lang)
                    if verbose:
                        print("Searching for label %s (ignore_case=%s)" % (repr(l), repr(match_label_ignore_case)), file=sys.stderr, flush=True)
                    results = backend.rb_get_nodes_with_label(l,
                                                              lang=lang,
                                                              ignore_case=match_label_ignore_case)
                if verbose:
                    print("Got %d matches" % len(results), file=sys.stderr, flush=True)

                for result in rb_sort_query_results(results):
                    item = result[0]
                    if item in items_seen:
                        continue
                    items_seen.add(item)
                    label = KgtkFormat.unstringify(result[1])
                    matches.append(
                        {
                            "ref": item,
                            "text": item,
                            "description": label
                        }
                    )

            if match_item_prefixes:
                if verbose:
                    print("Searching for node prefix %s" % repr(q), file=sys.stderr, flush=True)
                results = backend.rb_get_nodes_starting_with(q,
                                                             lang=lang,
                                                             limit=match_item_prefixes_limit,
                                                             ignore_case=match_item_ignore_case)
                if verbose:
                    print("Got %d matches" % len(results), file=sys.stderr, flush=True)
                for result in rb_sort_query_results(results):
                    item = result[0]
                    if item in items_seen:
                        continue
                    items_seen.add(item)
                    label = KgtkFormat.unstringify(result[1])
                    matches.append(
                        {
                            "ref": item,
                            "text": item,
                            "description": label
                        }
                    )

            if match_label_prefixes:
                # Query the labels, looking for a prefix match. The search may
                # be case-sensitive or case-insensitive, according to
                # "match_label_ignore_case".
                #
                # Labels are assumed to be encoded as language-qualified
                # strings in the database.  We want to do a prefix match, so
                # we stringify to a plain string, replace the leading '"' with
                # "'", and remove the trailing '"'
                #
                # TODO: create a KgtkFormat method for this this transformation.
                prefix: str = "'" + KgtkFormat.stringify(q)[1:-1]
                if verbose:
                    print("Searching for label prefix %s (ignore_case=%s)" % (repr(prefix), repr(match_label_ignore_case)), file=sys.stderr, flush=True)
                results = backend.rb_get_nodes_with_labels_starting_with(prefix,
                                                                         lang=lang,
                                                                         ignore_case=match_label_ignore_case,
                                                                         limit=match_label_prefixes_limit)
                if verbose:
                    print("Got %d matches" % len(results), file=sys.stderr, flush=True)
                for result in rb_sort_query_results(results):
                    item = result[0]
                    if item in items_seen:
                        continue
                    items_seen.add(item)
                    label = KgtkFormat.unstringify(result[1])
                    matches.append(
                        {
                            "ref": item,
                            "text": item,
                            "description": label
                        }
                    )

            if verbose:
                print("Got %d matches total" % len(matches), file=sys.stderr, flush=True)

            # Build the final response:
            response_data = {
                "matches": matches
            }

            return flask.jsonify(response_data), 200
    except Exception as e:
        print('ERROR: ' + str(e))
        flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)


def rb_link_to_url(text_value, current_value, lang: str = "en", prop: typing.Optional[str] = None)->bool:
    if text_value is None:
        return False

    # Look for text strings that are URLs:
    if text_value.startswith(("https://", "http://")):
        # print("url spotted: %s" % repr(text_value)) # ***
        current_value["url"] = text_value
        return True

    elif text_value.endswith((".jpg", ".svg")):
        image_url: str = "https://commons.wikimedia.org/wiki/File:"  + text_value
        # print("image spotted: %s" % repr(image_url)) # ***
        current_value["url"] = image_url
        return True
    return False

def rb_unstringify(item: str, default: str = "")->str:
    return KgtkFormat.unstringify(item) if item is not None and len(item) > 0 else default

rb_image_formatter_cache: typing.MutableMapping[str, typing.Optional[str]] = dict()

def get_image_formatter(backend, relationship: str)->typing.Optional[str]:
    if relationship not in rb_image_formatter_cache:
        result: typing.List[typing.List[str]] = backend.rb_get_image_formatter(relationship)
        if len(result) == 0:
            rb_image_formatter_cache[relationship] = None
        else:
            rb_image_formatter_cache[relationship] = rb_unstringify(result[0][0])
    return rb_image_formatter_cache[relationship]

rb_units_node_cache: typing.MutableMapping[str, typing.Optional[str]] = dict()

def rb_format_number_or_quantity(
        backend,
        target_node: str,
        value: KgtkValue,
        datatype: str,
        lang: str,
)->typing.Tuple[str, str, str]:
    number_value: str
    number_units: typing.Optional[str] = None
    number_ref: typing.Optional[str] = None

    if datatype == KgtkFormat.DataType.NUMBER:
        numberstr: str = target_node
        if numberstr.startswith("+"): # Remove any leading "+"
            number_value = numberstr[1:]
        else:
            number_value = numberstr
    else:
        if value.do_parse_fields():
            newnum: str = value.fields.numberstr
            if newnum.startswith("+"): # Remove any leading "+"
                newnum = newnum[1:]
            if value.fields.low_tolerancestr is not None or value.fields.high_tolerancestr is not None:
                newnum += "["
                if value.fields.low_tolerancestr is not None:
                    lowtolstr: str = value.fields.low_tolerancestr
                    if lowtolstr.startswith("+"):
                        lowtolstr = lowtolstr[1:]
                    newnum += lowtolstr
                newnum += ","
                if value.fields.high_tolerancestr is not None:
                    hitolstr: str = value.fields.high_tolerancestr
                    if hitolstr.startswith("+"):
                        hitolstr = hitolstr[1:]
                    newnum += hitolstr
                newnum += "]"

            if value.fields.si_units is not None:
                # TODO: supply a node reference for each SI unit.
                number_units = value.fields.si_units

            elif value.fields.units_node is not None:
                # Here's where it gets fancy:
                units_node: str = value.fields.units_node
                if units_node not in rb_units_node_cache:
                    units_node_labels: typing.List[typing.List[str]] = backend.get_node_labels(units_node, lang=lang)
                    if len(units_node_labels) > 0:
                        units_node_label: str = units_node_labels[0][1]
                        rb_units_node_cache[units_node] = rb_unstringify(units_node_label)
                    else:
                        rb_units_node_cache[units_node] = None # Remember the failure.

                if rb_units_node_cache[units_node] is not None:
                    number_units = rb_units_node_cache[units_node]
                else:
                    number_units = units_node # We could not find a label for this node when we looked last time.
                number_ref = units_node

            number_value = newnum
        else:
            # Validation failed.
            #
            # TODO: Add a validation failure indicator?
            number_value = target_node

    return number_value, number_units, number_ref

def rb_iso_format_time(
        target_node: str,
        value: KgtkValue,
)->str:

    if value.do_parse_fields() and value.fields.precision is not None:
        f: KgtkValueFields = value.fields
        precision: int = f.precision
        if precision <= 9 and f.yearstr is not None:
            return f.yearstr
        elif precision == 10 and f.yearstr is not None and f.monthstr is not None:
            return f.yearstr + "-" + f.monthstr
        elif precision == 11 and f.yearstr is not None and f.monthstr is not None and f.daystr is not None:
            return f.yearstr + "-" + f.monthstr + "-" + f.daystr
        elif precision in (12, 13, 14) and f.yearstr is not None and f.monthstr is not None and f.daystr is not None and f.hourstr is not None and f.minutesstr is not None:
            return f.yearstr + "-" + f.monthstr + "-" + f.daystr + " " + f.hourstr + ":" + f.minutesstr
        else:
            return target_node[1:]
    else:
        # Validation failed.
        #
        # TODO: Add a validation failure indicator?
        return target_node[1:]

def rb_human_format_time(
        target_node: str,
        value: KgtkValue,
)->str:

    if value.do_parse_fields() and value.fields.precision is not None:
        f: KgtkValueFields = value.fields
        d: datetime = datetime.datetime(f.year, f.month, f.day, f.hour, f.minutes, f.seconds)
        precision: int = f.precision
        if precision <= 9 and f.yearstr is not None:
            return f.yearstr
        elif precision == 10:
            return d.strftime("%B %Y")
        elif precision == 11:
            return d.strftime("%B %d, %Y")
        elif precision == 12:
            return d.strftime("%I %p, %B %d, %Y")
        elif precision == 13:
            return d.strftime("%I:%M %p, %B %d, %Y")
        else:
            return d.strftime("%I:%M:%S %p, %B %d, %Y")

    else:
        # Validation failed.
        #
        # TODO: Add a validation failure indicator?
        return target_node[1:]

def rb_format_time(
        target_node: str,
        value: KgtkValue,
        use_iso_format: bool = False,
)->str:
    if use_iso_format:
        return rb_iso_format_time(target_node, value)
    else:
        return rb_human_format_time(target_node, value)

def rb_dd_to_dms(degs: float)->typing.Tuple[bool, int, int, float]:
    # Taken from: https://stackoverflow.com/questions/2579535/convert-dd-decimal-degrees-to-dms-degrees-minutes-seconds-in-python
    neg: bool = degs < 0
    if neg:
        degs = - degs
    d_int: int
    degs, d_int = math.modf(degs)
    m_int: int
    mins, m_int = math.modf(60 * degs)
    secs: float =           60 * mins
    return neg, d_int, m_int, secs

def rm_format_dms(degs: float,
                  is_lat: bool)->str:

    neg: bool
    d_int: int
    m_int: int
    secs: float
    neg, d_int, m_int, secs = rb_dd_to_dms(degs)
    degree_sign = u"\N{DEGREE SIGN}"
    if is_lat:
        letter: str = "W" if neg else "E"
        return "%3d%s%2d\"%2.5f'%s" % (d_int, degree_sign, m_int, secs, letter)
    else:
        letter: str = "S" if neg else "N"
        return "%2d%s%2d\"%2.5f'%s" % (d_int, degree_sign, m_int, secs, letter)

def rb_format_geo(latlon: str,
                  use_decimal_format: bool = False,
)->str:
    if use_decimal_format:
        return latlon

    ddlatstr: str
    ddlonstr: str
    ddlatstr, ddlonstr = latlon.split("/")
    return rm_format_dms(float(ddlatstr), is_lat=True) + ", " + rm_format_dms(float(ddlonstr), is_lat=False)


rb_language_name_cache: typing.MutableMapping[str, typing.Optional[str]] = dict()

def rb_get_language_name(backend,
                         language: str,
                         language_suffix: typing.Optional[str],
                         lang: str,
                         show_code: bool = False,
                         verbose: bool = False)->str:
    """Get the language name for a language code.  If there is a language suffix, first look for the
    full language code before looking for the base code.

    If we find a language name:
        if show_code is true, return "<language_name> (<code>)".
        otherwise, return "<language_name>"
    Otherwise, return "<code>".
    """
    labels: typing.List[typing.List[str]]
    full_code: typing.Optional[str] = None
    name: str

    if language_suffix is not None and len(language_suffix) > 0:
        full_code = language + language_suffix
        if verbose:
            print("Looking up full language code %s" % repr(full_code), file=sys.stderr, flush=True)
        if full_code in rb_language_name_cache:
            name = rb_language_name_cache[full_code]
            if verbose:
                print("Found full code %s in cache: %s" % (repr(full_code), repr(name)), file=sys.stderr, flush=True)
            return name # show_code alread applied.

        labels = backend.rb_get_language_labels(KgtkFormat.stringify(full_code), lang=lang)
        if len(labels) > 0 and labels[0][1] is not None and len(labels[0][1]) > 0:
            name: str = KgtkFormat.unstringify(labels[0][1])
            if show_code:
                name += " (" + full_code + ")"
            if verbose:
                print("Found full code %s in database: %s" % (repr(full_code), repr(name)), file=sys.stderr, flush=True)

            # Remember the languge name with the optional code.
            rb_language_name_cache[full_code] = name
            return name

    short_code: str = language
    if verbose:
        print("Looking up short language code %s" % repr(short_code), file=sys.stderr, flush=True)
    if short_code in rb_language_name_cache:
        name = rb_language_name_cache[short_code]
        if verbose:
            print("Found short code %s in cache: %s" % (repr(short_code), repr(name)), file=sys.stderr, flush=True)
        if name == short_code:
            if full_code is not None:
                rb_language_name_cache[full_code] = full_code
                return full_code
            else:
                return short_code

        if show_code:
            if full_code is not None:
                name += " (" + full_code + ")"
            else:
                name += " (" + short_code + ")"

        if full_code is not None:
            # Speed up the next lookup.
            rb_language_name_cache[full_code] = name

        return name

    labels = backend.rb_get_language_labels(KgtkFormat.stringify(short_code), lang=lang)
    if len(labels) > 0 and labels[0][1] is not None and len(labels[0][1]) > 0:
        name = KgtkFormat.unstringify(labels[0][1])
        if verbose:
                print("Found short code %s in cache: %s" % (repr(short_code), repr(name)), file=sys.stderr, flush=True)
        # Remember the language name without the optional code:
        rb_language_name_cache[short_code] = name

        if show_code:
            if full_code is not None:
                name += " (" + full_code + ")"
            else:
                name += " (" + short_code + ")"

        if full_code is not None:
            # Speed up the next lookup.
            rb_language_name_cache[full_code] = name

        return name

    # Return the language code, full or short, without stringification.
    # Remember the lookup failure for speed.
    rb_language_name_cache[short_code] = short_code
    if full_code is not None and language_suffix is not None:
        rb_language_name_cache[full_code] = full_code
        if verbose:
            print("language name not found, using full code %s" % repr(full_code), file=sys.stderr, flush=True)
        return full_code
    else:
        if verbose:
            print("language name not found, using short code %s" % repr(short_code), file=sys.stderr, flush=True)
        return short_code

def rb_build_current_value(
        backend,
        target_node: str,
        value: KgtkValue,
        rb_type: str,
        target_node_label: typing.Optional[str],
        target_node_description: typing.Optional[str],
        lang: str,
        relationship: str = "",
        wikidatatype: str = ""
)->typing.Mapping[str, str]:

    current_value: typing.MutableMapping[str, any] = dict()
    datatype: KgtkFormat.DataType = value.classify()

    text_value: str

    if wikidatatype == "external-id":
        text_value = rb_unstringify(target_node)
        current_value["text"] = text_value
        formatter: typing.Optional[str] = get_image_formatter(backend, relationship)
        if formatter is not None:
            # print("formatter: %s" % formatter, file=sys.stderr, flush=True) # ***
            current_value["url"] = formatter.replace("$1", text_value)
        else:
            rb_link_to_url(text_value, current_value)

    elif rb_type == "/w/item":
        current_value["ref"] = target_node
        current_value["text"] = rb_unstringify(target_node_label, default=target_node)
        current_value["description"] = rb_unstringify(target_node_description)

    elif rb_type == "/w/text":
        language: str
        language_suffix: str
        text_value, language, language_suffix = KgtkFormat.destringify(target_node)
        current_value["text"] = text_value
        current_value["lang"] = rb_get_language_name(backend, language, language_suffix, lang)
        rb_link_to_url(text_value, current_value, lang=language)

    elif rb_type == "/w/string":
        text_value = rb_unstringify(target_node)
        current_value["text"] = text_value
        rb_link_to_url(text_value, current_value)

    elif rb_type == "/w/quantity":
        number_text: str
        number_ref: typing.Optional[str]
        number_value, number_units, number_ref = rb_format_number_or_quantity(backend, target_node, value, datatype, lang)
        current_value["text"] = number_value
        if number_units is not None:
            current_value["units"] = number_units
        if number_ref is not None:
            current_value["ref"] = number_ref

    elif rb_type == "/w/time":
        current_value["text"] = rb_format_time(target_node, value)

    elif rb_type == "/w/geo":
        geoloc = target_node[1:]
        current_value["text"] = rb_format_geo(geoloc)
        current_value["url"] = "http://maps.google.com/maps?q=" + geoloc.replace("/", ",")
    else:
        print("*** unknown rb_type %s" % repr(rb_type)) # ***

    return current_value

def rb_find_type(node2: str, value: KgtkValue)->str:
    datatype: KgtkFormat.DataType = value.classify()
    rb_type: str

    if datatype == KgtkFormat.DataType.SYMBOL:
        rb_type = "/w/item"

    elif datatype == KgtkFormat.DataType.LANGUAGE_QUALIFIED_STRING:
        rb_type = "/w/text"

    elif datatype == KgtkFormat.DataType.STRING:
        rb_type = "/w/string"

    elif datatype == KgtkFormat.DataType.QUANTITY:
        rb_type = "/w/quantity"

    elif datatype == KgtkFormat.DataType.NUMBER:
        rb_type = "/w/quantity"

    elif datatype == KgtkFormat.DataType.DATE_AND_TIMES:
        rb_type = "/w/time"

    elif datatype == KgtkFormat.DataType.LOCATION_COORDINATES:
        rb_type = "/w/geo"

    else:
        rb_type = "/w/unknown" # Includes EMPTY, LIST, EXTENSION, BOOLEAN
        print("*** unknown datatype") # ***def rb_send_kb_item(item: str):

    return rb_type

# The following routine was taken from Stack Overflow.
# https://stackoverflow.com/questions/33689980/get-thumbnail-image-from-wikimedia-commons
def rb_get_wc_thumb(image: str, width: int = 300): # image = e.g. from Wikidata, width in pixels
    image = image.replace(' ', '_') # need to replace spaces with underline
    m = hashlib.md5()
    m.update(image.encode('utf-8'))
    d: str = m.hexdigest()
    return "https://upload.wikimedia.org/wikipedia/commons/thumb/"+d[0]+'/'+d[0:2]+'/'+image+'/'+str(width)+'px-'+image

def rb_build_gallery(item_edges: typing.List[typing.List[str]],
                     item: str,
                     item_labels: typing.List[typing.List[str]])->typing.List[typing.Mapping[str, str]]:
    gallery: typing.List[typing.List[str]] = list()

    item_edge: typing.List[str]
    for item_edge in item_edges:
        edge_id: str
        node1: str
        relationship: str
        node2: str
        relationship_label: typing.Optional[str]
        target_node: str
        target_label: typing.Optional[str]
        target_description: typing.Optional[str]
        wikidatatype: typing.Optional[str]
        edge_id, node1, relationship, node2, relationship_label, target_node, target_label, target_description, wikidatatype = item_edge

        if relationship == "P18":
            value: KgtkValue = KgtkValue(node2)
            if value.is_string() or value.is_language_qualified_string():
                new_image: typing.Mapping[str, str] = {
                    "url": rb_get_wc_thumb(rb_unstringify(node2)),
                    "text": rb_unstringify(item_labels[0][1]) if len(item_labels) > 0 else item
                }
                # print("new image: %s" % repr(new_image), file=sys.stderr, flush=True)
                gallery.append(new_image)

    # print("gallery: %s" % repr(gallery), file=sys.stderr, flush=True)

    return gallery


rb_property_priority_map: typing.Optional[typing.Mapping[str, int]] = None

def rb_scan_property_list(initial_priority_map: typing.Mapping[str, int],
                          revised_priority_map: typing.MutableMapping[str, int],
                          properties_seen: typing.Set[str],
                          prop_list: typing.List[str],
                          forest: typing.Mapping[str, typing.List[str]],
                          labels: typing.Mapping[str, str]):
    prop_sort_map: typing.MutableMapping[str, str] = dict()
    key: str
    prop: str
    idx: int
    for idx, prop in enumerate(prop_list):
        if prop in properties_seen:
            continue
        properties_seen.add(prop)
        priority: str = str(initial_priority_map.get(prop, 99999)).zfill(5)
        label: str = labels.get(prop, prop)
        key = priority + "|" + label + "|" + str(idx).zfill(5)
        prop_sort_map[key] = prop

    for key in sorted(prop_sort_map.keys()):
        prop = prop_sort_map[key]
        revised_priority_map[prop] = len(revised_priority_map)
        if prop in forest:
            rb_scan_property_list(initial_priority_map, revised_priority_map, properties_seen, forest[prop], forest, labels)

def rb_build_property_priority_map(backend, verbose: bool = False):
    global rb_property_priority_map # Since we initialize it here.
    if rb_property_priority_map is not None:
        return # Already built.

    initial_priority_map: typing.MutableMapping[str, int] = dict()
    val: str
    for val in rb_property_priority_list:
        if val.endswith("*"):
            val = val[:-1]
        initial_priority_map[val] = len(initial_priority_map)
    if verbose:
        print("%d entries in the initial priority map" % len(initial_priority_map), file=sys.stderr, flush=True) # ***

    subproperty_relationships = backend.rb_get_subproperty_relationships()
    if verbose:
        print("%d subproperty relationships" % len(subproperty_relationships), file=sys.stderr, flush=True) # ***

    labels: typing.MutableMapping[str, str] = dict()
    forest: typing.MutableMapping[str, typing.List[str]] = dict()
    node1: str
    node2: str
    label: str
    rel: typing.List[str]
    for rel in subproperty_relationships:
        node1, node2, label = rel
        # print("%s (%s) is a subproperty of %s" % (repr(node1), repr(label), repr(node2)), file=sys.stderr, flush=True) # ***
        if node2 not in forest:
            forest[node2] = list()
        forest[node2].append(node1)
        labels[node1] = label
    if verbose:
        print("%d subproperty forest branches" % len(forest), file=sys.stderr, flush=True) # ***

    revised_priority_map: typing.MutableMapping[str, int] = dict()
    properties_seen: typing.Set[str] = set()

    prop: str
    for prop in rb_property_priority_list:
        if prop in properties_seen:
            continue
        properties_seen.add(prop)
        if prop.endswith("*"):
            prop = prop[:-1]
            revised_priority_map[prop] = len(revised_priority_map)
            if prop in forest:
                rb_scan_property_list(initial_priority_map, revised_priority_map, properties_seen, forest[prop], forest, labels)
        else:
            revised_priority_map[prop] = len(revised_priority_map)

    rb_property_priority_map = revised_priority_map
    if verbose:
        print("%d entries in the property priority map" % len(rb_property_priority_map), file=sys.stderr, flush=True) # ***


rb_property_priority_width = 5
rb_default_property_priority = int("1" + "0".zfill(rb_property_priority_width)) - 1

def rb_get_property_priority(relationship: str)->str:
    priority: int
    if rb_property_priority_map is None:
        priority = rb_default_property_priority
    else:
        priority = rb_property_priority_map.get(relationship, rb_default_property_priority)
    return str(priority).zfill(rb_property_priority_width)

def rb_build_keyed_item_edges(item_edges: typing.List[typing.List[str]])->typing.MutableMapping[str, typing.List[str]]:
    # Sort the item edges
    keyed_item_edges: typing.MutableMapping[str, typing.List[str]] = dict()

    idx: int
    item_edge: typing.List[str]
    for idx, item_edge in enumerate(item_edges):
        edge_id, node1, relationship, node2, relationship_label, target_node, target_label, target_description, wikidatatype = item_edge
        if relationship_label is None:
            relationship_label = relationship
        if target_label is None:
            target_label = target_node
        priority: str = rb_get_property_priority(relationship)
        item_edge_key: str = (priority + "|" + relationship_label + "|" + target_label + "|" + str(idx + 1000000)).lower()
        keyed_item_edges[item_edge_key] = item_edge
    return keyed_item_edges

def rb_build_sorted_item_edges(item_edges: typing.List[typing.List[str]])->typing.List[typing.List[str]]:
    # Sort the item edges:
    sorted_item_edges: typing.List[typing.List[str]] = list()

    keyed_item_edges: typing.MutableMapping[str, typing.List[str]] = rb_build_keyed_item_edges(item_edges)

    item_edge_key: str
    for item_edge_key in sorted(keyed_item_edges.keys()):
        sorted_item_edges.append(keyed_item_edges[item_edge_key])

    return sorted_item_edges

rb_qualifier_priority_map: typing.Mapping[str, int] = { val: idx for idx, val in enumerate(rb_qualifier_priority_list) }

def rb_build_item_qualifier_map(item_qualifier_edges: typing.List[typing.List[str]])->typing.Mapping[str, typing.List[typing.List[str]]]:
    item_qual_map: typing.MutableMapping[str, typing.List[typing.List[str]]] = dict()

    edge_id: str

    # Map the qualifiers onto the edges that they qualify.
    item_qual_edge: typing.List[str]
    for item_qual_edge in item_qualifier_edges:
        edge_id = item_qual_edge[0]
        if edge_id not in item_qual_map:
            item_qual_map[edge_id] = list()
        item_qual_map[edge_id].append(item_qual_edge)

    # Sort the qualifiers for each edge in alphabetical order by qualifier
    # label, then by value label.  If a qualifier has multiple values, it is
    # important that the values be adjacent to each other in the resulting
    # output.
    for edge_id in item_qual_map:
        keyed_edge_map: typing.MutableMapping[str, typing.List[typing.List[str]]] = dict()
        qual_relationship_key: str
        for item_qual_edge in item_qual_map[edge_id]:
            qual_relationship: str = item_qual_edge[3]
            qual_node2: str = item_qual_edge[4]
            qual_relationship_label: typing.Optional[str] = item_qual_edge[5]
            qual_node2_label: typing.Optional[str] = item_qual_edge[6]

            priority: str = rb_qualifier_priority_map.get(qual_relationship, 99999)
            prikey: str = str(priority + 100000)

            relkey: str = qual_relationship_label if qual_relationship_label is not None and len(qual_relationship_label) > 0 else qual_relationship
            n2key: str = qual_node2_label if qual_node2_label is not None and len(qual_node2_label) > 0 else qual_node2

            qual_relationship_key: str = prikey + "|" + relkey + "|" + n2key
            if qual_relationship_key not in keyed_edge_map:
                keyed_edge_map[qual_relationship_key] = list()
            keyed_edge_map[qual_relationship_key].append(item_qual_edge)

        sorted_item_qual_edges: typing.List[typing.List[str]] = list()
        for qual_relationship_key in sorted(keyed_edge_map.keys()):
            item_qual_edges: typing.List[typing.List[str]] = keyed_edge_map[qual_relationship_key]
            sorted_item_qual_edges.extend(item_qual_edges)
        item_qual_map[edge_id] = sorted_item_qual_edges

    return item_qual_map

def rb_render_item_qualifiers(backend,
                              item: str,
                              edge_id: str,
                              item_qualifier_edges: typing.List[typing.List[str]],
                              qual_proplist_max_len: int,
                              qual_valuelist_max_len: int,
                              lang: str,
                              verbose: bool)->typing.List[typing.MutableMapping[str, any]]:
    current_qual_edge_id: typing.Optional[str] = None
    current_qual_relationship: typing.Optional[str] = None
    current_qualifiers: typing.List[typing.MutableMapping[str, any]] = list()

    for item_qual_edge in item_qualifier_edges:
        if verbose:
            print(repr(item_qual_edge), file=sys.stderr, flush=True)

        qual_edge_id: str
        qual_relationship: str
        qual_node2: str
        qual_relationship_label: typing.Optional[str]
        qual_node2_label: typing.Optional[str]
        qual_node2_description: typing.Optional[str]
        _, _, qual_edge_id, qual_relationship, qual_node2, qual_relationship_label, qual_node2_label, qual_node2_description = item_qual_edge

        if current_qual_edge_id is not None and current_qual_edge_id == qual_edge_id:
            if verbose:
                print("*** skipping duplicate qualifier %s" % repr(current_qual_edge_id), file=sys.stderr, flush=True)
            # Skip duplicates (say, multiple labels or descriptions).
            continue
        current_qual_edge_id = qual_edge_id

        qual_value: KgtkValue = KgtkValue(qual_node2)
        qual_rb_type: str = rb_find_type(qual_node2, qual_value)

        if current_qual_relationship is None or qual_relationship != current_qual_relationship:
            # We are starting a new qualifier. Create the entry for the
            # qualifier, and start building the qualifier's list of values.
            current_qual_relationship = qual_relationship
            current_qual_values = list()
            current_qual_property_map: typing.MutableMapping[str, any] = {
                "ref": qual_relationship,
                "property": rb_unstringify(qual_relationship_label, default=qual_relationship),
                "type": qual_rb_type, # TODO: check for consistency
                "values": current_qual_values
            }
            current_qualifiers.append(current_qual_property_map)

        current_qual_value: typing.MutableMapping[str, any] = rb_build_current_value(backend,
                                                                                     qual_node2,
                                                                                     qual_value,
                                                                                     qual_rb_type,
                                                                                     qual_node2_label,
                                                                                     qual_node2_description,
                                                                                     lang)
        current_qual_values.append(current_qual_value)

    downsample_properties(current_qualifiers, qual_proplist_max_len, qual_valuelist_max_len, repr(item) + " edge " + repr(edge_id), verbose)

    return current_qualifiers

def rb_render_kb_items(backend,
                       item: str,
                       item_edges: typing.List[typing.List[str]],
                       proplist_max_len: int = 0,
                       valuelist_max_len: int = 0,
                       lang: str = 'en',
                       verbose: bool = False)->typing.Tuple[typing.List[typing.MutableMapping[str, any]],
                                                            typing.List[typing.MutableMapping[str, any]]]:

    response_properties: typing.List[typing.MutableMapping[str, any]] = list()
    response_xrefs: typing.List[typing.MutableMapping[str, any]] = list()

    # current_edge_id: typing.Optional[str] = None
    current_relationship: typing.Optional[str] = None
    current_values: typing.List[typing.MutableMapping[str, any]] = list()

    value_drop_count: int = 0

    item_edge: typing.List[str]
    for item_edge in item_edges:
        if verbose:
            print(repr(item_edge), file=sys.stderr, flush=True)

        edge_id: str
        node1: str
        relationship: str
        node2: str
        relationship_label: typing.Optional[str]
        target_node: str
        target_label: typing.Optional[str]
        target_description: typing.Optional[str]
        wikidatatype: typing.Optional[str]
        edge_id, node1, relationship, node2, relationship_label, target_node, target_label, target_description, wikidatatype = item_edge

        # if current_edge_id is not None and current_edge_id == edge_id:
        #     if verbose:
        #         print("*** skipping duplicate %s" % repr(current_edge_id), file=sys.stderr, flush=True)
        #     # Skip duplicates (say, multiple labels or descriptions).
        #     continue
        # current_edge_id = edge_id

        value: KgtkValue = KgtkValue(target_node)
        rb_type: str = rb_find_type(target_node, value)

        # If a relationship has multiple values, they must be next to each
        # other in the sorted list of item_edges.
        if current_relationship is None or relationship != current_relationship:
            # We are starting a new relationship.
            current_relationship = relationship
            current_values = list()
            relationship_label: str = rb_unstringify(relationship_label, default=relationship)
            current_property_map: typing.MutableMapping[str, any] = {
                "ref": relationship,
                "property": relationship_label,
                "type": rb_type, # TODO: check for consistency
                "values": current_values,
            }
            if wikidatatype is not None and wikidatatype == "external-id":
                response_xrefs.append(current_property_map)
            else:
                response_properties.append(current_property_map)

            # TODO: check that the wikidatatype is the same for all edges with
            # the same relationship.

        current_value: typing.MutableMapping[str, any] = rb_build_current_value(backend,
                                                                                target_node,
                                                                                value,
                                                                                rb_type,
                                                                                target_label,
                                                                                target_description,
                                                                                lang,
                                                                                relationship,
                                                                                wikidatatype)

        current_value["edge_id"] = edge_id # temporarily save the current edge ID.
        current_values.append(current_value)

    downsample_properties(response_properties, proplist_max_len, valuelist_max_len, repr(item), verbose)

    if verbose:
        print("rb_render_kb_items returns %d response_properties and %d response_xrefs)" % (len(response_properties),
                                                                                            len(response_xrefs)),
              file=sys.stderr, flush=True) # ***

    return response_properties, response_xrefs

def rb_build_edge_id_tuple(response_properties: typing.List[typing.MutableMapping[str, any]]):
    edge_set: typing.Set[str] = set()
    for scanned_property_map in response_properties:
        for scanned_value in scanned_property_map["values"]:
            scanned_edge_id = scanned_value["edge_id"]
            if scanned_edge_id not in edge_set:
                edge_set.add(scanned_edge_id)
    return tuple(list(edge_set))


edge_id_tuple_results_cache: typing.MutableMapping[str, typing.List[typing.List[str]]] = dict()
def rb_fetch_qualifiers_using_id_list(backend,
                                      edge_id_tuple,
                                      qual_query_limit: int = 0,
                                      lang: str = 'en',
                                      verbose: bool = False)->typing.List[typing.List[str]]:
    edge_id_tuple_key = "|".join(sorted(edge_id_tuple)) + "|" + lang + "}" + str(qual_query_limit)
    if edge_id_tuple_key in edge_id_tuple_results_cache:
        if verbose:
            print("Fetching qualifier edges for ID in %s (len=%d lang=%s, limit=%d) from cache" % (repr(edge_id_tuple),
                                                                                                   len(edge_id_tuple),
                                                                                                   repr(lang),
                                                                                                   qual_query_limit),
                  file=sys.stderr, flush=True) # ***
        return edge_id_tuple_results_cache[edge_id_tuple_key]

    if verbose:
        print("Fetching qualifier edges for ID in %s (len=%d, lang=%s, limit=%d)" % (repr(edge_id_tuple),
                                                                                     len(edge_id_tuple),
                                                                                     repr(lang),
                                                                                     qual_query_limit),
              file=sys.stderr, flush=True) # ***
    item_qualifier_edges = backend.rb_get_node_edge_qualifiers_in(edge_id_tuple, lang=lang, limit=qual_query_limit)

    # TODO: limit the size of the cache or apply LRU discipline.
    edge_id_tuple_results_cache[edge_id_tuple_key] = item_qualifier_edges # Cache the results.

    return item_qualifier_edges


def rb_fetch_qualifiers_using_id_queries(backend,
                                         edge_id_tuple,
                                         qual_query_limit: int = 0,
                                         lang: str = 'en',
                                         verbose: bool = False)->typing.List[typing.List[str]]:
    item_qualifier_edges: typing.List[typing.List[str]] = list()
    if verbose:
        print("Fetching qualifier edges for ID in %s (len=%d, lang=%s, limit=%d) as queries" % (repr(edge_id_tuple),
                                                                                                len(edge_id_tuple),
                                                                                                repr(lang),
                                                                                                qual_query_limit),
              file=sys.stderr, flush=True) # ***
    edge_id: str
    for edge_id in edge_id_tuple:
        item_qualifier_edges.extend(backend.rb_get_node_edge_qualifiers_by_edge_id(edge_id, lang=lang, limit=qual_query_limit))

    return item_qualifier_edges


def rb_fetch_qualifiers(backend,
                        item: str,
                        edge_id_tuple,
                        qual_query_limit: int = 0,
                        lang: str = 'en',
                        verbose: bool = False)->typing.List[typing.List[str]]:
    verbose2: bool = verbose

    item_qualifier_edges: typing.List[typing.List[str]]
    if len(edge_id_tuple) <= ID_SEARCH_THRESHOLD:
        if ID_SEARCH_USING_IN:
            item_qualifier_edges = rb_fetch_qualifiers_using_id_list(backend, edge_id_tuple, qual_query_limit=qual_query_limit, lang=lang, verbose=verbose2)
        else:
            item_qualifier_edges = rb_fetch_qualifiers_using_id_queries(backend, edge_id_tuple, qual_query_limit=qual_query_limit, lang=lang, verbose=verbose2)
    else:
        if verbose2:
            print("Fetching qualifier edges for item %s (lang=%s, limit=%d)" % (repr(item),
                                                                                repr(lang),
                                                                                qual_query_limit),
                  file=sys.stderr, flush=True) # ***
        item_qualifier_edges = backend.rb_get_node_edge_qualifiers(item, lang=lang, limit=qual_query_limit)
    if verbose2:
        print("Fetched %d qualifier edges" % len(item_qualifier_edges), file=sys.stderr, flush=True) # ***

    return item_qualifier_edges

def rb_fetch_and_render_qualifiers(backend,
                                   item: str,
                                   response_properties: typing.List[typing.MutableMapping[str, any]],
                                   qual_proplist_max_len: int = 0,
                                   qual_valuelist_max_len: int = 0,
                                   qual_query_limit: int = 0,
                                   lang: str = 'en',
                                   verbose: bool = False):
    scanned_property_map: typing.MutableMapping[str, any]
    scanned_value: typing.MutableMapping[str, any]
    scanned_edge_id: str

    edge_id_tuple = rb_build_edge_id_tuple(response_properties)
    item_qualifier_edges: typing.List[typing.List[str]] = rb_fetch_qualifiers(backend,
                                                                              item,
                                                                              edge_id_tuple,
                                                                              qual_query_limit=qual_query_limit,
                                                                              lang=lang,
                                                                              verbose=verbose)

    # Group the qualifiers by the item they qualify, identified by the item's
    # edge_id (which should be unique):
    item_qual_map: typing.Mapping[str, typing.List[typing.List[str]]] = rb_build_item_qualifier_map(item_qualifier_edges)
    if verbose:
        print("len(item_qual_map) = %d" % len(item_qual_map), file=sys.stderr, flush=True) # ***

    edges_without_qualifiers: int = 0
    for scanned_property_map in response_properties:
        for scanned_value in scanned_property_map["values"]:
            # Retrieve the associated edge_id
            scanned_edge_id = scanned_value["edge_id"]
            if scanned_edge_id not in item_qual_map:
                edges_without_qualifiers += 1
                continue # There are no associated qualifiers.

            scanned_value["qualifiers"] = \
                rb_render_item_qualifiers(backend,
                                          item,
                                          scanned_edge_id,
                                          item_qual_map[scanned_edge_id],
                                          qual_proplist_max_len,
                                          qual_valuelist_max_len,
                                          lang,
                                          verbose)

    if verbose:
        print("edges_without_qualifiers = %d" % edges_without_qualifiers, file=sys.stderr, flush=True) # ***

    for scanned_property_map in response_properties:
        for scanned_value in scanned_property_map["values"]:
            # Remove the edge_id
            if "edge_id" in scanned_value:
                del scanned_value["edge_id"]

def rb_render_kb_items_and_qualifiers(backend,
                                      item: str,
                                      item_edges: typing.List[typing.List[str]],
                                      proplist_max_len: int = 0,
                                      valuelist_max_len: int = 0,
                                      qual_proplist_max_len: int = 0,
                                      qual_valuelist_max_len: int = 0,
                                      qual_query_limit: int = 0,
                                      lang: str = 'en',
                                      verbose: bool = False)->typing.Tuple[typing.List[typing.MutableMapping[str, any]],
                                                                           typing.List[typing.MutableMapping[str, any]]]:

    response_properties: typing.List[typing.MutableMapping[str, any]] = list()
    response_xrefs: typing.List[typing.MutableMapping[str, any]] = list()
    response_properties, response_xrefs = rb_render_kb_items(backend,
                                                             item,
                                                             item_edges,
                                                             proplist_max_len=proplist_max_len,
                                                             valuelist_max_len=valuelist_max_len,
                                                             lang=lang,
                                                             verbose=verbose)

    rb_fetch_and_render_qualifiers(backend,
                                   item,
                                   response_properties,
                                   qual_proplist_max_len=qual_proplist_max_len,
                                   qual_valuelist_max_len=qual_valuelist_max_len,
                                   qual_query_limit=qual_query_limit,
                                   lang=lang,
                                   verbose=verbose)
    rb_fetch_and_render_qualifiers(backend,
                                   item,
                                   response_xrefs,
                                   qual_proplist_max_len=qual_proplist_max_len,
                                   qual_valuelist_max_len=qual_valuelist_max_len,
                                   qual_query_limit=qual_query_limit,
                                   lang=lang,
                                   verbose=verbose)
    return response_properties, response_xrefs

def downsample_properties(property_list: typing.MutableMapping[str, any],
                          proplist_max_len: int,
                          valuelist_max_len: int,
                          who: str,
                          verbose: bool = False):

    if proplist_max_len > 0 and len(property_list) > proplist_max_len:
        if verbose:
            print("Downsampling the properties for %s" % who, file=sys.stderr, flush=True)
        property_drop_count: int = 0
        while len(property_list) > proplist_max_len:
            property_drop_count += 1
            dropped_property_map: typing.Mapping[str, any] = property_list.pop(random.randrange(len(property_list)))
            if verbose:
                print("Dropping property %s (%s)" % (repr(dropped_property_map["property"]), repr(dropped_property_map["ref"])), file=sys.stderr, flush=True)
        if verbose:
            print("Dropped %d properties" % property_drop_count, file=sys.stderr, flush=True)

    if valuelist_max_len > 0:
        if verbose:
            print("Scanning for value lists to downsample for %s" % who, file=sys.stderr, flush=True)
        total_value_drop_count: int = 0
        downsampled_prop_count: int = 0
        scanned_property_map: typing.Mapping[str, any]
        for scanned_property_map in property_list:
            scanned_values: typing.List[any] = scanned_property_map["values"]
            if len(scanned_values) > valuelist_max_len:
                downsampled_prop_count += 1
                if verbose:
                    print("Downsampling values for property %s (%s)" % (repr(scanned_property_map["property"]),
                                                                        repr(scanned_property_map["ref"])), file=sys.stderr, flush=True)
                value_drop_count: int = 0
                while len(scanned_values) > valuelist_max_len:
                    value_drop_count += 1
                    dropped_value: typing.Mapping[str, str] = scanned_values.pop(random.randrange(len(scanned_values)))
                    if verbose:
                        print("dropping value %s (%s)" % (repr(dropped_value["text"]), repr(dropped_value.get("ref", ""))), file=sys.stderr, flush=True)
                total_value_drop_count += value_drop_count
                if verbose:
                    print("Dropped %d values" % value_drop_count, file=sys.stderr, flush=True)
        if verbose:
            print("Dropped %d values from %d properties" % (total_value_drop_count, downsampled_prop_count), file=sys.stderr, flush=True)

def rb_send_kb_items_and_qualifiers(backend,
                                    item: str,
                                    item_edges: typing.List[typing.List[str]],
                                    proplist_max_len: int = 0,
                                    valuelist_max_len: int = 0,
                                    qual_proplist_max_len: int = 0,
                                    qual_valuelist_max_len: int = 0,
                                    qual_query_limit: int = 0,
                                    lang: str = 'en',
                                    verbose: bool = False)->typing.Tuple[typing.List[typing.MutableMapping[str, any]],
                                                                         typing.List[typing.MutableMapping[str, any]]]:

    # Sort the item edges:
    sorted_item_edges: typing.List[typing.List[str]] = rb_build_sorted_item_edges(item_edges)
    if verbose:
        print("len(sorted_item_edges) = %d" % len(sorted_item_edges), file=sys.stderr, flush=True) # ***

    return rb_render_kb_items_and_qualifiers(backend,
                                             item,
                                             sorted_item_edges,
                                             proplist_max_len=proplist_max_len,
                                             valuelist_max_len=valuelist_max_len,
                                             qual_proplist_max_len=qual_proplist_max_len,
                                             qual_valuelist_max_len=qual_valuelist_max_len,
                                             qual_query_limit=qual_query_limit,
                                             lang=lang,
                                             verbose=verbose)


def rb_send_kb_categories(backend,
                          item: str,
                          response_categories: typing.MutableMapping[str, any],
                          category_edges: typing.List[typing.List[str]],
                          lang: str = 'en',
                          verbose: bool = False):

    if verbose:
        print("#categories: %d" % len(category_edges), file=sys.stderr, flush=True)

    node1: str
    node1_label: str
    node1_description: str

    categories_seen: typing.Set[str] = set()

    # Sort the item categories
    category_key: str
    keyed_category_edges: typing.MutableMapping[str, typing.List[str]] = dict()
    idx: int
    category_edge: typing.List[str]
    for idx, category_edge in enumerate(category_edges):
        node1, node1_label, node1_description = category_edge
        if node1 in categories_seen:
            continue
        categories_seen.add(node1)

        if node1_label is None:
            node1_label = node1
        category_key = (node1_label + "|" + str(idx + 1000000)).lower()
        keyed_category_edges[category_key] = category_edge

    for category_key in sorted(keyed_category_edges.keys()):
        category_edge = keyed_category_edges[category_key]
        if verbose:
            print(repr(category_edge), file=sys.stderr, flush=True)
        node1, node1_label, node1_description = category_edge

        response: typing.Mapping[str, str] = {
            "ref": node1,
            "text": rb_unstringify(node1_label, default=node1),
            "description": rb_unstringify(node1_description)
        }
        response_categories.append(response)


def rb_send_kb_item(item: str,
                    lang: str = "en",
                    proplist_max_len: int = 0,
                    valuelist_max_len: int = 0,
                    query_limit: int = 10000,
                    qual_proplist_max_len: int = 0,
                    qual_valuelist_max_len: int = 0,
                    qual_query_limit: int = 10000,
                    verbose: bool = False):
    try:
        with get_backend(app) as backend:
            rb_build_property_priority_map(backend, verbose=verbose) # Endure this has been initialized.

            verbose2: bool = verbose # ***

            if verbose2:
                print("Fetching item edges for %s (lang=%s, limit=%d)" % (repr(item), repr(lang), query_limit), file=sys.stderr, flush=True) # ***
            item_edges: typing.List[typing.List[str]] = backend.rb_get_node_edges(item, lang=lang, limit=query_limit)
            if len(item_edges) > query_limit: # Forcibly truncate!
                item_edges = item_edges[:query_limit]
            if verbose2:
                print("Fetched %d item edges" % len(item_edges), file=sys.stderr, flush=True) # ***

            # item_inverse_edges: typing.List[typing.List[str]] = backend.rb_get_node_inverse_edges(item, lang=lang)
            # item_inverse_qualifier_edges: typing.List[typing.List[str]] = backend.rb_get_node_inverse_edge_qualifiers(item, lang=lang)
            # if verbose:
            #     print("Fetching category edges", file=sys.stderr, flush=True) # ***
            # item_category_edges: typing.List[typing.List[str]] = backend.rb_get_node_categories(item, lang=lang)
            if verbose2:
                print("Done fetching edges", file=sys.stderr, flush=True) # ***

            response: typing.MutableMapping[str, any] = dict()
            response["ref"] = item

            item_labels: typing.List[typing.List[str]] = backend.get_node_labels(item, lang=lang)
            response["text"] = rb_unstringify(item_labels[0][1]) if len(item_labels) > 0 else item

            item_aliases: typing.List[str] = [x[1] for x in backend.get_node_aliases(item, lang=lang)]
            response["aliases"] = [rb_unstringify(x) for x in item_aliases]

            item_descriptions: typing.List[typing.List[str]] = backend.get_node_descriptions(item, lang=lang)
            response["description"] = rb_unstringify(item_descriptions[0][1]) if len(item_descriptions) > 0 else ""

            response_properties: typing.List[typing.MutableMapping[str, any]]
            response_xrefs: typing.List[typing.MutableMapping[str, any]]
            response_properties, response_xrefs = rb_send_kb_items_and_qualifiers(backend,
                                                                                  item,
                                                                                  item_edges,
                                                                                  proplist_max_len=proplist_max_len,
                                                                                  valuelist_max_len=valuelist_max_len,
                                                                                  qual_proplist_max_len=qual_proplist_max_len,
                                                                                  qual_valuelist_max_len=qual_valuelist_max_len,
                                                                                  qual_query_limit=qual_query_limit,
                                                                                  lang=lang,
                                                                                  verbose=verbose)
            response["properties"] = response_properties
            response["xrefs"] = response_xrefs

            # response_categories: typing.List[typing.MutableMapping[str, any]] = [ ]
            # response["categories"] = response_categories
            # rb_send_kb_categories(backend, item, response_categories, item_category_edges, lang=lang, verbose=verbose)

            # We cound assume a link to Wikipedia, but that won't be valid when
            # using KGTK for other data sources.
            # response["url"] = "https://sample.url"
            # response["document"] = "Sample document: " + item

            # The data source would also, presumably, be responsible for providing images.
            # response["gallery"] = [ ] # This is required by kb.js as a minimum element.
            response["gallery"] = rb_build_gallery(item_edges, item, item_labels)

            return flask.jsonify(response), 200
    except Exception as e:
        print('ERROR: ' + str(e))
        traceback.print_exc()
        flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

@app.route('/kb/item', methods=['GET'])
def rb_get_kb_item():
    """This is the API call to return JSON-encoded full information for an item.

    Parameter Usage
    ========= ==================================================================================
    id        The is the node name (P### or Q###) to be retrieved.  Case is significant.

    lang      The is the language code to use when selecting labels.  The default value is "en".

    proplist_max_len
              The maximum number of top-level properties (claims) to return.

    query_limit
              A limit on SQL query return list length.

    qual_proplist_max_len
              The maximum number of properties per qualifier.

    qual_valuelist_max_len
              The maximum numbers oer property per qualifier.

    qual_query_limit
              The maximum number of qualifiers per claim.

    valuelist_max_len
              The maximum number of values per rop-level property.

    verbose   This debugging parameter controls debugging output on the server.  The default is False.
    """
    args = flask.request.args
    item: str  = args.get('id')
    lang: str = args.get("lang", default=app.config['DEFAULT_LANGUAGE'])
    proplist_max_len: int = args.get('proplist_max_len', type=int,
                                     default=app.config['PROPLIST_MAX_LEN'])
    valuelist_max_len: int = args.get('valuelist_max_len', type=int,
                                      default=app.config['VALUELIST_MAX_LEN'])
    qual_proplist_max_len: int = args.get('qual_proplist_max_len', type=int,
                                          default=app.config['QUAL_PROPLIST_MAX_LEN'])
    qual_valuelist_max_len: int = args.get('qual_valuelist_max_len', type=int,
                                           default=app.config['QUAL_VALUELIST_MAX_LEN'])
    query_limit: int = args.get('query_limit', type=int,
                                default=app.config['QUERY_LIMIT'])
    qual_query_limit: int = args.get('qual_query_limit', type=int,
                                     default=app.config['QUAL_QUERY_LIMIT'])
    verbose: bool = args.get("verbose", type=rb_is_true,
                             default=app.config['VERBOSE'])

    if verbose:
        print("rb_get_kb_item: %s" % repr(item))
        print("lang: %s" % repr(lang))
        print("proplist_max_len: %s" % repr(proplist_max_len))
        print("valuelist_max_len: %s" % repr(valuelist_max_len))
        print("qual_proplist_max_len: %s" % repr(qual_proplist_max_len))
        print("qual_valuelist_max_len: %s" % repr(qual_valuelist_max_len))
        print("query_limit: %s" % repr(query_limit))
        print("qual_query_limit: %s" % repr(qual_query_limit))
    return rb_send_kb_item(item,
                           lang=lang,
                           proplist_max_len=proplist_max_len,
                           valuelist_max_len=valuelist_max_len,
                           query_limit=query_limit,
                           qual_proplist_max_len=qual_proplist_max_len,
                           qual_valuelist_max_len=qual_valuelist_max_len,
                           qual_query_limit=qual_query_limit,
                           verbose=verbose)


@app.route('/kb/item/<string:item>', methods=['GET'])
def rb_get_kb_named_item(item):
    """This is the API call to return the full information for an item wrapped in a browser
    client (HTML).  The item ID is passed in the URL directly.

    This code does not place constraints on the item name, but other code may still expect Pxxx or Qxxx.

    Parameter Usage
    ========= ==================================================================================
    lang      The is the language code to use when selecting labels.  The default value is "en".

    proplist_max_len
              The maximum number of top-level properties (claims) to return.

    query_limit
              A limit on SQL query return list length.

    qual_proplist_max_len
              The maximum number of properties per qualifier.

    qual_valuelist_max_len
              The maximum numbers oer property per qualifier.

    qual_query_limit
              The maximum number of qualifiers per claim.

    valuelist_max_len
              The maximum number of values per rop-level property.

    verbose   This debugging parameter controls debugging output on the server.  The default is False.

    TODO: encode the argument to the "lang" parameter to avoid a URL vulnerability.

    TODO: It might be useful to be able to pass each parameter individually through the HTML file,
    rather than concatenating them into a single string here.
    """
    # Parse some optional parameters.
    args = flask.request.args
    params: str = ""

    lang: str = args.get("lang", default=app.config['DEFAULT_LANGUAGE'])
    # TODO: encode the language properly, else this is a vulnerability.
    # Note: the first parameter does not have a leading ampersand!
    params += "lang=%s" % lang

    proplist_max_len: int = args.get('proplist_max_len', type=int,
                                     default=app.config['PROPLIST_MAX_LEN'])
    params += "&proplist_max_len=%d" % proplist_max_len

    valuelist_max_len: int = args.get('valuelist_max_len', type=int,
                                      default=app.config['VALUELIST_MAX_LEN'])
    params += "&valuelist_max_len=%d" % valuelist_max_len

    qual_proplist_max_len: int = args.get('qual_proplist_max_len', type=int,
                                          default=app.config['QUAL_PROPLIST_MAX_LEN'])
    params += "&qual_proplist_max_len=%d" % qual_proplist_max_len

    qual_valuelist_max_len: int = args.get('qual_valuelist_max_len', type=int,
                                           default=app.config['QUAL_VALUELIST_MAX_LEN'])
    params += "&qual_valuelist_max_len=%d" % qual_valuelist_max_len

    query_limit: int = args.get('query_limit', type=int,
                                default=app.config['QUERY_LIMIT'])
    params += "&query_limit=%d" % query_limit

    qual_query_limit: int = args.get('qual_query_limit', type=int,
                                     default=app.config['QUAL_QUERY_LIMIT'])
    params += "&qual_query_limit=%d" % qual_query_limit

    verbose: bool = args.get("verbose", default=app.config['VERBOSE'], type=rb_is_true)
    if verbose:
        params += "&verbose"

    if verbose:
        print("rb_get_kb_named_item: %s params: %s" % (repr(item), repr(params)), file=sys.stderr, flush=True)

    try:
        return flask.render_template("kb.html", ITEMID=item, PARAMS=params, SCRIPT="/kb/kb.js")
    except Exception as e:
        print('ERROR: ' + str(e))
        flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

@app.route('/kb/<string:item>', methods=['GET'])
def rb_get_kb_named_item2(item):
    args = flask.request.args
    verbose: bool = args.get("verbose", default=False, type=rb_is_true)

    if verbose:
        print("get_kb_named_item2: " + item)

    if item is None or len(item) == 0:
        try:
            return flask.send_from_directory('web/static', "kb.html")
        except Exception as e:
            print('ERROR: ' + str(e))
            flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    elif item in [ "kb.js", "kb.html" ]:
        try:
            return flask.send_from_directory('web/static', item)
        except Exception as e:
            print('ERROR: ' + str(e))
            flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

    else:
        try:
            return flask.render_template("kb.html", ITEMID=item, SCRIPT="/kb/kb.js")
        except Exception as e:
            print('ERROR: ' + str(e))
            flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)


### Test URL handlers:

# These all call the corresponding backend query method with the same name.
# Use 'fmt=df' for the most readable output, however, that requires pandas
# to be installed.  Otherwise a pretty-printed list format is the default.

# Status codes: https://docs.python.org/3/library/http.html

def get_request_args():
    """Access all handler args we currently support.
    """
    return {
        'node': flask.request.args.get('node'),
        'lang': flask.request.args.get('lang', app.config['DEFAULT_LANGUAGE']),
        'images': flask.request.args.get('images', 'False').lower() == 'true',
        'fanouts': flask.request.args.get('fanouts', 'False').lower() == 'true',
        'inverse': flask.request.args.get('inverse', 'False').lower() == 'true',
        'fmt': flask.request.args.get('fmt'),
    }

@app.route(os.path.join(app.config['SERVICE_PREFIX'], 'test_get_edges'), methods=['GET'])
def test_get_edges():
    node = flask.request.args.get('node')
    if node is None:
        flask.abort(HTTPStatus.BAD_REQUEST.value)
    return 'get_edges %s ' % node

@app.route(os.path.join(app.config['SERVICE_PREFIX'], 'get_node_labels'), methods=['GET'])
def get_node_labels():
    args = get_request_args()
    if args['node'] is None:
        flask.abort(HTTPStatus.BAD_REQUEST.value)
    try:
        with get_backend(app) as backend:
            labels = backend.get_node_labels(args['node'], lang=args['lang'], fmt=args['fmt'])
            return backend.query_result_to_string(labels)
    except Exception as e:
        print('ERROR: ' + str(e))
        flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

@app.route(os.path.join(app.config['SERVICE_PREFIX'], 'get_node_aliases'), methods=['GET'])
def get_node_aliases():
    args = get_request_args()
    if args['node'] is None:
        flask.abort(HTTPStatus.BAD_REQUEST.value)
    try:
        with get_backend(app) as backend:
            aliases = backend.get_node_aliases(args['node'], lang=args['lang'], fmt=args['fmt'])
            return backend.query_result_to_string(aliases)
    except Exception as e:
        print('ERROR: ' + str(e))
        flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

@app.route(os.path.join(app.config['SERVICE_PREFIX'], 'get_node_descriptions'), methods=['GET'])
def get_node_descriptions():
    args = get_request_args()
    if args['node'] is None:
        flask.abort(HTTPStatus.BAD_REQUEST.value)
    try:
        with get_backend(app) as backend:
            descriptions = backend.get_node_descriptions(args['node'], lang=args['lang'], fmt=args['fmt'])
            return backend.query_result_to_string(descriptions)
    except Exception as e:
        print('ERROR: ' + str(e))
        flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

@app.route(os.path.join(app.config['SERVICE_PREFIX'], 'get_node_images'), methods=['GET'])
def get_node_images():
    args = get_request_args()
    if args['node'] is None:
        flask.abort(HTTPStatus.BAD_REQUEST.value)
    try:
        with get_backend(app) as backend:
            images = backend.get_node_images(args['node'], fmt=args['fmt'])
            return backend.query_result_to_string(images)
    except Exception as e:
        print('ERROR: ' + str(e))
        flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

@app.route(os.path.join(app.config['SERVICE_PREFIX'], 'get_node_edges'), methods=['GET'])
def get_node_edges():
    args = get_request_args()
    if args['node'] is None:
        flask.abort(HTTPStatus.BAD_REQUEST.value)
    try:
        with get_backend(app) as backend:
            edges = backend.get_node_edges(
                args['node'], lang=args['lang'], images=args['images'], fanouts=args['fanouts'], fmt=args['fmt'])
            return backend.query_result_to_string(edges)
    except Exception as e:
        print('ERROR: ' + str(e))
        flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

@app.route(os.path.join(app.config['SERVICE_PREFIX'], 'get_node_inverse_edges'), methods=['GET'])
def get_node_inverse_edges():
    args = get_request_args()
    if args['node'] is None:
        flask.abort(HTTPStatus.BAD_REQUEST.value)
    try:
        with get_backend(app) as backend:
            edges = backend.get_node_inverse_edges(
                args['node'], lang=args['lang'], images=args['images'], fanouts=args['fanouts'], fmt=args['fmt'])
            return backend.query_result_to_string(edges)
    except Exception as e:
        print('ERROR: ' + str(e))
        flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

@app.route(os.path.join(app.config['SERVICE_PREFIX'], 'get_node_edge_qualifiers'), methods=['GET'])
def get_node_edge_qualifiers():
    args = get_request_args()
    if args['node'] is None:
        flask.abort(HTTPStatus.BAD_REQUEST.value)
    try:
        with get_backend(app) as backend:
            qualifiers = backend.get_node_edge_qualifiers(
                args['node'], lang=args['lang'], images=args['images'], fanouts=args['fanouts'], fmt=args['fmt'])
            return backend.query_result_to_string(qualifiers)
    except Exception as e:
        print('ERROR: ' + str(e))
        flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

@app.route(os.path.join(app.config['SERVICE_PREFIX'], 'get_node_inverse_edge_qualifiers'), methods=['GET'])
def get_node_inverse_edge_qualifiers():
    args = get_request_args()
    if args['node'] is None:
        flask.abort(HTTPStatus.BAD_REQUEST.value)
    try:
        with get_backend(app) as backend:
            qualifiers = backend.get_node_inverse_edge_qualifiers(
                args['node'], lang=args['lang'], images=args['images'], fanouts=args['fanouts'], fmt=args['fmt'])
            return backend.query_result_to_string(qualifiers)
    except Exception as e:
        print('ERROR: ' + str(e))
        flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

@app.route(os.path.join(app.config['SERVICE_PREFIX'], 'get_configuration'), methods=['GET'])
def get_configuration():
    """Show the currently loaded configuration values."""
    try:
        with get_backend(app) as backend:
            return backend.query_result_to_string(backend.api.config)
    except Exception as e:
        print('ERROR: ' + str(e))


### Top-level entry points:

@app.route(os.path.join(app.config['SERVICE_PREFIX'], 'get_all_node_data'), methods=['GET'])
def get_all_node_data():
    """Top-level method that collects all of a node's edge data,
    label strings dictionary, and whatever else we might need, and
    returns it all in a single 'kgtk_object_collection' JSON structure.
    """
    args = get_request_args()
    if args['node'] is None:
        flask.abort(HTTPStatus.BAD_REQUEST.value)
    try:
        with get_backend(app) as backend:
            data = backend.get_all_node_data(
                args['node'], lang=args['lang'], images=args['images'], fanouts=args['fanouts'], inverse=args['inverse'])
            return data or {}
    except Exception as e:
        print('ERROR: ' + str(e))
        flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)


@app.route('/kb/get_events_and_scores_by_date', methods=['GET'])
def get_events_and_scores_by_date():

    args = flask.request.args
    lang = args.get("lang", default="en")

    debug = args.get("debug", default=False, type=rb_is_true)
    verbose = args.get("verbose", default=False, type=rb_is_true)
    match_label_prefixes: bool = args.get("match_label_prefixes", default=True, type=rb_is_true)
    match_label_prefixes_limit: intl = args.get("match_label_prefixes_limit", default=99999999999999999, type=int)
    match_label_ignore_case: bool = args.get("match_label_ignore_case", default=True, type=rb_is_true)

    try:
        with get_backend(app) as backend:

            if debug:
                start = datetime.datetime.now()

            if match_label_prefixes:
                results = backend.rb_get_events_and_scores_by_date(lang=lang,
                                                                    ignore_case=match_label_ignore_case,
                                                                    limit=match_label_prefixes_limit)

                if verbose:
                    print("match_label_prefixes: Got %d matches" % len(results), file=sys.stderr, flush=True)

                results_grouped_by_sentence = {}
                for result in results:
                    sentence_id = result[0]

                    # add empty result obj if it is not in the set already
                    if sentence_id not in results_grouped_by_sentence:
                        results_grouped_by_sentence[sentence_id] = {}

                    # clean up the sentence string and add it to the result obj
                    if 'sentence' not in results_grouped_by_sentence[sentence_id]:
                        sentence_str = result[1]
                        sentence_pattern = re.compile('^\'(.*)\'\@en$')
                        sentence_match = re.match(sentence_pattern, sentence_str)[1]
                        results_grouped_by_sentence[sentence_id]['sentence'] = sentence_match

                    # clean up datetime str and add it to the result obj
                    if 'datetime' not in results_grouped_by_sentence[sentence_id]:
                        datetime_str = result[2]
                        datetime_pattern = re.compile('\^(\d+-\d+-\d+T\d+:\d+:\d+Z)\/11')
                        datetime_match = re.match(datetime_pattern, datetime_str)[1]
                        results_grouped_by_sentence[sentence_id]['datetime'] = datetime_match

                    # get the correct key/label for the moral foundation score
                    mf_key = scores_mapping[result[4]]
                    if mf_key not in results_grouped_by_sentence[sentence_id]:
                        mf_score = float(result[5])
                        results_grouped_by_sentence[sentence_id][mf_key] = mf_score

                results_grouped_by_date = {}
                for sentence_id, values in results_grouped_by_sentence.items():
                    date = values['datetime']
                    if date not in results_grouped_by_date:
                        results_grouped_by_date[date] = []

                    try:
                        results_grouped_by_date[date].append({
                            "id": sentence_id,
                            "sentence": values['sentence'],
                            "datetime": values['datetime'],
                            "authority/virtue": values["authority/virtue"],
                            "authority/vice": values["authority/vice"],
                            "fairness/virtue": values["fairness/virtue"],
                            "fairness/vice": values["fairness/vice"],
                            "harm/virtue": values["harm/virtue"],
                            "harm/vice": values["harm/vice"],
                            "ingroup/virtue": values["ingroup/virtue"],
                            "ingroup/vice": values["ingroup/vice"],
                            "purity/virtue": values["purity/virtue"],
                            "purity/vice": values["purity/vice"],
                        })
                    except KeyError:
                        print('sentence missing moral foundation scores: https://venice.isi.edu/browser/{}'.format(sentence_id))

            if debug:
                print('finished sql part, duration: ', str(datetime.datetime.now() - start ))

            return flask.jsonify(results_grouped_by_date), 200
    except Exception as e:
        print('ERROR: ' + str(e))
        flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)


@app.route('/kb/get_mf_scores_by_date', methods=['GET'])
def get_mf_scores_by_date():

    args = flask.request.args
    lang = args.get("lang", default="en")

    debug = args.get("debug", default=False, type=rb_is_true)
    verbose = args.get("verbose", default=False, type=rb_is_true)
    match_label_prefixes: bool = args.get("match_label_prefixes", default=True, type=rb_is_true)
    match_label_prefixes_limit: intl = args.get("match_label_prefixes_limit", default=99999999999999999, type=int)
    match_label_ignore_case: bool = args.get("match_label_ignore_case", default=True, type=rb_is_true)

    try:
        with get_backend(app) as backend:

            if debug:
                start = datetime.datetime.now()

            matches = []

            if match_label_prefixes:
                results = backend.rb_get_moral_foundations_with_p585(lang=lang,
                                                                    ignore_case=match_label_ignore_case,
                                                                    limit=match_label_prefixes_limit)

                if verbose:
                    print("match_label_prefixes: Got %d matches" % len(results), file=sys.stderr, flush=True)

                results_grouped_by_sentence = {}
                for result in results:
                    sentence_id = result[0]

                    # add empty result obj if it is not in the set already
                    if sentence_id not in results_grouped_by_sentence:
                        results_grouped_by_sentence[sentence_id] = {}

                    # clean up datetime str and add it to the result obj
                    if 'datetime' not in results_grouped_by_sentence[sentence_id]:
                        datetime_str = result[1]
                        datetime_pattern = re.compile('\^(\d+-\d+-\d+T\d+:\d+:\d+Z)\/11')
                        datetime_match = re.match(datetime_pattern, result[1])[1]
                        results_grouped_by_sentence[sentence_id]['datetime'] = datetime_match

                    # get the correct key/label for the moral foundation score
                    mf_key = scores_mapping[result[3]]
                    if mf_key not in results_grouped_by_sentence[sentence_id]:
                        mf_score = float(result[4])
                        results_grouped_by_sentence[sentence_id][mf_key] = mf_score

                for sentence_id, values in results_grouped_by_sentence.items():
                    try:
                        matches.append({
                            "id": sentence_id,
                            "datetime": values['datetime'],
                            "authority/virtue": values["authority/virtue"],
                            "authority/vice": values["authority/vice"],
                            "fairness/virtue": values["fairness/virtue"],
                            "fairness/vice": values["fairness/vice"],
                            "harm/virtue": values["harm/virtue"],
                            "harm/vice": values["harm/vice"],
                            "ingroup/virtue": values["ingroup/virtue"],
                            "ingroup/vice": values["ingroup/vice"],
                            "purity/virtue": values["purity/virtue"],
                            "purity/vice": values["purity/vice"],
                        })
                    except KeyError:
                        print('sentence missing moral foundation scores: https://venice.isi.edu/browser/{}'.format(sentence_id))

            if debug:
                print('finished sql part, duration: ', str(datetime.datetime.now() - start ))
                start = datetime.datetime.now()

            df = pd.DataFrame(matches)
            out_df = df.groupby('datetime').sum()

            if debug:
                print('finished pandas part, duration: ', str(datetime.datetime.now() - start ))

            return flask.jsonify(out_df.to_dict()), 200
    except Exception as e:
        print('ERROR: ' + str(e))
        flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)


@app.route('/kb/get_mf_scores_by_date_for_node/<string:node>', methods=['GET'])
def get_mf_scores_by_date_for_node(node):

    args = flask.request.args
    lang = args.get("lang", default="en")

    debug = args.get("debug", default=False, type=rb_is_true)
    verbose = args.get("verbose", default=False, type=rb_is_true)
    match_label_prefixes: bool = args.get("match_label_prefixes", default=True, type=rb_is_true)
    match_label_prefixes_limit: intl = args.get("match_label_prefixes_limit", default=100000, type=int)
    match_label_ignore_case: bool = args.get("match_label_ignore_case", default=True, type=rb_is_true)

    try:
        with get_backend(app) as backend:

            if debug:
                start = datetime.datetime.now()

            matches = []
            items_seen: typing.Set[str] = set()

            if match_label_prefixes:
                results = backend.rb_get_moral_foundations_with_p585_for_node(node=node,
                                                                            lang=lang,
                                                                            ignore_case=match_label_ignore_case,
                                                                            limit=match_label_prefixes_limit)

                if verbose:
                    print("match_label_prefixes: Got %d matches" % len(results), file=sys.stderr, flush=True)

                results_grouped_by_sentence = {}
                for result in results:
                    sentence_id = result[0]

                    # add empty result obj if it is not in the set already
                    if sentence_id not in results_grouped_by_sentence:
                        results_grouped_by_sentence[sentence_id] = {}

                    # clean up datetime str and add it to the result obj
                    if 'datetime' not in results_grouped_by_sentence[sentence_id]:
                        datetime_str = result[1]
                        datetime_pattern = re.compile('\^(\d+-\d+-\d+T\d+:\d+:\d+Z)\/11')
                        datetime_match = re.match(datetime_pattern, result[1])[1]
                        results_grouped_by_sentence[sentence_id]['datetime'] = datetime_match

                    # get the correct key/label for the moral foundation score
                    mf_key = scores_mapping[result[3]]
                    if mf_key not in results_grouped_by_sentence[sentence_id]:
                        mf_score = float(result[4])
                        results_grouped_by_sentence[sentence_id][mf_key] = mf_score

                for sentence_id, values in results_grouped_by_sentence.items():
                    try:
                        matches.append({
                            "id": sentence_id,
                            "datetime": values['datetime'],
                            "authority/virtue": values["authority/virtue"],
                            "authority/vice": values["authority/vice"],
                            "fairness/virtue": values["fairness/virtue"],
                            "fairness/vice": values["fairness/vice"],
                            "harm/virtue": values["harm/virtue"],
                            "harm/vice": values["harm/vice"],
                            "ingroup/virtue": values["ingroup/virtue"],
                            "ingroup/vice": values["ingroup/vice"],
                            "purity/virtue": values["purity/virtue"],
                            "purity/vice": values["purity/vice"],
                        })
                    except KeyError:
                        print('sentence missing moral foundation scores: https://venice.isi.edu/browser/{}'.format(sentence_id))

            if debug:
                print('finished sql part, duration: ', str(datetime.datetime.now() - start ))
                start = datetime.datetime.now()

            df = pd.DataFrame(matches)
            out_df = df.groupby('datetime').sum()

            if debug:
                print('finished pandas part, duration: ', str(datetime.datetime.now() - start ))

            return flask.jsonify(out_df.to_dict()), 200
    except Exception as e:
        print('ERROR: ' + str(e))
        flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)


@app.route('/kb/get_mf_and_concreteness_scores_by_date', methods=['GET'])
def get_mf_scores_and_concreteness_by_date():

    args = flask.request.args
    lang = args.get("lang", default="en")

    debug = args.get("debug", default=False, type=rb_is_true)
    verbose = args.get("verbose", default=False, type=rb_is_true)
    match_label_prefixes: bool = args.get("match_label_prefixes", default=True, type=rb_is_true)
    match_label_prefixes_limit: intl = args.get("match_label_prefixes_limit", default=100000, type=int)
    match_label_ignore_case: bool = args.get("match_label_ignore_case", default=True, type=rb_is_true)

    try:
        with get_backend(app) as backend:

            if debug:
                start = datetime.datetime.now()

            matches = []
            items_seen: typing.Set[str] = set()

            if match_label_prefixes:
                results = backend.rb_get_moral_foundations_and_concreteness_with_p585(lang=lang,
                                                                    ignore_case=match_label_ignore_case,
                                                                    limit=match_label_prefixes_limit)

                if verbose:
                    print("match_label_prefixes: Got %d matches" % len(results), file=sys.stderr, flush=True)

                results_grouped_by_sentence = {}
                for result in results:
                    sentence_id = result[0]

                    # add empty result obj if it is not in the set already
                    if sentence_id not in results_grouped_by_sentence:
                        results_grouped_by_sentence[sentence_id] = {}

                    # clean up datetime str and add it to the result obj
                    if 'datetime' not in results_grouped_by_sentence[sentence_id]:
                        datetime_str = result[1]
                        datetime_pattern = re.compile('\^(\d+-\d+-\d+T\d+:\d+:\d+Z)\/11')
                        datetime_match = re.match(datetime_pattern, result[1])[1]
                        results_grouped_by_sentence[sentence_id]['datetime'] = datetime_match

                    # get the correct key/label for the moral foundation score
                    mf_key = scores_mapping[result[3]]
                    if mf_key not in results_grouped_by_sentence[sentence_id]:
                        mf_score = float(result[4])
                        results_grouped_by_sentence[sentence_id][mf_key] = mf_score

                for sentence_id, values in results_grouped_by_sentence.items():
                    try:
                        matches.append({
                            "id": sentence_id,
                            "datetime": values['datetime'],
                            "authority/virtue": values["authority/virtue"],
                            "authority/vice": values["authority/vice"],
                            "fairness/virtue": values["fairness/virtue"],
                            "fairness/vice": values["fairness/vice"],
                            "harm/virtue": values["harm/virtue"],
                            "harm/vice": values["harm/vice"],
                            "ingroup/virtue": values["ingroup/virtue"],
                            "ingroup/vice": values["ingroup/vice"],
                            "purity/virtue": values["purity/virtue"],
                            "purity/vice": values["purity/vice"],
                            "concreteness": values["concreteness"],
                        })
                    except KeyError:
                        print('sentence missing moral foundation scores: https://venice.isi.edu/browser/{}'.format(sentence_id))


            if debug:
                print('finished sql part, duration: ', str(datetime.datetime.now() - start ))
                start = datetime.datetime.now()

            df = pd.DataFrame(matches)
            out_df = df.groupby('datetime').sum()

            if debug:
                print('finished pandas part, duration: ', str(datetime.datetime.now() - start ))

            return flask.jsonify(out_df.to_dict()), 200
    except Exception as e:
        print('ERROR: ' + str(e))
        flask.abort(HTTPStatus.INTERNAL_SERVER_ERROR.value)

@app.route('/kb/get_acled_forecast/<string:filename>', methods=['GET'])
def get_acled_forecast(filename):

    forecast_data = open('/data/forecasts/{}'.format(filename)).read()

    return forecast_data
