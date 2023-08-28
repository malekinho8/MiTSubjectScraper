# Plots a distribution of a column of interest in a csv.
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os

# 0. Specify constants
NUM_BINS = 40
OUTPUT_FOLDER = 'example_outputs'
# 0.1 Specify any additional filters
filter_grad = True
terms = None # ['Fall']
min_year = 2004
max_year = 2023
min_responses = 1

# 1. Access the contents of the csv of interest
# 1.1 Load the csv file
# 1.1.1 Specify the csv folder location
csv_folder = './course_csv_data/scuffed_csv_files'
# 1.1.2 Specify the csv file name
csv_filename = 'subject_2_scuffed.csv'
# 1.1.3 Make the csv path
csv_path = os.path.join(csv_folder,csv_filename)
# 1.1.4 Load the csv into a DataFrame
df = pd.read_csv(csv_path)
# 1.1.5 Print the columns of the df
print(df.columns)

# 1.2 Filter the df
# 1.2.1 Filter out graduate/undergraduate courses
if filter_grad:
    df = df.loc[df['Level (U or G)'].values == 'G']
    df = df.reset_index()
# 1.2.2 Filter out terms
if terms is not None:
    temp_df = pd.DataFrame()
    for term in terms:
        temp_df = pd.concat([temp_df,df.loc[df['Term'].values == term]])
    df = temp_df
    temp_df = None
# 1.2.3 Filter out data beyond the year range
df = df.loc[df['Year'].values >= min_year]
df = df.loc[df['Year'].values <= max_year]
# 1.2.4 Filter out data that does not satisfy min responses
df = df.loc[df['Number of Respondents'].values >= min_responses]
df.reset_index()

# 2. Specify which column you would like to plot
var_name = 'Total Weekly Hours Spent (Avg)'

# 3. Plot the distribution of the variable of interest
# 3.1 Access the data vector from the dataframe
data_slice = np.array(df[var_name])
# 3.1.1 Obtain the median of the data slice
median = np.nanmedian(data_slice)
# 3.2 Use matplotlib to plot histogram
fig = plt.figure(1)
hist = plt.hist(data_slice,bins=NUM_BINS,weights=df['Number of Respondents'].values)
plt.vlines([median],ymin=0,ymax=hist[0].max()*1.2,colors=['r'],linestyles=['dashed'],label=f'Median = {median}')
plt.ylim([hist[0].min(), hist[0].max()*1.2])
plt.title(f'Distribution of Values for {var_name}')
plt.legend()
plt.tight_layout()
plt.show(block=True)

# save the figure as a png
output_filename = f'distribution({var_name})[bins={NUM_BINS}].png'
output_path = os.path.join(OUTPUT_FOLDER,output_filename)
fig.savefig(output_path)

