"""
Label Balancer, balances and perform the necessary image
augmentation (e.g. 5-degree rotations + horizontal flip)
to river stream images, with site_ids.

The default augmentations are rotations every 5 degrees, from 5-30,
and then do horizontal flip, and then do 5-30 again. Therefore, we have
a total of 13x multiplier per site ID.

If you want to change the angle of rotations, you can change THETA, but you will 
need to recalculate the factor for upsampling (how much you will need to zoom into
the new image to crop out the padding). 

If you want to change the range of rotations, change MULTIPLIER. If you're doing
5-30 rotations, then it's 6x (from degree 5 to degree 10, there are 6 iterations). 
DO NOT CHANGE TOTAL_MULTIPLIER as it accounts for the original image and the horizontal flip. 

The script will determine which label images to augment
based on the number of images in the two category problem
(label 1,2,3) and (label 4,5,6). It contains three levels of 
complexity: 
    (1) augment the category with the least amount of images
    (2) augment the labels with the least amount of images
    (1) augment the site_ids with the least amount of images

The motivation behind is such that we have more data from the category, 
the label, and the site ids with least amount of images. 

Input: a dataset folder in working directory, structured like this: 
    flow_600_200/ 
        1/
            image.JPG
        2/
        ... 
        6/ 

Output: a folder named balanced_dataset with the same input structure

"""

# Import external libraries
import os
import cv2 as cv
import numpy as np
import datetime
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import script to check if data is balanced
from utils import *

"""CHANGE HYPERPARAMETERS"""
THETA = 5                                       # --> degree of rotations (per augmentation)   
FACT = 1.3                                      # --> multiplication factor to upsample (e.g. zoom into the image)
                                                # If you're using 5 degrees interval, then it takes 1.3x zoom factor on each 
                                                # image to crop out the padding resulted from rotation

                                                # If you change THETA, you must change FACT, recommended
                                                # to keep its default value

MULTIPLIER = 6                                  # If rotations from degree 5-30 (there are 6 iterations).
                                                # this number represents how many times, we need to iterate
                                                # to reach the final rotation degree

TOTAL_MULTIPLIER = (MULTIPLIER*2) + 1           # DO NOT CHANGE THIS VALUE

DATASET_NAME = "flow_600_200"                   # The directory where the labels are stored in
FOLDER_LABELS = ["1, 2, 3, 4, 5, 6"]            # The directories within DATASET_NAME representing the labels
DEST_FOLDER = "balanced_data"

def DataAugmentation(images_to_aumgment, label_dir, dest_dir, label): 
    """
    Balances a label folder by starting with the site id
    with the least amount of images until 'images_to_augmnet'
    is met
    """

    # Create the list of images
    image_list = os.listdir(label_dir)

    # Declare dictionary to count number of images in site_id
    site_ids_count = {}

    # Declare dictionary to store the full_paths of
    # each image within a site id
    site_path = {}          # dictionary with a list inside
                            # e.g. [site_id: 23]

    # Count site_id and append full_file_path
    total_files = 0
    for file_name in image_list:
        total_files += 1
        full_file_path = os.path.join(label_dir, file_name)
        site_id = file_name.split("_")[0]

        if site_id in site_ids_count:
            site_ids_count[site_id] += 1
            site_path[site_id].append(full_file_path)
        else:
            site_ids_count[site_id] = 1
            site_path[site_id] = [full_file_path]

    # Sort the dictionary, and turn it into a list
    sorted_list = SortDict(site_ids_count)    

    # Fetch date for naming convention
    current_date = datetime.datetime.now()
    formatted_date = current_date.strftime("%m%d%y")

    # Augment from the site ids with the lowest number of 
    # images until it reaches images_to_augment (total number to augment)
    counter = 1             # --> counter for number of images currently augmented 
    for element in sorted_list: 
        # Element is shaped like this: ('site_id', 2)
        # first element is the site_id (a string)
        # second element is the count

        site_index = 0
        for site in site_path[element[0]]: 
            # Now augment the original images,
            # to reach the max. The code is applying
            # the minimum degree of rotation to each
            # image in order to reach the image count
            switch = -1                                     # --> (see more down), rotations only or horizontal flipped rotations
            theta = THETA
            fact = FACT

            # After the switch is triggered two times, 
            # increase THETA and FACT            
            switch_ended = 1    

            # Continue to augment until you reached: 
            # 1) the end of images_to_augment
            # 2) the end of the multiplier (e.g. ran out of rotations and horizontal flip)
            for i in range(MULTIPLIER*2):
                basename = os.path.basename(site)
                new_file_name = f"{basename.split('_')[0]}_D{formatted_date}_{formatted_date}_{site_index}_{i}_ROT_AUG_{label}.JPG"
                new_destination = os.path.join(dest_dir, new_file_name)

                if counter > images_to_aumgment:       # --> if we reached enough images within the loop, then return
                    print(f"\nReached enough images, balancing is finished for {label}")
                    return
                elif switch == -1: #  case 1: only rotations
                    augmented_img = Data_augmentation(site, theta, fact, False)
                    cv.imwrite(new_destination, augmented_img)
                    counter+=1
                elif switch == 1:  # case 2: only horizontal flipped rotations
                    augmented_img = Data_augmentation(site, theta, fact, True)
                    cv.imwrite(new_destination, augmented_img)
                    counter+=1

                switch = switch*-1
                if switch_ended % 2 == 0:
                    theta+=5
                    fact+=0.3   # --> these THETA and FACT values ensure no black padding on final image
                switch_ended+=1
            site_index+=1

