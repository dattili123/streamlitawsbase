Here's a Python function that reads a file with lines in the format:

<file path> <commit id> <commit message>

and converts it into a CSV file:

import csv

def parse_commit_log_to_csv(input_file_path, output_csv_path):
    """
    Parses a file containing lines with <file path> <commit id> <commit message>
    and writes the parsed data to a CSV file.

    Args:
        input_file_path (str): Path to the input text file.
        output_csv_path (str): Path to save the output CSV file.
    """
    try:
        with open(input_file_path, 'r', encoding='ISO-8859-1') as infile, \
             open(output_csv_path, 'w', newline='', encoding='utf-8') as outfile:
            
            writer = csv.writer(outfile)
            writer.writerow(['File Path', 'Commit ID', 'Commit Message'])
            
            for line in infile:
                parts = line.strip().split()
                if len(parts) >= 3:
                    file_path = ' '.join(parts[:-2])
                    commit_id = parts[-2]
                    commit_message = parts[-1]
                    writer.writerow([file_path, commit_id, commit_message])

        print(f"CSV file created successfully at: {output_csv_path}")
    except Exception as e:
        print(f"Error occurred: {e}")

Example usage:

parse_commit_log_to_csv("path/to/your/input.txt", "path/to/output.csv")

Let me know if you want it to handle multi-word commit messages or special formatting cases.

