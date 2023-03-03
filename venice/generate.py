import os
import sys
import pathlib
import papermill as pm
from datetime import datetime
from kgtk.functions import kgtk, kypher
from kgtk.configure_kgtk_notebooks import ConfigureKGTK


# Check if user passed in a file
if len(sys.argv) <= 1:
    print('Err, please provide input file arg..')
    print('For example: `generate.py <input_file.tsv>`')
    sys.exit()


# Get input file path
input_path = sys.argv[1]


# Get current directory
current_dir = os.getcwd()


# Create temporary directory
temp_dir = os.path.join(current_dir, 'temp')
os.system('rm -rf {}'.format(temp_dir))
os.makedirs(temp_dir, exist_ok=False)


# Create output directory
date = datetime.now().strftime('%Y_%m_%d')
output_dir = os.path.join(current_dir, 'output/{}'.format(date))
os.system('rm -rf {}'.format(output_dir))
os.makedirs(output_dir, exist_ok=False)


# Configure KGTK
ck = ConfigureKGTK(['all'])
ck.configure_kgtk(
    input_graph_path=current_dir,
    output_path=output_dir,
    project_name='venice',
)


# Execute script 01-partition to partition the data
pm.execute_notebook(
    '{}/{}'.format(current_dir, 'utils/01-partition.ipynb'),
    '{}/{}'.format(temp_dir, '01-partition.output.ipynb'),
    parameters=dict(
        wikidata_input_path=input_path,
        wikidata_parts_path=temp_dir,
        temp_folder_path=temp_dir,
        gzip_command='gzip',
        use_mgzip='False',
    )
)


# Calculate pagerank
kgtk('''
  --debug graph-statistics
  -i {}/claims.tsv.gz
  -o {}/metadata.pagerank.undirected.tsv.gz
  --compute-pagerank True
  --compute-hits False
  --page-rank-property Pundirected_pagerank
  --output-degrees False
  --output-pagerank True
  --output-hits False
  --output-statistics-only
  --undirected True
  --log-file {}/metadata.pagerank.undirected.summary.txt
'''.format(*[temp_dir]*3))


# Execute script 02-create-db to create the sqlite3.db file
pm.execute_notebook(
    '{}/{}'.format(current_dir, 'utils/02-create-db.ipynb'),
    '{}/{}'.format(temp_dir, '02-create-db.output.ipynb'),
    kernel_name='python3',
    parameters=dict(
        input_path=temp_dir,
        output_path=output_dir,
        project_name='venice',
        create_class_viz='no',
        create_db='yes',
        create_es='no',
    )
)