def LabelBalancer():
    """
    This function will determine which label images to 
    augment based on the number of images in the two 
    category problem (label 1,2,3) and (label, 4, 5, 6)
    """

    # Obtain image directory
    root_dir = os.getcwd()
    dataset_dir = os.path.join(root_dir, DATASET_NAME)
    dest_dir = os.path.join(root_dir, DEST_FOLDER)

    # Initialize the lists
    category_1_images = [] 
    category_2_images = []

    # The line below basically does this: 
    #                       os.path.join(dataset_dir, "1"),
    #                       os.path.join(dataset_dir, "2"), 
    #                       os.path.join(dataset_dir, "3"), 
    #                       os.path.join(dataset_dir, "4"), 
    #                       os.path.join(dataset_dir, "5"), 
    #                       os.path.join(dataset_dir, "6")]   
    all_label_dirs = [os.path.join(dataset_dir, str(i)) for i in range(1, 7)]

    # Prepare category 1
    category_1_list = [
        os.listdir(all_label_dirs[0]), 
        os.listdir(all_label_dirs[1]), 
        os.listdir(all_label_dirs[2])]
    
    for i in range(len(category_1_list)): 
        category_1_images.extend(category_1_list[i])
    
    category_1_count = len(category_1_images)

    # Prepare category 2
    category_2_list = [
        os.listdir(all_label_dirs[3]), 
        os.listdir(all_label_dirs[4]), 
        os.listdir(all_label_dirs[5])]

    for i in range(len(category_2_list)): 
        category_2_images.extend(category_2_list[i])
    
    category_2_count = len(category_2_images)

    # Create the destination directories
    # The line below is similar to all_label_dirs
    dest_label_dirs = [os.path.join(dest_dir, str(i)) for i in range(1, 7)]

    # Case #1 
    """FINISH AND ORGANIZE CASE 1"""
    if category_1_count > category_2_count: 
        print("\nCategory 1 larger than Category 2\n")

        images_to_augment = category_1_count - category_2_count
        print(f"Images to augment: {images_to_augment}\n")

        # Return the function if we do not have enough images to augment
        if category_1_count * TOTAL_MULTIPLIER < images_to_augment: 
            print("Category 2 does not contain enough images to augment to Category 1")
            print("The script will terminate...\n")
            return
        
        # If enough images, proceed to augment
        print("Category 2 does contain enough images to augment to Category 1")
        print("Proceeding to augment...\n")

        # Copy all the original files to the destination directory
        print(f"Copying original files to {dest_dir}...\n")
        max_workers = 10
        with ThreadPoolExecutor(max_workers=max_workers) as executor: 
            executor.map(Copy_dir, all_label_dirs, dest_label_dirs)

        # Get counts of each label in category 2
        # Similar to category_2_count, but instead a list of lengths
        category_2_count_split = [
            len(category_2_list[0]), 
            len(category_2_list[1]), 
            len(category_2_list[2])]
        
        # Compute the complementary probabilities for sampling
        p_label_1 = 1 - (category_2_count_split[0] / category_2_count)
        p_label_2 = 1 - (category_2_count_split[1] / category_2_count)
        p_label_3 = 1 - (category_2_count_split[2] / category_2_count)

        # Normalize the probabilities to 1, before sampling
        p_total = p_label_1 + p_label_2 + p_label_3
        p_label_1 /= p_total
        p_label_2 /= p_total
        p_label_3 /= p_total

        # Use numpy to sample which labels to augment
        sample = list(np.random.choice([1, 2, 3], images_to_augment, p=[p_label_1, p_label_2, p_label_3], replace=True))
        
        # Count how many images to augment for each label
        images_to_aug_per_label = [sample.count(1), sample.count(2), sample.count(3)]

        # Comment this out, if you want to double-check if the number
        # of images are the same
        print("\nLabel 4,5,6 should contain the respective number of images. If not, the balancing was incorrect\n")
        print(images_to_aug_per_label[0] + category_1_count_split[0])
        print(images_to_aug_per_label[1] + category_1_count_split[1])
        print(images_to_aug_per_label[2] + category_1_count_split[2])
        print()

        # Perform the data augmentation in parallel
        max_workers = 10
        with ThreadPoolExecutor(max_workers=max_workers) as executor: 
            futures = []
            for i in range(len(images_to_aug_per_label)):
                print(f"Augmenting label {i+3}...\n")
                future = executor.submit(DataAugmentation, images_to_aug_per_label[i], 
                                all_label_dirs[i+3],
                                dest_label_dirs[i+3], 
                                f"L{i+4}")
                futures.append(future)
                
        for future in as_completed(futures):
            try:
                result = future.result()  # This will raise any exceptions caught in the thread
                print("Data augmentation task completed successfully.")
            except Exception as e:
                print(f"Error in data augmentation: {e}")

    # Case #2
    else: 
        print("\nCategory 2 larger than Category 1\n")

        images_to_augment = category_2_count - category_1_count
        print(f"Images to augment: {images_to_augment}\n")

        # Return the function if we do not have enough images to augment
        if category_1_count * TOTAL_MULTIPLIER < images_to_augment: 
            print("Category 1 does not contain enough images to augment to Category 2")
            print("The script will terminate...\n")
            return
        
        # If enough images, proceed to augment
        print("Category 1 does contain enough images to augment to Category 2")
        print("Proceeding to augment...\n")

        # Copy all the original files to the destination directory
        print(f"Copying original files to {dest_dir}...\n")
        max_workers = 10
        with ThreadPoolExecutor(max_workers=max_workers) as executor: 
            executor.map(Copy_dir, all_label_dirs, dest_label_dirs)

        # Get counts of each label in category 1
        # Similar to category_1_count, but instead a list of lengths
        category_1_count_split = [
            len(category_1_list[0]), 
            len(category_1_list[1]), 
            len(category_1_list[2])]
        
        # Compute the complementary probabilities for sampling
        p_label_1 = 1 - (category_1_count_split[0] / category_1_count)
        p_label_2 = 1 - (category_1_count_split[1] / category_1_count)
        p_label_3 = 1 - (category_1_count_split[2] / category_1_count)

        # Normalize the probabilities to 1, before sampling
        p_total = p_label_1 + p_label_2 + p_label_3
        p_label_1 /= p_total
        p_label_2 /= p_total
        p_label_3 /= p_total

        # Use numpy to sample which labels to augment
        sample = list(np.random.choice([1, 2, 3], images_to_augment, p=[p_label_1, p_label_2, p_label_3], replace=True))
        
        # Count how many images to augment for each label
        images_to_aug_per_label = [sample.count(1), sample.count(2), sample.count(3)]

        # Comment this out, if you want to double-check if the number
        # of images are the same
        print("\nLabel 1,2,3 should contain the respective number of images. If not, the balancing was incorrect\n")
        print(images_to_aug_per_label[0] + category_1_count_split[0])
        print(images_to_aug_per_label[1] + category_1_count_split[1])
        print(images_to_aug_per_label[2] + category_1_count_split[2])
        print()

        # Perform the data augmentation in parallel
        max_workers = 10
        with ThreadPoolExecutor(max_workers=max_workers) as executor: 
            futures = []
            for i in range(len(images_to_aug_per_label)):
                print(f"Augmenting label {i+1}...\n")
                future = executor.submit(DataAugmentation, images_to_aug_per_label[i], 
                                all_label_dirs[i],
                                dest_label_dirs[i], 
                                f"L{i+1}")
                futures.append(future)
        for future in as_completed(futures):
            try:
                result = future.result()  # This will raise any exceptions caught in the thread
                print("Data augmentation task completed successfully.")
            except Exception as e:
                print(f"Error in data augmentation: {e}")

