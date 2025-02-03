#!/bin/bash

#To add a new direcotry to unit tests, add it to source_dirs array. 
#Add the source (folder containing src and test directories) to the array
source_dirs=("modules/python")

for source_dir in "${source_dirs[@]}"; do
    export PYTHONPATH=$PYTHONPATH:${source_dir}
    export PYTHONPATH=$PYTHONPATH:${source_dir}/src
    python -m unittest discover "${source_dir}/tests"
done
