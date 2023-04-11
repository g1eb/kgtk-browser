import kgtk.kypher.api as kapi
from browser.backend.kgtk_browser_config import *


# Query configuration section:

# The queries defined below are used by the backend to retrieve and
# aggregate information about nodes.  It should generally not be
# necessary to adapt these queries unless the schema of the knowledge
# graph significantly deviates from the standard KGTK schema used for
# Wikidata.  By 'schema' we mean what kind of labels are used for
# edges and what kind of representation scheme is used for certain
# information.  For example, an edge label description string might be
# attached as a 'label' edge from the edge label (such as 'P31'), or
# it might be attached, for example, via some intermediate node.
# Similarly, queries might access information from an actual graph
# table, or instead return dummy default values (e.g., to return the
# same default fanout for every edge), or compute a value in some way.

# The backend makes assumptions about the columns retrieved by each
# query and what kind of parameters each of them take.  If a query
# gets modified, these assumption need to be met to not require any
# backend reprogramming.  If data relevant to a particular parameter
# is not available (e.g., a dataset might be monolingual or might not
# have any image information), parameters controlling that information
# may simply be ignored.  The doc string of each query describes its
# behavior in more detail.


class KypherAPIObject(object):
    def __init__(self):
        self.kapi = kapi.KypherApi(graphcache=GRAPH_CACHE,
                                   loglevel=LOG_LEVEL,
                                   index=INDEX_MODE,
                                   maxresults=MAX_RESULTS,
                                   maxcache=MAX_CACHE_SIZE,
                                   readonly=False)

        self.kapi.add_input(KG_EDGES_GRAPH, name='edges', handle=True)
        self.kapi.add_input(KG_QUALIFIERS_GRAPH, name='qualifiers', handle=True)
        self.kapi.add_input(KG_LABELS_GRAPH, name='labels', handle=True)
        self.kapi.add_input(KG_ALIASES_GRAPH, name='aliases', handle=True)
        self.kapi.add_input(KG_DESCRIPTIONS_GRAPH, name='descriptions', handle=True)
        self.kapi.add_input(KG_IMAGES_GRAPH, name='images', handle=True)
        self.kapi.add_input(KG_FANOUTS_GRAPH, name='fanouts', handle=True)
        self.kapi.add_input(KG_DATATYPES_GRAPH, name='datatypes', handle=True)

    def NODE_LABELS_QUERY(self):
        return self.kapi.get_query(
            doc="""
                Create the Kypher query used by 'BrowserBackend.get_node_labels()'.
                Given parameters 'NODE' and 'LANG' retrieve labels for 'NODE' in
                the specified language (using 'any' for 'LANG' retrieves all labels).
                Return distinct 'node1', 'node_label' pairs as the result (we include
                'NODE' as an output to make it easier to union result frames).
                """,
            inputs='labels',
            maxcache=MAX_CACHE_SIZE * 10,
            match='$labels: (n)-[r:`%s`]->(l)' % KG_LABELS_LABEL,
            where=f'n=$NODE and ($LANG="any" or kgtk_lqstring_lang(l)=$LANG)',
            ret='distinct n as node1, l as node_label',
        )

    def NODE_ALIASES_QUERY(self):
        return self.kapi.get_query(
            doc="""
                Create the Kypher query used by 'BrowserBackend.get_node_aliases()'.
                Given parameters 'NODE' and 'LANG' retrieve aliases for 'NODE' in
                the specified language (using 'any' for 'LANG' retrieves all labels).
                Return distinct 'node1', 'node_alias' pairs as the result.
                """,
            inputs='aliases',
            match='$aliases: (n)-[r:`%s`]->(a)' % KG_ALIASES_LABEL,
            where=f'n=$NODE and ($LANG="any" or kgtk_lqstring_lang(a)=$LANG)',
            ret='distinct n as node1, a as node_alias',
        )

    def NODE_DESCRIPTIONS_QUERY(self):
        return self.kapi.get_query(
            doc="""
                Create the Kypher query used by 'BrowserBackend.get_node_descriptions()'.
                Given parameters 'NODE' and 'LANG' retrieve descriptions for 'NODE' in
                the specified language (using 'any' for 'LANG' retrieves all labels).
                Return distinct 'node1', 'node_description' pairs as the result.
                """,
            inputs='descriptions',
            match='$descriptions: (n)-[r:`%s`]->(d)' % KG_DESCRIPTIONS_LABEL,
            where=f'n=$NODE and ($LANG="any" or kgtk_lqstring_lang(d)=$LANG)',
            ret='distinct n as node1, d as node_description',
        )

    def NODE_IMAGES_QUERY(self, node: str):
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.get_node_images()'.
            Given parameter 'NODE' retrieve image URIs for 'NODE'.
            Return distinct 'node1', 'node_image' pairs as the result.
            """,
            name=f'node_images_query_{node}',
            inputs='images',
            match='$images: (n)-[r:`%s`]->(i)' % KG_IMAGES_LABEL,
            where=f'n="{node}"',
            ret='distinct n as node1, i as node_image',
        )

    def NODE_EDGES_QUERY(self, node: str, lang: str, images, fanouts):
        return self.kapi.get_query(
            doc="""
                Create the Kypher query used by 'BrowserBackend.get_node_edges()'.
                Given parameter 'NODE' retrieve all edges that have 'NODE' as their node1.
                Additionally retrieve descriptive information for all node2's such as their
                label, and optionally any images and fanouts.  Parameter 'LANG' controls
                the language for retrieved labels, parameters 'FETCH_IMAGES' and 'FETCH_FANOUTS'
                control whether any images or fanouts should be returned.  If they are False,
                the corresponding result column values will all be None.
                Return edge 'id', 'node1', 'label', 'node2', as well as node2's 'node_label',
                and optional 'node_image' and 'node_fanout' as the result (note that in case
                of multiple node2 labels or images, edge row information may be duplicated).
                """,
            name=f'node_edges_query_{node}_{lang}_{images}_{fanouts}',
            inputs=('edges', 'labels', 'images', 'fanouts'),
            match='$edges: (n1)-[r]->(n2)',
            where=f'n1="{node}"',
            opt='$labels: (n2)-[:`%s`]->(n2label)' % KG_LABELS_LABEL,
            owhere=f'"{lang}"="any" or kgtk_lqstring_lang(n2label)="{lang}"',
            opt2='$images: (n2)-[:`%s`]->(n2image)' % KG_IMAGES_LABEL,
            owhere2=f'"{images}"',
            opt3='$fanouts: (n2)-[:`%s`]->(n2fanout)' % KG_FANOUTS_LABEL,
            owhere3=f'"{fanouts}"',
            ret='r as id, n1 as node1, r.label as label, n2 as node2, ' +
                'n2label as node_label, n2image as node_image, n2fanout as node_fanout',
        )

    def NODE_INVERSE_EDGES_QUERY(self, node: str, lang: str, images, fanouts):
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.get_node_inverse_edges()'.
            Given parameter 'NODE' retrieve all edges that have 'NODE' as their node2.
            Otherwise this is similar to 'NODE_EDGES_QUERY', just with descriptive
            information retrieved about edge node1's instead.
            """,
            name=f'node_inverse_edges_query_{node}_{lang}_{images}_{fanouts}',
            inputs=('edges', 'labels', 'images', 'fanouts'),
            match='$edges: (n1)-[r]->(n2)',
            where=f'n2="{node}"',
            opt='$labels: (n1)-[:`%s`]->(n1label)' % KG_LABELS_LABEL,
            owhere=f'"{lang}"="any" or kgtk_lqstring_lang(n1label)="{lang}"',
            opt2='$images: (n1)-[:`%s`]->(n1image)' % KG_IMAGES_LABEL,
            owhere2=f'"{images}"',
            opt3='$fanouts: (n1)-[:`%s`]->(n1fanout)' % KG_FANOUTS_LABEL,
            owhere3=f'"{fanouts}"',
            ret='r as id, n1 as node1, r.label as label, n2 as node2, ' +
                'n1label as node_label, n1image as node_image, n1fanout as node_fanout',
        )

    def NODE_EDGE_QUALIFIERS_QUERY(self, node: str, lang: str, images, fanouts):
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.get_node_edge_qualifiers()'.
            Given parameter 'NODE' retrieve all edges that have 'NODE' as their node1
            and then all qualifier edges for all such base edges found.  For each
            qualifier edge return information similar to what 'NODE_EDGES_QUERY' returns
            for base edges.
            """,
            name=f'node_edge_qualifiers_query_{node}_{lang}_{images}_{fanouts}',
            inputs=('edges', 'qualifiers', 'labels', 'images', 'fanouts'),
            match='$edges: (n1)-[r]->(), $qualifiers: (r)-[q]->(qn2)',
            where=f'n1="{node}"',
            opt='$labels: (qn2)-[:`%s`]->(qn2label)' % KG_LABELS_LABEL,
            owhere=f'"{lang}"="any" or kgtk_lqstring_lang(qn2label)="{lang}"',
            opt2='$images: (qn2)-[:`%s`]->(qn2image)' % KG_IMAGES_LABEL,
            owhere2=f'"{images}"',
            opt3='$fanouts: (qn2)-[:`%s`]->(qn2fanout)' % KG_FANOUTS_LABEL,
            owhere3=f'"{fanouts}"',
            ret='q, r as node1, q.label as label, qn2 as node2, ' +
                'qn2label as node_label, qn2image as node_image, qn2fanout as node_fanout',
            order='r, qn2 desc',
        )

    def NODE_INVERSE_EDGE_QUALIFIERS_QUERY(self, node: str, lang: str, images, fanouts):
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.get_node_inverse_edge_qualifiers()'.
            Given parameter 'NODE' retrieve all edges that have 'NODE' as their node2
            and then all qualifier edges for all such inverse base edges found.  For each
            qualifier edge return information similar to what 'NODE_EDGES_QUERY' returns
            for base edges.
            """,
            name=f'node_inverse_edge_qualifiers_query_{node}_{lang}_{images}_{fanouts}',
            inputs=('edges', 'qualifiers', 'labels', 'images', 'fanouts'),
            match='$edges: ()-[r]->(n2), $qualifiers: (r)-[q]->(qn2)',
            where=f'n2="{node}"',
            opt='$labels: (qn2)-[:`%s`]->(qn2label)' % KG_LABELS_LABEL,
            owhere=f'"{lang}"="any" or kgtk_lqstring_lang(qn2label)="{lang}"',
            opt2='$images: (qn2)-[:`%s`]->(qn2image)' % KG_IMAGES_LABEL,
            owhere2=f'"{images}"',
            opt3='$fanouts: (qn2)-[:`%s`]->(qn2fanout)' % KG_FANOUTS_LABEL,
            owhere3=f'"{fanouts}"',
            ret='q, r as node1, q.label as label, qn2 as node2, ' +
                'qn2label as node_label, qn2image as node_image, qn2fanout as node_fanout',
            order='r, qn2 desc',
        )

    def MATCH_ITEMS_EXACTLY_QUERY(self):
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.get_node_labels()'
            for case_independent searches.
            Given parameters 'NODE' retrieve labels for 'NODE'.
            Return distinct 'node1', 'node_label' pairs as the result (we include
            'NODE' as an output to make it easier to union result frames).
            """,
            inputs='l_d_pgr_ud',
            maxcache=MAX_CACHE_SIZE * 10,
            match=f'l_d_pgr_ud: (n)-[r:{KG_LABELS_LABEL}]->(l)',
            where=f'n=$NODE',
            ret='distinct n as node1, l as node_label, r.`node1;description` as description',
        )

    def MATCH_ITEMS_EXACTLY_SUBCLASS_QUERY(self):
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.get_node_labels()'
            for case_independent searches.
            Given parameters 'NODE' retrieve labels for 'NODE' which are a subclass.
            Return distinct 'node1', 'node_label' pairs as the result (we include
            'NODE' as an output to make it easier to union result frames).
            """,
            inputs=('l_d_pgr_ud', 'claims'),
            maxcache=MAX_CACHE_SIZE * 10,
            match=f'l_d_pgr_ud: (n)-[r:{KG_LABELS_LABEL}]->(l), claims: (n)-[:{KG_SUBCLASS_LABEL}]->()',
            where=f'n=$NODE',
            ret='distinct n as node1, l as node_label, r.`node1;description` as description',
        )

    def MATCH_ITEMS_EXACTLY_SUBCLASSSTAR_QUERY(self):
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.get_node_labels()'
            for case_independent searches.
            Given parameters 'NODE' retrieve labels for 'NODE' which is a subclass of 'CLASS'.
            Return distinct 'node1', 'node_label' pairs as the result (we include
            'NODE' as an output to make it easier to union result frames).
            """,
            inputs=('l_d_pgr_ud', 'p31279star'),
            maxcache=MAX_CACHE_SIZE * 10,
            match=f'l_d_pgr_ud: (n)-[r:{KG_LABELS_LABEL}]->(l), claims: (n)-[:{KG_P31P279STAR_LABEL}]->(class)',
            where=f'n=$NODE and class=$CLASS and n!=class',
            ret='distinct n as node1, l as node_label, r.`node1;description` as description',
        )

    def RB_NODES_WITH_LABEL_QUERY(self):
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.rb_get_nodes_with_label()'.
            Given parameters 'LABEL' and 'LANG' retrieve nodes with labels matching 'LABEL' in
            the specified language (using 'any' for 'LANG' retrieves all labels).
            Return distinct 'node1', 'node_label' pairs as the result

            For proper performace, 'node2' in the label graph must be indexed:

            CREATE INDEX "graph_2_node2_idx" ON graph_2 ("node2");
            ANALYZE "graph_2_node2_idx";
            """,
            inputs='labels',
            maxcache=MAX_CACHE_SIZE * 10,
            match='$labels: (n)-[r:`%s`]->(l)' % KG_LABELS_LABEL,
            where=f'l=$LABEL and ($LANG="any" or kgtk_lqstring_lang(l)=$LANG)',
            ret='distinct n as node1, l as node_label',
        )

    def MATCH_UPPER_LABELS_EXACTLY_QUERY(self):
        return self.kapi.get_query(
            doc="""
             Exact Match case insensitive query
            """,
            inputs='l_d_pgr_ud',
            maxcache=MAX_CACHE_SIZE * 10,
            match=f'l_d_pgr_ud: (n)-[r:{KG_LABELS_LABEL}]->(l)',
            where='r.`node2;upper`=$LABEL',
            ret='distinct n as node1, l as node_label, cast("-1.0", float) as score, cast(r.`node1;pagerank`, '
                'float) as prank, r.`node1;description` as description',
            order='score*prank',
            limit='$LIMIT'
        )

    def MATCH_UPPER_LABELS_EXACTLY_SUBCLASS_QUERY(self):
        return self.kapi.get_query(
            doc="""
             Exact Match case insensitive query for qnodes which are also subclasses
            """,
            inputs=('l_d_pgr_ud', 'claims'),
            maxcache=MAX_CACHE_SIZE * 10,
            match=f'l_d_pgr_ud: (n)-[r:{KG_LABELS_LABEL}]->(l), claims: (n)-[:{KG_SUBCLASS_LABEL}]->()',
            where='r.`node2;upper`=$LABEL',
            ret='distinct n as node1, l as node_label, cast("-1.0", float) as score, cast(r.`node1;pagerank`, '
                'float) as prank, r.`node1;description` as description',
            order='score*prank',
            limit='$LIMIT'
        )

    def MATCH_UPPER_LABELS_EXACTLY_SUBCLASSSTAR_QUERY(self):
        return self.kapi.get_query(
            doc="""
             Exact Match case insensitive query for qnodes which are subclasses of parameter CLASS
            """,
            inputs=('l_d_pgr_ud', 'p31279star'),
            maxcache=MAX_CACHE_SIZE * 10,
            match=f'l_d_pgr_ud: (n)-[r:{KG_LABELS_LABEL}]->(l), p31279star: (n)-[:{KG_P31P279STAR_LABEL}]->(class)',
            where='r.`node2;upper`=$LABEL and class=$CLASS and n!=class',
            ret='distinct n as node1, l as node_label, cast("-1.0", float) as score, cast(r.`node1;pagerank`, '
                'float) as prank, r.`node1;description` as description',
            order='score*prank',
            limit='$LIMIT'
        )

    def MATCH_LABELS_TEXTSEARCH_QUERY(self):
        return self.kapi.get_query(
            doc="""
             Text Search query
            """,
            inputs='l_d_pgr_ud',
            maxcache=MAX_CACHE_SIZE * 10,
            match=f'l_d_pgr_ud: (n)-[r:{KG_LABELS_LABEL}]->(l)',
            where='textmatch(l, $LABEL) and ($LANG="any" or kgtk_lqstring_lang(l)=$LANG)',
            ret='distinct n as node1, l as node_label, matchscore(l) as score,'
                ' cast(r.`node1;pagerank`, float) as prank, r.`node1;description` as description',
            order='score*prank',
            limit='$LIMIT'
        )

    def MATCH_LABELS_TEXTSEARCH_SUBCLASS_QUERY(self):
        return self.kapi.get_query(
            doc="""
             Text Search subclass query, search for qnodes which are also subclasses
            """,
            inputs=('l_d_pgr_ud', 'claims'),
            maxcache=MAX_CACHE_SIZE * 10,
            match=f'l_d_pgr_ud: (n)-[r:{KG_LABELS_LABEL}]->(l), claims: (n)-[:{KG_SUBCLASS_LABEL}]->()',
            where='textmatch(l, $LABEL) and ($LANG="any" or kgtk_lqstring_lang(l)=$LANG)',
            ret='distinct n as node1, l as node_label, matchscore(l) as score,'
                ' cast(r.`node1;pagerank`, float) as prank, r.`node1;description` as description',
            order='score*prank',
            limit='$LIMIT'
        )

    def MATCH_LABELS_TEXTSEARCH_SUBCLASSSTAR_QUERY(self):
        return self.kapi.get_query(
            doc="""
             Text Search subclass query, search for qnodes which are subclasses of parameter CLASS
            """,
            inputs=('l_d_pgr_ud', 'p31279star'),
            maxcache=MAX_CACHE_SIZE * 10,
            match=f'l_d_pgr_ud: (n)-[r:{KG_LABELS_LABEL}]->(l), p31279star: (n)-[:{KG_P31P279STAR_LABEL}]->(class)',
            where='textmatch(l, $LABEL) and ($LANG="any" or kgtk_lqstring_lang(l)=$LANG) and class=$CLASS and n!=class',
            ret='distinct n as node1, l as node_label, matchscore(l) as score,'
                ' cast(r.`node1;pagerank`, float) as prank, r.`node1;description` as description',
            order='score*prank',
            limit='$LIMIT'
        )

    def MATCH_LABELS_TEXTLIKE_QUERY(self):
        return self.kapi.get_query(
            doc="""
             Text Like Query
            """,
            inputs='l_d_pgr_ud',
            maxcache=MAX_CACHE_SIZE * 10,
            match=f'l_d_pgr_ud: (n)-[r:{KG_LABELS_LABEL}]->(l)',
            where='textlike(l, $LABEL) and ($LANG="any" or kgtk_lqstring_lang(l)=$LANG)',
            ret='distinct n as node1, l as node_label, matchscore(l) as score,'
                ' cast(r.`node1;pagerank`, float) as prank, r.`node1;description` as description',
            order='score*prank',
            limit='$LIMIT'
        )

    def MATCH_LABELS_TEXTLIKE_SUBCLASS_QUERY(self):
        return self.kapi.get_query(
            doc="""
             Text Like Query for qnodes which are also subclasses
            """,
            inputs='l_d_pgr_ud, claims',
            maxcache=MAX_CACHE_SIZE * 10,
            match=f'l_d_pgr_ud: (n)-[r:{KG_LABELS_LABEL}]->(l), claims: (n)-[:{KG_SUBCLASS_LABEL}]->()',
            where='textlike(l, $LABEL) and ($LANG="any" or kgtk_lqstring_lang(l)=$LANG)',
            ret='distinct n as node1, l as node_label, matchscore(l) as score,'
                ' cast(r.`node1;pagerank`, float) as prank, r.`node1;description` as description',
            order='score*prank',
            limit='$LIMIT'
        )

    def MATCH_LABELS_TEXTLIKE_SUBCLASSSTAR_QUERY(self):
        return self.kapi.get_query(
            doc="""
             Text Like Query for qnodes which are also subclasses of parameter CLASS
            """,
            inputs=('l_d_pgr_ud', 'p31279star'),
            maxcache=MAX_CACHE_SIZE * 10,
            match=f'l_d_pgr_ud: (n)-[r:{KG_LABELS_LABEL}]->(l), p31279star: (n)-[:{KG_P31P279STAR_LABEL}]->(class)',
            where='textlike(l, $LABEL) and ($LANG="any" or kgtk_lqstring_lang(l)=$LANG) and class=$CLASS and n!=class',
            ret='distinct n as node1, l as node_label, matchscore(l) as score,'
                ' cast(r.`node1;pagerank`, float) as prank, r.`node1;description` as description',
            order='score*prank',
            limit='$LIMIT'
        )

    def RB_NODE_EDGES_QUERY(self):
        return self.kapi.get_query(
            doc="""
                Create the Kypher query used by 'BrowserBackend.rb_get_node_edges()'.
                Given parameter 'NODE' retrieve all edges that have 'NODE' as their node1.
                Additionally retrieve descriptive information for all relationship labels.
                Additionally retrieve the node2 descriptions.
                Parameter 'LANG' controls the language for retrieved labels.
                Return edge 'id', 'label', 'node2', as well as node2's 'node2_label'
                and label's 'label_label'.
                Limit the number of return edges to LIMIT.

                """,
            inputs=('edges', 'labels', 'descriptions', 'datatypes'),
            match='$edges: (n1)-[r {label: rl}]->(n2)',
            where=f'n1=$NODE',
            opt='$labels: (rl)-[:`%s`]->(llabel)' % KG_LABELS_LABEL,
            owhere=f'$LANG="any" or kgtk_lqstring_lang(llabel)=$LANG',
            opt2='$labels: (n2)-[:`%s`]->(n2label)' % KG_LABELS_LABEL,
            owhere2=f'$LANG="any" or kgtk_lqstring_lang(n2label)=$LANG',
            opt3='$descriptions: (n2)-[r:`%s`]->(n2desc)' % KG_DESCRIPTIONS_LABEL,
            owhere3=f'$LANG="any" or kgtk_lqstring_lang(n2desc)=$LANG',
            opt4='$datatypes: (rl)-[:`%s`]->(rlwdt)' % KG_DATATYPES_LABEL,
            ret='r as id, ' +
                'n1 as node1, ' +
                'r.label as relationship, ' +
                'n2 as node2, ' +
                'llabel as relationship_label, ' +
                'n2 as target_node, ' +
                'n2label as target_label, ' +
                'n2desc as target_description, ' +
                'rlwdt as wikidatatype',
            order='r.label, n2, r, llabel, n2label, n2desc',  # For better performance with LIMIT, sort in caller.
            limit='$LIMIT'
        )

    def RB_NODE_EDGE_QUALIFIERS_QUERY(self):
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.get_node_edge_qualifiers()'.
            Given parameter 'NODE' retrieve all edges that have 'NODE' as their node1
            and then all qualifier edges for all such base edges found.  For each
            qualifier edge return information similar to what 'NODE_EDGES_QUERY' returns
            for base edges.
            """,
            inputs=('edges', 'qualifiers', 'labels', 'descriptions'),
            match='$edges: (n1)-[r]->(n2), $qualifiers: (r)-[q {label: ql}]->(qn2)',
            where='n1=$NODE',
            opt='$labels: (ql)-[:`%s`]->(qllabel)' % KG_LABELS_LABEL,
            owhere='$LANG="any" or kgtk_lqstring_lang(qllabel)=$LANG',
            opt2='$labels: (qn2)-[:`%s`]->(qn2label)' % KG_LABELS_LABEL,
            owhere2='$LANG="any" or kgtk_lqstring_lang(qn2label)=$LANG',
            opt3='$descriptions: (qn2)-[r:`%s`]->(qd)' % KG_DESCRIPTIONS_LABEL,
            owhere3='$LANG="any" or kgtk_lqstring_lang(qd)=$LANG',
            ret='r as id, ' +
                'n1 as node1, ' +
                'q as qual_id, ' +
                'q.label as qual_relationship, ' +
                'qn2 as qual_node2, ' +
                'qllabel as qual_relationship_label, ' +
                'qn2label as qual_node2_label, ' +
                'qd as qual_node2_description',
            order='r, q.label, qn2, q, qllabel, qn2label, qd',  # For better performance with LIMIT, sort in caller.
            limit='$LIMIT'
        )

    def RB_NODE_EDGE_QUALIFIERS_BY_EDGE_ID_QUERY(self):
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.get_node_edge_qualifiers()'.
            Given parameter 'NODE' retrieve all edges that have 'EDGE_ID' as their edge ID
            and then all qualifier edges for all such base edges found.  For each
            qualifier edge return information similar to what 'NODE_EDGES_QUERY' returns
            for base edges.
            """,
            inputs=('edges', 'qualifiers', 'labels', 'descriptions'),
            match='$edges: (n1)-[r]->(n2), $qualifiers: (r)-[q {label: ql}]->(qn2)',
            where='r=$EDGEID',
            opt='$labels: (ql)-[:`%s`]->(qllabel)' % KG_LABELS_LABEL,
            owhere='$LANG="any" or kgtk_lqstring_lang(qllabel)=$LANG',
            opt2='$labels: (qn2)-[:`%s`]->(qn2label)' % KG_LABELS_LABEL,
            owhere2='$LANG="any" or kgtk_lqstring_lang(qn2label)=$LANG',
            opt3='$descriptions: (qn2)-[r:`%s`]->(qd)' % KG_DESCRIPTIONS_LABEL,
            owhere3='$LANG="any" or kgtk_lqstring_lang(qd)=$LANG',
            ret='r as id, ' +
                'n1 as node1, ' +
                'q as qual_id, ' +
                'q.label as qual_relationship, ' +
                'qn2 as qual_node2, ' +
                'qllabel as qual_relationship_label, ' +
                'qn2label as qual_node2_label, ' +
                'qd as qual_node2_description',
            order='r, q.label, qn2, q, qllabel, qn2label, qd',  # For better performance with LIMIT, sort in caller.
            limit='$LIMIT'
        )

    def RB_NODE_INVERSE_EDGES_QUERY(self, node: str, lang: str):
        return self.kapi.get_query(
            doc="""
                   Create the Kypher query used by 'BrowserBackend.rb_get_node_inverse_edges()'.
                   Given parameter 'NODE' retrieve all edges that have 'NODE' as their node2.
                   Additionally retrieve descriptive information for all relationship labels.
                   Additionally retrieve descriptive information for all node2's such as their
                   label, and optionally any images and fanouts.  Parameter 'LANG' controls
                   the language for retrieved labels.
                   Return edge 'id', 'label', 'node2', as well as node2's 'node2_label'
                   and label's 'label_label'.

                   """,
            name=f'rb_node_inverse_edges_query_{node}_{lang}',
            inputs=('edges', 'labels', 'descriptions', 'datatypes'),
            match='$edges: (n1)-[r {label: rl}]->(n2)',
            where=f'n2="{node}"',
            opt='$labels: (rl)-[:`%s`]->(llabel)' % KG_LABELS_LABEL,
            owhere=f'"{lang}"="any" or kgtk_lqstring_lang(llabel)="{lang}"',
            opt2='$labels: (n1)-[:`%s`]->(n1label)' % KG_LABELS_LABEL,
            owhere2=f'"{lang}"="any" or kgtk_lqstring_lang(n1label)="{lang}"',
            opt3='$descriptions: (n1)-[r:`%s`]->(n1desc)' % KG_DESCRIPTIONS_LABEL,
            owhere3=f'"{lang}"="any" or kgtk_lqstring_lang(n1desc)="{lang}"',
            opt4='$datatypes: (rl)-[:`%s`]->(rlwdt)' % KG_DATATYPES_LABEL,
            ret='r as id, ' +
                'n1 as node1, ' +
                'r.label as relationship, ' +
                'n2 as node2, ' +
                'llabel as relationship_label, ' +
                'n1 as target_node, ' +
                'n1label as target_label, ' +
                'n1desc as target_description, ' +
                'rlwdt as wikidatatype',
            order='r.label, n2, r, llabel, n1label, n1desc'
        )

    def RB_NODE_INVERSE_EDGE_QUALIFIERS_QUERY(self, node: str, lang: str):
        return self.kapi.get_query(
            doc="""
                   Create the Kypher query used by 'BrowserBackend.get_node_inverse_edge_qualifiers()'.
                   Given parameter 'NODE' retrieve all edges that have 'NODE' as their node2
                   and then all qualifier edges for all such base edges found.  For each
                   qualifier edge return information similar to what 'NODE_EDGES_QUERY' returns
                   for base edges.
                   """,
            name=f'rb_node_inverse_edge_qualifiers_query_{node}_{lang}',
            inputs=('edges', 'qualifiers', 'labels', 'descriptions'),
            match='$edges: (n1)-[r]->(n2), $qualifiers: (r)-[q {label: ql}]->(qn2)',
            where=f'n2="{node}"',
            opt='$labels: (ql)-[:`%s`]->(qllabel)' % KG_LABELS_LABEL,
            owhere=f'"{lang}"="any" or kgtk_lqstring_lang(qllabel)="{lang}"',
            opt2='$labels: (qn2)-[:`%s`]->(qn2label)' % KG_LABELS_LABEL,
            owhere2=f'"{lang}"="any" or kgtk_lqstring_lang(qn2label)="{lang}"',
            opt3='$descriptions: (qn2)-[r:`%s`]->(qd)' % KG_DESCRIPTIONS_LABEL,
            owhere3=f'"{lang}"="any" or kgtk_lqstring_lang(qd)="{lang}"',
            ret='r as id, ' +
                'n1 as node1, ' +
                'q as qual_id, ' +
                'q.label as qual_relationship, ' +
                'qn2 as qual_node2, ' +
                'qllabel as qual_relationship_label, ' +
                'qn2label as qual_node2_label, ' +
                'qd as qual_node2_description',
            order='r, q.label, qn2, q, qllabel, qn2label, qd'
        )

    def RB_NODE_CATEGORIES_QUERY(self, node: str, lang: str):
        return self.kapi.get_query(
            doc="""
                   Create the Kypher query used by 'BrowserBackend.rb_get_node_categories()'.
                   Given parameter 'NODE' retrieve all edges that have 'NODE' as their node2
                   under relationship P301.
                   Additionally retrieve descriptive information for all relationship labels.
                   Additionally retrieve descriptive information for all node2's such as their
                   label, and optionally any images and fanouts.  Parameter 'LANG' controls
                   the language for retrieved labels.
                   Return the category `node1`, 'node1_label', and'node1_description'.

                   WARNING! This query may be incorrect, and should be considered a placeholder.

                   """,
            name=f'rb_node_categories_query_{node}_{lang}',
            inputs=('edges', 'labels', 'descriptions'),
            match='$edges: (n1)-[:P301]->(n2)',
            where=f'n2="{node}"',
            opt='$labels: (n1)-[:`%s`]->(n1label)' % KG_LABELS_LABEL,
            owhere=f'"{lang}"="any" or kgtk_lqstring_lang(n1label)="{lang}"',
            opt2='$descriptions: (n1)-[r:`%s`]->(n1desc)' % KG_DESCRIPTIONS_LABEL,
            owhere2=f'"{lang}"="any" or kgtk_lqstring_lang(n1desc)="{lang}"',
            ret='n1 as node1, ' +
                'n1label as node1_label, ' +
                'n1desc as node1_description',
            order='n1, n1label, n1desc'
        )

    def RB_IMAGE_FORMATTER_QUERY(self):
        return self.kapi.get_query(
            doc="""
                   Create the Kypher query used by 'BrowserBackend.rb_get_image_formatter()'.
                   Given parameter 'NODE' retrieve the first edge's node2 value that has 'NODE' as the node1
                   under relationship P1630.
                   Return node2.
                   """,
            inputs='edges',
            match='$edges: (n1)-[:P1630]->(n2)',
            where=f'n1=$NODE',
            ret='n2 as node2 ',
            limit=1
        )

    def RB_SUBPROPERTY_RELATIONSHIPS_QUERY(self):
        return self.kapi.get_query(
            doc="""
                   Create the Kypher query used by 'BrowserBackend.rb_get_subproperty_relationships()'.
                   Return node1 and node2.
                   """,
            inputs=('edges', 'labels'),
            match='$edges: (n1)-[:P1647]->(n2)',
            opt='$labels: (n1)-[:`%s`]->(n1label)' % KG_LABELS_LABEL,
            owhere='$LANG="any" or kgtk_lqstring_lang(n1label)=$LANG',
            ret='n1 as node1, n2 as node2, n1label as node1_label',
        )

    def RB_LANGUAGE_LABELS_QUERY(self):
        where_clause = f'n2=$CODE and isa in ["Q34770", "Q1288568", "Q33742"]'
        return self.kapi.get_query(
            doc="""
                   Create the Kypher query used by 'BrowserBackend.rb_get_language_labels()'.
                   Given parameter 'CODE' retrieve all edges that have 'CODE' as their node2
                   under relationship P424, validated by P31->Q34770 (instance_of language).

                   The validation is needed because P424 (Wikimedia language code) also
                   appears in in other contexts (e.g., Q15156406 (English Wikisource)).

                   However, some languages (Esperanto (Q143) and Armenian (Q8785), for
                   example) are not marked as instance of (P31) language (Q34770).

                   So, we accept instance of modern language (Q1288568) or natural
                   language (Q33742) as alternatives.

                   Alternative approaches include:
                   1) Excluding the items we don't want. e.g. exclude items that
                      are instances of (P31) Wikisource language edition (Q15156455).
                   2) Looking for entries with aliases equal to the language code.
                   3) Looking for entries with matching Identifiers.
                   4) Encouraging Wikidata to consistantly mark languages.

                   Returns the labels for the node1's.
                   Parameter 'LANG' controls the language for retrieved labels.
                   Return the category `node1` and 'node1_label'.
                   """,
            inputs=('edges', 'labels'),
            match='$edges: (isa)<-[:P31]-(n1)-[:P424]->(n2)',
            where=where_clause,
            opt='$labels: (n1)-[:`%s`]->(n1label)' % KG_LABELS_LABEL,
            owhere='$LANG="any" or kgtk_lqstring_lang(n1label)=$LANG',
            ret='n1 as node1, n1label as node1_label',
            order='n1, n1label'
        )

    def GET_CLASS_VIZ_EDGE_QUERY(self):
        match_clause = f'(class)-[{{label: property, graph: n1, edge_type: edge_type}}]->(superclass)'
        return self.kapi.get_query(
            doc="""
                        Query the 'classvizedge' table to fetch the edges for given Qnode
                        """,
            inputs='classvizedge',
            maxcache=MAX_CACHE_SIZE * 10,
            match=match_clause,
            where='n1=$NODE'
        )

    def GET_CLASS_VIZ_NODE_QUERY(self):
        match_clause = f'(class)-[{{graph: n1, instance_count: instance_count, label: label}}]->()'
        return self.kapi.get_query(
            doc="""
                             Query the 'classviznode' table to fetch the edges for given Qnode
                        """,
            inputs='classviznode',
            maxcache=MAX_CACHE_SIZE * 10,
            match=match_clause,
            where='n1=$NODE'
        )

    def GET_PROPERTY_VALUES_COUNT_QUERY(self) -> kapi.KypherQuery:
        """
        This function returns all the properties and their value counts for a Qnode. Helper function
        to identify high cardinatlity properties.
        :param node:
        :return: KypherQuery object
        """
        match_clause = f'claims: (n1)-[eid {{label: property}}]->(), ' \
                       f'datatypes: (property)-[:`%s`]->(rlwdt)' % KG_DATATYPES_LABEL
        where_clause = 'n1=$NODE'

        return self.kapi.get_query(
            doc="""
                    Find property value counts for a Qnode
                 """,
            inputs=('claims', 'labels', 'datatypes'),
            maxcache=MAX_CACHE_SIZE * 10,
            match=match_clause,
            where=where_clause,
            opt='$labels: (property)-[:`%s`]->(llabel)' % KG_LABELS_LABEL,
            owhere='$LANG="any" or kgtk_lqstring_lang(llabel)=$LANG',
            ret='distinct property as node1, count(eid) as node2, rlwdt as wikidatatype, llabel as property_label'
        )

    def RB_NODE_EDGES_CONDITIONAL_QUERY(self):
        where_clause = f'n1=$NODE AND hc_props=$PROPS'
        return self.kapi.get_query(
            doc="""
                    Create the Kypher query used by 'BrowserBackend.rb_get_node_edges()'.
                    Given parameter 'NODE' retrieve all edges that have 'NODE' as their node1, for a list of
                    properties only.
                    Additionally retrieve descriptive information for all relationship labels.
                    Additionally retrieve the node2 descriptions.
                    Parameter 'LANG' controls the language for retrieved labels.
                    Return edge 'id', 'label', 'node2', as well as node2's 'node2_label'
                    and label's 'label_label'.
                    Limit the number of return edges to LIMIT.

                    """,
            inputs=('edges', 'labels', 'descriptions', 'datatypes'),
            match='$edges: (hc_props)-[:kgtk_values]->(rl),'
                  '$edges: (n1)-[r {label: rl}]->(n2)',
            where=where_clause,
            opt='$labels: (rl)-[:`%s`]->(llabel)' % KG_LABELS_LABEL,
            owhere='$LANG="any" or kgtk_lqstring_lang(llabel)=$LANG',
            opt2='$labels: (n2)-[:`%s`]->(n2label)' % KG_LABELS_LABEL,
            owhere2='$LANG="any" or kgtk_lqstring_lang(n2label)=$LANG',
            opt3='$descriptions: (n2)-[r:`%s`]->(n2desc)' % KG_DESCRIPTIONS_LABEL,
            owhere3='$LANG="any" or kgtk_lqstring_lang(n2desc)=$LANG',
            opt4='$datatypes: (rl)-[:`%s`]->(rlwdt)' % KG_DATATYPES_LABEL,
            ret='r as id, ' +
                'n1 as node1, ' +
                'r.label as relationship, ' +
                'n2 as node2, ' +
                'llabel as relationship_label, ' +
                'n2 as target_node, ' +
                'n2label as target_label, ' +
                'n2desc as target_description, ' +
                'rlwdt as wikidatatype',
            order='r.label, n2, r, llabel, n2label, n2desc',  # For better performance with LIMIT, sort in caller.
            limit='$LIMIT'
        )

    def RB_NODE_EDGES_ONE_PROPERTY_WITH_QUALIFIERS_QUERY(self,
                                                         node: str,
                                                         property: str,
                                                         lang: str,
                                                         skip: int,
                                                         limit: int,
                                                         sort_order: str,
                                                         qualifier_property: str,
                                                         sort_by: str,
                                                         is_sort_by_quantity: bool):

        where_clause = f'n1="{node}" AND rl="{property}"'
        if qualifier_property is None:
            optional_qualifier_where_clause = "1=1"
        else:
            optional_qualifier_where_clause = f'ql="{qualifier_property}"'

        if is_sort_by_quantity:
            order_clause = f'cast({sort_by}, float) {sort_order}'
        else:
            order_clause = f'{sort_by} {sort_order}'
        return self.kapi.get_query(
            doc="""
                    Create the Kypher query used by 'BrowserBackend.rb_get_node_edges()'.
                    Given parameter 'NODE' retrieve all edges that have 'NODE' as their node1 for a given property.
                    Additionally retrieve descriptive information for all relationship labels.
                    Additionally retrieve the node2 descriptions.
                    Parameter 'LANG' controls the language for retrieved labels.
                    Return edge 'id', 'label', 'node2', as well as node2's 'node2_label'
                    and label's 'label_label'.
                    Limit the number of return edges to LIMIT.

                    """,
            inputs=('edges', 'labels', 'descriptions', 'datatypes', 'qualifiers'),
            match='$edges: (n1)-[r {label: rl}]->(n2)',
            where=where_clause,
            opt='$labels: (rl)-[:label]->(llabel)',
            owhere=f'"{lang}"="any" or kgtk_lqstring_lang(llabel)="{lang}"',
            opt2='$labels: (n2)-[:label]->(n2label)',
            owhere2=f'"{lang}"="any" or kgtk_lqstring_lang(n2label)="{lang}"',
            opt3='$descriptions: (n2)-[r:description]->(n2desc)',
            owhere3=f'"{lang}"="any" or kgtk_lqstring_lang(n2desc)="{lang}"',
            opt4='$datatypes: (rl)-[:datatype]->(rlwdt)',
            opt5='$qualifiers: (r)-[q {label: ql}]->(qn2)',
            owhere5=optional_qualifier_where_clause,
            opt6='$labels: (ql)-[:label]->(qllabel)',
            owhere6=f'"{lang}"="any" or kgtk_lqstring_lang(qllabel)="{lang}"',
            opt7='$labels: (qn2)-[:label]->(qn2label)',
            owhere7=f'"{lang}"="any" or kgtk_lqstring_lang(qn2label)="{lang}"',
            ret='distinct r as id, ' +
                'n1 as node1, ' +
                'r.label as relationship, ' +
                'n2 as node2, ' +
                'llabel as relationship_label, ' +
                'n2 as target_node, ' +
                'n2label as target_label, ' +
                'n2desc as target_description, ' +
                'rlwdt as wikidatatype',
            limit=f"{limit}",
            skip=skip,
            order=order_clause
        )

    def GET_RB_NODE_EDGE_QUALIFIERS_IN_QUERY(self):
        """This code generates a new name for each query, thus
        rendering the query cache ineffective and filled with junk.

        The conversion applied to `id_list` does not take into
        consideration that Python and SQL are lilely to have
        different approaches to strings with embedded quotes.
        Fortunately, we do not expect embedded quotes in the
        id_list.
        """
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.get_node_edge_qualifiers_in()'.
            Given parameter 'ID_LIST' retrieve all edges that have their ID in 'ID_LIST'
            and then all qualifier edges for all such base edges found.  For each
            qualifier edge return information similar to what 'NODE_EDGES_QUERY' returns
            for base edges.

            Do not supply a name for these queries.
            """,
            inputs=('edges', 'qualifiers', 'labels', 'descriptions'),
            match='$edges: (props)-[:kgtk_values]->(r),'
                  '$edges: (n1)-[r]->(n2), '
                  '$qualifiers: (r)-[q {label: ql}]->(qn2)',
            # where='r in [' + ", ".join([repr(id_value) for id_value in id_list]) + ']',
            where='props=$PROPS',
            opt='$labels: (ql)-[:`%s`]->(qllabel)' % KG_LABELS_LABEL,
            owhere='$LANG="any" or kgtk_lqstring_lang(qllabel)=$LANG',
            opt2='$labels: (qn2)-[:`%s`]->(qn2label)' % KG_LABELS_LABEL,
            owhere2='$LANG="any" or kgtk_lqstring_lang(qn2label)=$LANG',
            opt3='$descriptions: (qn2)-[r:`%s`]->(qd)' % KG_DESCRIPTIONS_LABEL,
            owhere3='$LANG="any" or kgtk_lqstring_lang(qd)=$LANG',
            ret='r as id, ' +
                'n1 as node1, ' +
                'q as qual_id, ' +
                'q.label as qual_relationship, ' +
                'qn2 as qual_node2, ' +
                'qllabel as qual_relationship_label, ' +
                'qn2label as qual_node2_label, ' +
                'qd as qual_node2_description',
            order='r, q.label, qn2, q, qllabel, qn2label, qd',
            limit="$LIMIT"
        )

    def GET_INCOMING_EDGES_COUNT_QUERY(self, properties_to_hide: str) -> kapi.KypherQuery:
        """
        This function returns all the incoming edges counts per property for a Qnode.
        :param node: Qnode
        :return: KypherQuery object
        """
        match_clause = f'claims: ()-[eid {{label: property}}]->(node)'
        where_clause = f'node=$NODE and NOT property IN [{properties_to_hide}]'
        return self.kapi.get_query(
            doc="""
                    Find incoming properties for the qnode and their counts
                 """,
            inputs=('claims', 'labels'),
            maxcache=MAX_CACHE_SIZE * 10,
            match=match_clause,
            where=where_clause,
            opt='$labels: (property)-[:`%s`]->(llabel)' % KG_LABELS_LABEL,
            owhere='$LANG="any" or kgtk_lqstring_lang(llabel)=$LANG',
            ret='distinct property as node1, count(eid) as node2, llabel as property_label'
        )

    def RB_NODE_RELATED_EDGES_ONE_PROPERTY_QUERY(self):
        where_clause = f'n2=$NODE AND rl=$PROPERTY'
        return self.kapi.get_query(
            doc="""
                    Create the Kypher query used by 'BrowserBackend.rb_get_node_one_property_related_edges()'.
                    Given parameter 'NODE' retrieve all edges that have 'NODE' as their node2 for a given property.
                    Additionally retrieve descriptive information for all relationship labels.
                    Parameter 'LANG' controls the language for retrieved labels.
                    Return edge 'id', 'label', 'node1', as well as node1's 'node1_label'
                    and label's 'label_label'.
                    Limit the number of return edges to LIMIT.

                    """,
            inputs=('edges', 'labels'),
            match='$edges: (n1)-[r {label: rl}]->(n2)',
            where=where_clause,
            opt='$labels: (rl)-[:`%s`]->(llabel)' % KG_LABELS_LABEL,
            owhere='$LANG="any" or kgtk_lqstring_lang(llabel)=$LANG',
            opt2='$labels: (n1)-[:`%s`]->(n1label)' % KG_LABELS_LABEL,
            owhere2='$LANG="any" or kgtk_lqstring_lang(n1label)=$LANG',
            ret='r as id, ' +
                'n1 as node1, ' +
                'r.label as relationship, ' +
                'llabel as relationship_label, ' +
                'n1label as node1_label',
            limit='$LIMIT',
            skip='$SKIP'
        )

    def RB_NODE_RELATED_EDGES_MULTIPLE_PROPERTIES_QUERY(self):
        where_clause = f'n2=$NODE AND lc_props=$PROPS'
        return self.kapi.get_query(
            doc="""
                    Create the Kypher query used by 'BrowserBackend.rb_get_node_one_property_related_edges()'.
                    Given parameter 'NODE' retrieve all edges that have 'NODE' as their node2 for low cardinality
                    properies. Additionally retrieve descriptive information for all relationship labels.
                    Parameter 'LANG' controls the language for retrieved labels.
                    Return edge 'id', 'label', 'node1', as well as node1's 'node1_label'
                    and label's 'label_label'.
                    Limit the number of return edges to LIMIT.

                    """,
            inputs=('edges', 'labels'),
            match='$edges: (lc_props)-[:kgtk_values]->(rl),'
                  '$edges: (n1)-[r {label: rl}]->(n2)',
            where=where_clause,
            opt='$labels: (rl)-[:`%s`]->(llabel)' % KG_LABELS_LABEL,
            owhere='$LANG="any" or kgtk_lqstring_lang(llabel)=$LANG',
            opt2='$labels: (n1)-[:`%s`]->(n1label)' % KG_LABELS_LABEL,
            owhere2='$LANG="any" or kgtk_lqstring_lang(n1label)=$LANG',
            ret='r as id, ' +
                'n1 as node1, ' +
                'r.label as relationship, ' +
                'llabel as relationship_label, ' +
                'n1label as node1_label',
            limit='$LIMIT'
        )

    def RB_GET_EVENTS_AND_SCORES_BY_DATE(self, limit: int) -> kapi.KypherQuery:
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.rb_get_events_and_scores_by_date()'.
            """,
            name='RB_GET_EVENTS_AND_SCORES_BY_DATE',
            inputs=('edges', 'label', 'qualifiers'),
            maxcache=MAX_CACHE_SIZE * 10000,
            match='''
                $edges: (sentence_id)-[:P31]->(:Q00_venice_sentence),
                $edges: (sentence_id)-[:P585]->(sentence_datetime),
                $edges: (sentence_id)-[quality_type]->(quality_id),
                $qualifiers: (quality_type)-[:P1181]->(quality_score)
            ''',
            where='''
                quality_id in [
                    'Q00_authority',
                    'Q00_subversion',
                    'Q00_fairness',
                    'Q00_cheating',
                    'Q00_care',
                    'Q00_harm',
                    'Q00_loyalty',
                    'Q00_betrayal',
                    'Q00_sanctity',
                    'Q00_degradation',
                    'Q00_concreteness'
                ]
            ''',
            ret='''
                sentence_id,
                sentence_datetime,
                quality_id,
                quality_score
            ''',
            limit= "$LIMIT"
        )

    def RB_GET_EMOTIONS_WITH_P585(self,limit: int) -> kapi.KypherQuery:
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.rb_get_emotions_with_p585()'.
            """,
            name='RB_GET_EMOTIONS_WITH_P585',
            inputs=('edges', 'qualifiers'),
            maxcache=MAX_CACHE_SIZE * 10000,
            match='''
                $edges: (document_id)-[:P31]->(:Q00_venice_doc),
                $edges: (document_id)-[:P585]->(document_datetime),
                $edges: (document_id)-[quality_type]->(emotion_id),
                $qualifiers: (quality_type)-[:P1181]->(emotion_score)
            ''',
            where='''
                emotion_id in [
                    'Q00_anticipation',
                    'Q00_love',
                    'Q00_joy',
                    'Q00_pessimism',
                    'Q00_optimism',
                    'Q00_sadness',
                    'Q00_disgust',
                    'Q00_anger',
                    'Q00_surprise',
                    'Q00_fear',
                    'Q00_trust'
                ]
            ''',
            ret='''
                document_id,
                document_datetime,
                emotion_id,
                emotion_score
            ''',
            limit= "$LIMIT"
        )

    def RB_GET_EMOTIONS_WITH_P585_FOR_NODE(self, node: str,limit: int) -> kapi.KypherQuery:
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.rb_get_emotions_with_p585_for_node()'.
            """,
            name='RB_GET_EMOTIONS_WITH_P585_FOR_NODE',
            inputs=('edges', 'qualifiers'),
            maxcache=MAX_CACHE_SIZE * 10000,
            match='''
                $edges: (participant_id)-[:P1344]->(event_id),
                $edges: (event_id)-[:P00_venice_from_sentence]->(sentence_id),
                $edges: (sentence_id)-[:P00_venice_from_doc]->(document_id),
                $edges: (document_id)-[:P31]->(:Q00_venice_doc),
                $edges: (document_id)-[:P585]->(document_datetime),
                $edges: (document_id)-[quality_type]->(emotion_id),
                $qualifiers: (quality_type)-[:P1181]->(emotion_score)
            ''',
            where='''
                emotion_id in [
                    'Q00_anticipation',
                    'Q00_love',
                    'Q00_joy',
                    'Q00_pessimism',
                    'Q00_optimism',
                    'Q00_sadness',
                    'Q00_disgust',
                    'Q00_anger',
                    'Q00_surprise',
                    'Q00_fear',
                    'Q00_trust'
                ] and participant_id=$NODE
            ''',
            ret='''
                document_id,
                document_datetime,
                emotion_id,
                emotion_score
            ''',
            limit= "$LIMIT"
        )

    def RB_GET_MORAL_FOUNDATIONS_WITH_P585(self, limit: int) -> kapi.KypherQuery:
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.rb_get_moral_foundations_with_p585()'.
            """,
            name='RB_GET_MORAL_FOUNDATIONS_WITH_P585',
            inputs=('edges', 'qualifiers'),
            maxcache=MAX_CACHE_SIZE * 10000,
            match='''
                $edges: (sentence_id)-[:P31]->(:Q00_venice_sentence),
                $edges: (sentence_id)-[:P585]->(sentence_datetime),
                $edges: (sentence_id)-[quality_type]->(quality_id),
                $qualifiers: (quality_type)-[:P1181]->(quality_score)
            ''',
            where='''
                quality_id in [
                    'Q00_authority',
                    'Q00_subversion',
                    'Q00_fairness',
                    'Q00_cheating',
                    'Q00_care',
                    'Q00_harm',
                    'Q00_loyalty',
                    'Q00_betrayal',
                    'Q00_sanctity',
                    'Q00_degradation'
                ]
            ''',
            ret='''
                sentence_id,
                sentence_datetime,
                quality_id,
                quality_score
            ''',
            limit= "$LIMIT"
        )

    def RB_GET_MORAL_FOUNDATIONS_WITH_P585_FOR_NODE(self, node: str, limit: int) -> kapi.KypherQuery:
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.rb_get_moral_foundations_with_p585_for_node()'.
            """,
            name='RB_GET_MORAL_FOUNDATIONS_WITH_P585_FOR_NODE',
            inputs=('edges', 'qualifiers'),
            maxcache=MAX_CACHE_SIZE * 10000,
            match='''
                $edges: (participant_id)-[:P1344]->(event_id),
                $edges: (event_id)-[:P00_venice_from_sentence]->(sentence_id),
                $edges: (sentence_id)-[:P31]->(:Q00_venice_sentence),
                $edges: (sentence_id)-[:P585]->(sentence_datetime),
                $edges: (sentence_id)-[quality_type]->(quality_id),
                $qualifiers: (quality_type)-[:P1181]->(quality_score)
            ''',
            where='''
                quality_id in [
                    'Q00_authority',
                    'Q00_subversion',
                    'Q00_fairness',
                    'Q00_cheating',
                    'Q00_care',
                    'Q00_harm',
                    'Q00_loyalty',
                    'Q00_betrayal',
                    'Q00_sanctity',
                    'Q00_degradation'
                ] and participant_id=$NODE
            ''',
            ret='''
                sentence_id,
                sentence_datetime,
                quality_id,
                quality_score
            ''',
            limit= "$LIMIT"
        )

    def RB_GET_MORAL_FOUNDATIONS_AND_CONCRETENESS_WITH_P585(self, limit: int) -> kapi.KypherQuery:
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.rb_get_moral_foundations_and_concreteness_with_p585()'.
            """,
            name='RB_GET_MORAL_FOUNDATIONS_AND_CONCRETENESS_WITH_P585',
            inputs=('edges', 'qualifiers'),
            maxcache=MAX_CACHE_SIZE * 10000,
            match='''
                $edges: (sentence_id)-[:P31]->(:Q00_venice_sentence),
                $edges: (sentence_id)-[:P585]->(sentence_datetime),
                $edges: (sentence_id)-[quality_type]->(quality_id),
                $qualifiers: (quality_type)-[:P1181]->(quality_score)
            ''',
            where='''
                quality_id in [
                    'Q00_authority',
                    'Q00_subversion',
                    'Q00_fairness',
                    'Q00_cheating',
                    'Q00_care',
                    'Q00_harm',
                    'Q00_loyalty',
                    'Q00_betrayal',
                    'Q00_sanctity',
                    'Q00_degradation',
                    'Q00_concreteness'
                ]
            ''',
            ret='''
                sentence_id,
                sentence_datetime,
                quality_id,
                quality_score
            ''',
            limit= "$LIMIT"
        )

    def RB_GET_MESSAGES(self, limit: int) -> kapi.KypherQuery:
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.rb_get_messages()'.
            """,
            name='RB_GET_MESSAGES',
            inputs=('edges'),
            maxcache=MAX_CACHE_SIZE * 10000,
            match='''
                $edges: (document_id)-[:P31]->(:Q00_venice_doc),
                $edges: (document_id)-[:P00_venice_document_text]->(document_text)
            ''',
            ret='''
                document_id,
                document_text
            ''',
            limit= "$LIMIT"
        )

    def RB_GET_SENTENCES_FOR_PARTICIPANT(self, participant_id: str, limit: int) -> kapi.KypherQuery:
        return self.kapi.get_query(
            doc="""
            Create the Kypher query used by 'BrowserBackend.rb_get_messages()'.
            """,
            name='RB_GET_SENTENCES_FOR_PARTICIPANT',
            inputs=('edges', 'label', 'qualifiers'),
            maxcache=MAX_CACHE_SIZE * 10000000,
            match='''
                $edges: (participant_id)-[:P1344]->(event_id),
                $edges: (event_id)-[:P585]->(event_date),
                $label: (event_id)-[:label]->(event_text),
                $edges: (event_id)-[:P00_venice_from_sentence]->(sentence_id),
                $label: (sentence_id)-[:label]->(sentence_text),
                $edges: (sentence_id)-[moral_foundation_type]->(moral_foundation_id),
                $qualifiers: (moral_foundation_type)-[:P1181]->(moral_foundation_score),
                $edges: (sentence_id)-[:P00_venice_from_doc]->(document_id),
                $edges: (document_id)-[:P585]->(document_date)
            ''',
            where='''
                moral_foundation_id in [
                    'Q00_authority',
                    'Q00_subversion',
                    'Q00_fairness',
                    'Q00_cheating',
                    'Q00_care',
                    'Q00_harm',
                    'Q00_loyalty',
                    'Q00_betrayal',
                    'Q00_sanctity',
                    'Q00_degradation'
                ] and participant_id=$participant_id
            ''',
            ret='''
                participant_id,
                document_id,
                document_date,
                sentence_id,
                sentence_text,
                moral_foundation_id,
                moral_foundation_score,
                event_id,
                event_date,
                event_text
            ''',
            limit='$LIMIT'
        )

    def VENICE_DOCUMENT(self, document_id: str) -> kapi.KypherQuery:
        return self.kapi.get_query(
            doc="""
            Show the full document as it appears in the KG
            """,
            name='VENICE_DOCUMENT',
            inputs=('edges', 'label'),
            maxcache=MAX_CACHE_SIZE * 100,
            match='''
                $edges: (document_id)-[:P31]->(document_instance_of),
                $edges: (document_id)-[:P00_venice_document_text]->(document_text),
                $label: (document_id)-[:label]->(document_label)
            ''',
            opt1='''
                $edges: (document_id)-[:P00_venice_contain_sentence]->(sentence_id),
                $edges: (sentence_id)-[:P31]->(sentence_instance_of),
                $edges: (sentence_id)-[:P585]->(sentence_datetime),
                $edges: (sentence_id)-[:P00_venice_data_source]->(sentence_data_source),
                $label: (sentence_id)-[:label]->(sentence_text)
            ''',
            opt2='''
                $edges: (document_id)-[:P00_venice_emo]->(emotion_id),
                $label: (emotion_id)-[:label]->(emotion_text)
            ''',
            opt3='''
                $edges: (document_id)-[:P585]->(document_datetime)
            ''',
            where='''
                document_id=$document_id
            ''',
            ret='''
                document_id,
                document_text,
                document_label,
                document_instance_of,
                document_datetime,
                sentence_id,
                sentence_text,
                sentence_instance_of,
                sentence_data_source,
                sentence_datetime,
                emotion_id,
                emotion_text
            '''
        )
