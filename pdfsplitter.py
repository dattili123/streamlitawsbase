def split_pdf_by_size(input_pdf_path, output_dir, max_size_in_mb=1):
    """
    Split a single PDF into multiple smaller PDFs based on the specified size.

    :param input_pdf_path: Path to the input PDF file.
    :param output_dir: Directory where the split PDFs will be saved.
    :param max_size_in_mb: Maximum size for each split PDF in MB.
    """
    max_size_in_bytes = max_size_in_mb * 1024 * 1024  # Convert MB to bytes
    os.makedirs(output_dir, exist_ok=True)

    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    part_number = 1
    current_size = 0

    for page_number, page in enumerate(reader.pages, start=1):
        writer.add_page(page)

        # Create a temporary file to calculate the current PDF size
        temp_output = os.path.join(output_dir, f"temp_part_{part_number}.pdf")
        with open(temp_output, "wb") as temp_file:
            writer.write(temp_file)
        
        # Check the size of the temporary file
        current_size = os.path.getsize(temp_output)

        if current_size >= max_size_in_bytes:
            # Save the current part and reset the writer
            output_file = os.path.join(output_dir, f"split_part_{part_number}.pdf")
            os.rename(temp_output, output_file)
            print(f"Saved {output_file} with size {current_size / (1024 * 1024):.2f} MB")

            part_number += 1
            writer = PdfWriter()  # Reset writer for the next part
        else:
            # Remove the temporary file since we haven't reached the size limit
            os.remove(temp_output)

    # Save any remaining pages
    if writer.pages:
        output_file = os.path.join(output_dir, f"split_part_{part_number}.pdf")
        with open(output_file, "wb") as final_file:
            writer.write(final_file)
        print(f"Saved {output_file} with size {os.path.getsize(output_file) / (1024 * 1024):.2f} MB")
