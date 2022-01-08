#!/usr/bin/env python
# coding: utf-8

# # KGTK Browser Cache Setup

# This note book will create the SQLite DB Cache and the required indices for KGTK Browser.
#
# The required input parameters are:
# - input_path: Path where the following files should be present
#     - labels.en.tsv.gz
#     - aliases.en.tsv.gz
#     - descriptions.en.tsv.gz
#     - claims.tsv.gz
#     - metadata.types.tsv.gz
#     - qualifiers.tsv.gz
#     - metadata.pagerank.undirected.tsv.gz
# - output_path: Output path
# - project_name: folder inside the `output_path` where the required files and cache will be created
#
# **Cache file location:** `<output_path>/<project_name>/temp.<project_name>/wikidata.sqlite3.db`

# In[1]:


import os
import pandas as pd
from kgtk.configure_kgtk_notebooks import ConfigureKGTK
import kgtk.kypher.api as kapi


# In[2]:


input_path = "./graphs/"
output_path = "/data/kgtk-browser/"

project_name = "venice"

files = 'label,pagerank_undirected,alias,description,claims,datatypes,qualifiers'


# In[3]:


files = files.split(',')


# In[4]:


ck = ConfigureKGTK(files)
ck.configure_kgtk(input_graph_path=input_path,
                  output_path=output_path,
                  project_name=project_name)


# In[5]:


ck.print_env_variables()


# ## Load the files into cache

# In[6]:


ck.load_files_into_cache()


# ## Define the Kypher API

# In[7]:


_kapi2 = kapi.KypherApi(graphcache=os.environ['STORE'], loglevel=1, index='auto',
                      maxresults=100, maxcache=0)


# ## Create a file with `label`, `undirected_pagerank` and `description`

# In[8]:


os.system('kgtk query --gc $STORE     -i label pagerank_undirected description    --match \'label: (qnode)-[l]->(y), pagerank: (qnode)-[:Pundirected_pagerank]->(pr)\'     --opt \'description: (qnode)-[:description]->(d)\'     --return \'qnode as node1, l.label as label, y as node2, upper(y) as `node2;upper`, pr as `node1;pagerank`, ifnull(d, "") as `node1;description`\'     --order-by \'qnode\'     -o $OUT/label_pagerank_undirected_description.tsv.gz')


# ### Load this file into cache as well

# In[9]:


os.system('kgtk query --gc $STORE -i $OUT/label_pagerank_undirected_description.tsv.gz --as l_d_pgr_ud --limit 10')


# ## Create the required indices

# In[10]:


os.system('kgtk --debug query -i l_d_pgr_ud --idx node1 "node2;upper" label text:node2//name=ldpgridx --gc $STORE --limit 5')


# In[11]:


os.system('kgtk --debug query -i label --idx label --gc $STORE --limit 5')


# In[12]:


os.system('kgtk --debug query -i alias --idx label --gc $STORE --limit 5')


# In[13]:


os.system('kgtk --debug query -i description --idx id --gc $STORE --limit 5')


# In[14]:


os.system('kgtk --debug query -i claims --idx label node1 node2 id --gc $STORE --limit 5')


# In[15]:


os.system('kgtk --debug query -i datatypes --idx label node1 --gc $STORE --limit 5')


# In[16]:


os.system('kgtk --debug query -i qualifiers --idx node2 node1 label --gc $STORE --limit 5')


# ## Take a look at cache file content

# In[17]:


os.system('kgtk query --gc $STORE --show-cache ')


# ## Define a function to do a `textmatch` search

# In[18]:


def text_search_labels(search_text, limit=20):
    text_search_labels_query = _kapi2.get_query(
        doc="Doc string here",
        name=f"text_search_labels_{search_text}",
        inputs='l_d_pgr_ud',
        match='l_d_pgr_ud: (qnode)-[l:label]->(y)',
        where=f'textmatch(y, "{search_text}")',
       ret='distinct qnode as node1, y as label, 10*matchscore(y) as score, cast(l.`node1;pagerank`, float) as prank, l.`node1;description` as description',
       order='score*prank',
       limit=limit
    )
    results =  list([list(x) for x in text_search_labels_query.execute()])
    df = pd.DataFrame(results, columns=['node1', 'label', 'score', 'pagerank', 'description'])
    print(len(df))
    return df



# In[19]:


#text_search_labels('arn sch')


# ## Define a function to search for Qnodes Exactly

# In[20]:


def exact_search_items(search_text, limit=20):
    search_text = search_text.upper()
    text_search_labels_query =  _kapi2.get_query(
    doc="""
    Create the Kypher query used by 'BrowserBackend.get_node_labels()'
    for case_independent searches.
    Given parameters 'NODE' and 'LANG' retrieve labels for 'NODE' in
    the specified language (using 'any' for 'LANG' retrieves all labels).
    Return distinct 'node1', 'node_label' pairs as the result (we include
    'NODE' as an output to make it easier to union result frames).
    """,
    name=f'exact_search_items{search_text}',
    inputs='l_d_pgr_ud',
    match='l_d_pgr_ud: (n)-[r:label]->(l)',
    where=f'n="{search_text}"',
    ret='distinct n as node1, l as node_label, r.`node1;description` as description',
)
    results =  list([list(x) for x in text_search_labels_query.execute()])
    df = pd.DataFrame(results, columns=['node1', 'label', 'description'])
    print(len(df))
    return df



# In[21]:


#exact_search_items('q30')


# In[22]:


#exact_search_items('Q140')


# ## Define a function to search labels Exactly

# In[23]:


def exact_search_labels(search_text, limit=20):
    search_text = f"'{search_text.upper()}'@EN"
    text_search_labels_query =  _kapi2.get_query(
    doc="""
     Exact Match case insensitive query
    """,
    name=f'exact_search_labels{search_text}',
    inputs='l_d_pgr_ud',
    match=f'l_d_pgr_ud: (n)-[r:label]->(l)',
    where=f'r.`node2;upper`="{search_text}"',
    ret='distinct n as node1, l as node_label, cast("-1.0", float) as score, cast(r.`node1;pagerank`, float) as prank, r.`node1;description` as description',
    order='score*prank',
    limit=limit
)
    results =  list([list(x) for x in text_search_labels_query.execute()])
    df = pd.DataFrame(results, columns=['node1', 'label', 'score', 'prank', 'description'])
    print(len(df))
    return df


# In[24]:


#exact_search_labels('canada')


# ## Define a function to fo a `textlike` search

# In[25]:


def text_like_search_labels(search_text, limit=20):
    search_label = f"%{'%'.join(search_text.split(' '))}%"
    print(search_text)
    text_search_labels_query = _kapi2.get_query(
        doc="Doc string here",
        name=f"text_like_search_labels_{search_text}",
        inputs='l_d_pgr_ud',
        match='l_d_pgr_ud: (qnode)-[l:label]->(y)',
        where=f'textlike(y, "{search_label}")',
       ret='distinct qnode as node1, y as label, matchscore(y) as score, cast(l.`node1;pagerank`, float) as prank, l.`node1;description` as description',
       order='score*prank',
       limit=limit
    )
    results =  list([list(x) for x in text_search_labels_query.execute()])
    df = pd.DataFrame(results, columns=['node1', 'label', 'score', 'pagerank', 'description'])
    print(len(df))
    return df



# In[26]:


#text_like_search_labels("fifa group b")
