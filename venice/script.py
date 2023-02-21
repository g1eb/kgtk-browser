# Import the main kgtk package
from kgtk.functions import kgtk, kypher
from kgtk.configure_kgtk_notebooks import ConfigureKGTK
import os
import papermill as pm
# Minimal KGTK configuration for this example
ck = ConfigureKGTK(['all'])
ck.configure_kgtk(
    graph_cache_path='wikidata.sqlite3.db',
    output_path='./output',
    project_name='kgtk-tutorial',
)
pm.execute_notebook(
    "kgtk-notebooks/use-cases/create_wikidata/partition-wikidata.ipynb",
    os.environ["TEMP"] + "/partition-wikidata.out.ipynb",
    kernel_name='python3',
    parameters=dict(
        wikidata_input_path = os.environ["all"],
        wikidata_parts_path = os.environ["OUT"] + "/parts",
        temp_folder_path = os.environ["OUT"] + "/parts/temp",
        sort_extras = "--buffer-size 30% --temporary-directory $OUT/parts/temp",
        verbose = False,
        gzip_command = 'gzip'
    )
)
kgtk("""
  --debug graph-statistics
  -i output/kgtk-tutorial/parts/claims.tsv.gz
  -o output/kgtk-tutorial/parts/metadata.pagerank.undirected.tsv.gz
  --compute-pagerank True
  --compute-hits False
  --page-rank-property Pundirected_pagerank
  --output-degrees False
  --output-pagerank True
  --output-hits False
  --output-statistics-only
  --undirected True
  --log-file ./output/kgtk-tutorial/temp.kgtk-tutorial/metadata.pagerank.undirected.summary.txt
""")
pm.execute_notebook(
    "kgtk-notebooks/use-cases/create_wikidata/KGTK-Query-Text-Search-Setup.ipynb",
    os.environ["TEMP"] + "/KGTK-Query-Text-Search-Setup.out.ipynb",
    kernel_name="python3",
    parameters=dict(
        input_path = 'output/kgtk-tutorial/parts',
        output_path = 'graph-cache-db/',
        project_name = 'kgtk-tutorial',
        create_class_viz = 'no',
        create_db = 'yes',
        create_es = 'no',
    )
)
