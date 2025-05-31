import pandas as pd
import re

def extract_category(instance_name):
    """
    Extracts the subject area and difficulty level from the instance name.
    Example: "instance_IM2010_MATH4008_CSIE1212_MGT1002__soc_lazy.json" -> "soc_lazy"
    """
    # Regex to find the two relevant parts before ".json"
    match = re.search(r'__([a-zA-Z]+)_([a-zA-Z]+)\.json$', str(instance_name)) # Added str() for safety
    if match:
        part1 = match.group(1)
        part2 = match.group(2)
        
        valid_part1 = ["soc", "hum", "stem"]
        valid_part2 = ["lazy", "normal", "hard"]
        
        if part1 in valid_part1 and part2 in valid_part2:
            return f"{part1}_{part2}"
    
    # Fallback for other patterns or if the above is too specific
    # This tries to get the last two meaningful parts before .json
    if isinstance(instance_name, str) and instance_name.endswith('.json'):
        base_name = instance_name[:-5] # Remove .json
        segments = base_name.split('_')
        segments = [s for s in segments if s] # Remove empty strings from double underscores

        if len(segments) >= 2:
            part2 = segments[-1]
            part1 = segments[-2]
            
            valid_part1 = ["soc", "hum", "stem"]
            valid_part2 = ["lazy", "normal", "hard"]

            if part1 in valid_part1 and part2 in valid_part2:
                return f"{part1}_{part2}"
                
    return "unknown_category"

# --- Main Script ---

# **IMPORTANT**: Replace "your_file.csv" with the actual path to your CSV file.
csv_file_path = "big_comparison_times.csv"  # <--- CHANGE THIS TO YOUR FILENAME

# **IMPORTANT**: After running the script once, check df.columns and update this
# with the actual name of the column in your CSV that holds the instance names.
INSTANCE_NAME_COLUMN = "instance"  # <--- CHANGE THIS if your instance name column has a different header

try:
    # Load the CSV file, using the first row as headers
    df = pd.read_csv(csv_file_path)
    print(f"DataFrame shape (rows, columns): {df.shape}")
    print(f"Total number of rows loaded: {len(df)}")
    print(f"DataFrame Info:")
    df.info() # This also shows the number of entries (rows)

    # Check if the specified instance name column exists
    if INSTANCE_NAME_COLUMN not in df.columns:
        print(f"\nError: Column '{INSTANCE_NAME_COLUMN}' not found in the CSV.")
        print(f"Available columns are: {df.columns.tolist()}")
        print("Please update the 'INSTANCE_NAME_COLUMN' variable in the script.")
    else:
        # Apply the function to create the new 'category' column
        df['category'] = df[INSTANCE_NAME_COLUMN].apply(extract_category)
        
        print("\nDataFrame with the new 'category' column (first 5 rows):")
        print(df)
        print("-" * 50)

        # Verify the categories created
        print("\nUnique categories found:")
        print(df['category'].value_counts())
        print("-" * 50)

        # Identify numeric columns for description
        # Exclude the instance name column (if it's not numeric) and the new category column
        columns_to_exclude = [INSTANCE_NAME_COLUMN, 'category']
        # Select columns that are numeric and not in the exclusion list
        numeric_cols = df.select_dtypes(include=['number']).columns
        # If INSTANCE_NAME_COLUMN was accidentally included and is numeric, it might be fine,
        # but typically filenames aren't used in numeric aggregation.
        # More robust:
        potential_numeric_cols = [col for col in df.columns if col not in columns_to_exclude]
        # Filter these further to only those that are actually numeric
        # This handles cases where INSTANCE_NAME_COLUMN might be numeric but shouldn't be described.
        numeric_cols_to_describe = df[potential_numeric_cols].select_dtypes(include=['number']).columns.tolist()
        
        if not numeric_cols_to_describe:
            print("\nNo numeric columns found to describe (after excluding instance and category columns).")
            print("Please check your data or column names.")
        else:
            print(f"\nNumeric columns to be analyzed: {numeric_cols_to_describe}")
            print("-" * 50)

            # Group by the new 'category' and describe the numeric columns
            grouped_data = df.groupby('category')
            print(grouped_data.size())

            print("\nDescriptive statistics for numeric columns grouped by category:")
            for category_name, group in grouped_data:
                if category_name == "unknown_category" and group.empty:
                    continue
                print(f"\n--- Category: {category_name} ---")
                # Describe only the selected numeric columns for this group
                print(group[numeric_cols_to_describe].describe())
                print("-" * 30)

except FileNotFoundError:
    print(f"Error: The file '{csv_file_path}' was not found. Please check the path.")
except pd.errors.EmptyDataError:
    print(f"Error: The file '{csv_file_path}' is empty.")
except Exception as e:
    print(f"An error occurred: {e}")