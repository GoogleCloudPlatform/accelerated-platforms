#!/bin/bash

#To add a new direcotry to coverage tests, add it to coverage_dirs array. 
#Corresponding source (folder containing src and test directories) must be added to .coveragerc in the root dorectory
coverage_dirs=("use-cases/model-fine-tuning-pipeline/data-processing/ray/tests/")

#Add the source (folder containing src and test directories) to PYTHONPATH so the modules are available when you run the tests
source_dirs=("use-cases/model-fine-tuning-pipeline/data-processing/ray/src")

for source_dir in "${source_dirs[@]}"; do
    export PYTHONPATH=$PYTHONPATH:${source_dir}
done

for coverage_dir in "${coverage_dirs[@]}"; do
    python -m coverage run -m unittest discover ${coverage_dir}
done


