# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import logging.config
import os

# Configure logging
logging.config.fileConfig("logging.conf")
logger = logging.getLogger("prompt_helper")

if "LOG_LEVEL" in os.environ:
    new_log_level = os.environ["LOG_LEVEL"].upper()
    logger.info(
        f"Log level set to '{new_log_level}' via LOG_LEVEL environment variable"
    )
    logger.setLevel(new_log_level)


# user_query can be None if only image is passed as an argument
def prompt_generation(search_result, user_query=None):
    # Option 1: Emphasize User Intent
    prompt1 = f"""An online shopper is searching for products.  
    Given their query and a list of initial product recommendations, identify ONLY the TOP 3 products that best match the shopper's intent. 
    Search Query: {user_query}. 
    Product List: 
    {search_result}"""

    # Option 2:  Provide Context and Constraints - works better!
    prompt2 = f"""You are an AI assistant helping an online shopper find the most relevant products.  
    The shopper has submitted a search query, and a preliminary search has returned a list of potential matches. 
    Your task is to refine these results by selecting only the 3 best products from the list without duplicates. 
    Return only the product details in the format as it is in search result. Don't add any additional information
    Search Query: {user_query}. 
    Product List: 
    {search_result}"""

    # Option 3:  Be More Directive
    prompt3 = f"""Rerank the following product recommendations to best satisfy an online shopper's search query. 
    Return only the top 3 most relevant products. 
    Search Query: {user_query}. 
    Product List: 
    {search_result}"""

    # Option 4:  Provide Context and Constraints - works better! + Product id as well
    prompt4 = f"""You are an AI assistant helping an online shopper find the most relevant products.  
    The shopper has submitted a search query, and a preliminary search has returned a list of potential matches. 
    Your task is to refine these results by selecting only the 3 best products from the list without duplicates. 
    Return complete product details in a readable format as it is in search result.
    Result should be numbered.Don't add any additional information to the result.
    Search Query: {user_query}. 
    Product List: 
    {search_result}"""

    return prompt2
