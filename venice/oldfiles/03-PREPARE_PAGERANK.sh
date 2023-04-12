export GRAPHS="./graphs"
export WORKING_FOLDER="./temp"
export KGTK_OPTIONS="--debug"

echo -e "\n*** Sort the claims and qualifiers file on the id column: ***"
time kgtk ${KGTK_OPTIONS} graph-statistics \
    -i ${GRAPHS}/claims.tsv.gz \
    -o ${GRAPHS}/metadata.pagerank.undirected.tsv.gz \
    --compute-pagerank True \
    --compute-hits False \
    --page-rank-property Pundirected_pagerank \
    --use-mgzip True \
    --mgzip-threads 12 \
    --output-degrees False \
    --output-pagerank True \
    --output-hits False \
    --output-statistics-only \
    --undirected True \
    --log-file ${WORKING_FOLDER}/metadata.pagerank.undirected.summary.txt
