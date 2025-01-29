#!/bin/bash

#To add a new direcotry to coverage tests, add it to source_dirs array. 
#Add the source (folder containing src and test directories) to the array
source_dirs=("use-cases/model-fine-tuning-pipeline/data-processing/ray/src")

for source_dir in "${source_dirs[@]}"; do
    export PYTHONPATH=$PYTHONPATH:${source_dir}
    python -m coverage run -m unittest discover "${source_dir}/../tests"
done



