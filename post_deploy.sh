#!/bin/bash
set -e


echo -e "\n >>> Running: 01-PREPARE_DATA_FOR_BROWSER.sh \n"

./venice/01-PREPARE_DATA_FOR_BROWSER.sh


echo -e "\n >>> Running: 02-BUILD_THE_GRAPH_CACHE.sh \n"

./venice/02-BUILD_THE_GRAPH_CACHE.py


echo -e "\n >>> Running: 03-PREPARE_PAGERANK.sh \n"

./venice/03-PREPARE_PAGERANK.sh


echo -e "\n >>> all done, timestamp: \n"

echo `date -u`
