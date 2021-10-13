#!/bin/bash
set -e

./venice/01-PREPARE_DATA_FOR_BROWSER.sh
./venice/02-BUILD_THE_GRAPH_CACHE.sh
