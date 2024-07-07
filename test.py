#API 329efb3e6b1d4291b7559e2409deb4d4

import pandas as pd

# Replace 'your_file.csv' with the path to your actual CSV file
file_path = 'btsearch.csv'

# Read the CSV file
df = pd.read_csv(file_path, delimiter=';')

# Accessing the LONGuke and LATIuke columns
id=df['id']
lokalizacja=df['siec_id']
longitude = df['LONGuke']
latitude = df['LATIuke']

# Example: Print the first 5 rows of the longitude and latitude columns
print(df[['siec_id','LONGuke', 'LATIuke']].head())