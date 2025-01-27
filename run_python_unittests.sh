#!/bin/bash

#Add the source (folder containing src and test directories) to PYTHONPATH so the modules are available when you run the tests
source_dirs=("use-cases/model-fine-tuning-pipeline/data-processing/ray")
#Add the directories containing the unit tests cases to test_dirs array
test_dirs=("use-cases/model-fine-tuning-pipeline/data-processing/ray/tests/")

for source_dir in "${source_dirs[@]}"; do
    export PYTHONPATH=$PYTHONPATH:${source_dir}
done

for test_dir in "${test_dirs[@]}"; do
    python -m unittest ${test_dir}
done
