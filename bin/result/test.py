import csv

output_csv = "/home/dev/dev/flame-sdd-server/bin/result/result.csv"

def copy_defect_images(output_csv:str, date:str, width:int, height:int, mt_no:str):
    new_filenames = []
    try:
        with open(output_csv, 'r', newline='') as csvfile:
            reader = csv.reader(csvfile)
            next(reader)  # Skip header
            for row in reader:
                if len(row) > 0 and row[-1].strip() == '1': # if defect
                    image_filename = row[0].strip()[:-4] # remove file extension (.jpg)
                    new_filename = f"{date}_H{width}X{height}_{mt_no}_{image_filename}_x.jpg" # construct new filename
                    new_filenames.append(new_filename)
    except FileNotFoundError:
        print(f"File not found: {output_csv}")
    except Exception as e:
        print(f"Error processing {output_csv}: {e}")
    print(f"Generated {len(new_filenames)} defect image filenames.")

    print(len(new_filenames))

# Example usage
job_desc = {
    "date": "20251104010203",
    "mt_stand_width": 300,
    "mt_stand_height": 150,
    "mt_no": "S26945501"
}
copy_defect_images(output_csv=output_csv,
                    date=job_desc.get("date"),
                    width=job_desc.get("mt_stand_width"),
                    height=job_desc.get("mt_stand_height"),
                    mt_no=job_desc.get("mt_no"))

