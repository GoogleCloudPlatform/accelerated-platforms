import pandas as pd
import logging

class DataPrep:

    logger = logging.getLogger(__name__)

    def __init__(self,df,required_cols,filter_null_cols,chunk_size=199):
        self.df = df
        self.required_cols = required_cols
        self.filter_null_cols = filter_null_cols
        self.chunk_size = chunk_size


    def split_dataframe(self):
        self.logger.info(f"Splitting dataframe into chunk size of '{self.chunk_size}'")
        chunks = list()
        num_chunks = len(self.df) // self.chunk_size + 1
        for i in range(num_chunks):
            chunks.append(df[i * self.chunk_size : (i + 1) * self.chunk_size])
        return chunks
    
    def update_dataframe(self):
        
        self.df = self.df[self.required_cols]
        self.logger.info(f"Original dataset shape: '{self.df.shape}'")
        # Drop rows with null values in specified columns
        self.df.dropna(
            subset=self.filter_null_cols,
            inplace=True,
        )
        self.logger.info(f"After dropping null values: '{self.df.shape}'")
        return self.df