if __name__ == "__main__":
    des="""
    ------------------------------------------
    - CT DEEP Label Balancer and Augmentation for Image Classification (Overview) -

    Balances and perform the necessary image augmentation
    (e.g. 5-degree rotations + horizontal flip) to river
    stream images from CT DEEP, to prepare the dataset for
    image classification training. This iteration focuses on
    the two-category problem (label 1,2,3 and label 4,5,6).
    ------------------------------------------
    - The Augmentation Process -

    The default augmentations are rotations every 5 degrees (from 5-30) 
    with horizontal flip before moving to the next degree rotation. The 
    script will augment the category with the least amount of images. 
    After determining which category has less images, it will augment more
    the labels with lesser amount of images, and within each label, it will 
    augment more the site_ids with the least amount of images. 
    ------------------------------------------
    - How to Use -

    > in_dir: directory containing the labeled folders (e.g. 1,2...6)
    > out_dir (optional)
    > theta (default=5): the angle of rotation. If you change theta, you must
    change fact as well
    > fact (default=1.3): the zoom factor, after rotation.
    > multiplier (default=6): how many times to rotate. So if it's 6, it will rotate 
    from 5-30 degrees with horizontal flip in between, with a final 13x multiplier
    per image
    ------------------------------------------
    """
    # Initialize the Parser
    parser = argparse.ArgumentParser(description=des.lstrip(" "),formatter_class=argparse.RawTextHelpFormatter)

    # Add the arguments
    parser.add_argument('--in_dir',type=str,help='input directory of images with labeled subfolders\t[None]')
    parser.add_argument('--out_dir',type=str,help='output directory prefix\t[None]')
    parser.add_argument('--theta',type=int,help='the angle of rotation\t[5]')
    parser.add_argument('--fact', type=int, help='the zoom factor, after rotation\t[1.3]')
    parser.add_argument('--multiplier',type=int,help='how many times to rotate\t[6]')
    args = parser.parse_args()

    if args.in_dir is not None:
        DATASET_NAME = args.in_dir
    else: raise IOError
    if args.out_dir is not None:
        DEST_FOLDER = os.path.join(args.out_dir, "balanced_data")
    else: DEST_FOLDER
    if args.theta is not None:
        THETA = args.theta
    else: THESE = 5
    if args.fact is not None:
        FACT = args.fact
    else: FACT = 1.3
    if args.multiplier is not None:
        MULTIPLIER = args.multiplier
    else: MULTIPLIER = 6

    params = {'in_dir':DATASET_NAME,'out_dir':DEST_FOLDER,
              'theta':THETA,'fact':FACT,'multiplier':MULTIPLIER}
    print('using params:%s'%params)

    # Call the function
    LabelBalancer()
    print("\nFinish balancing the labels\nCheck your directory for 'balanced_data'")














