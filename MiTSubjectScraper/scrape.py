# The purpose of this script is to extract data from the MIT subject evaluation site. 
# Currently the script is only designed to handle one subject at a time, due to the large number of subjects in the database.
# Each course is currently set to take approximately 2 seconds to scrape, so it can take on the order of an hour or so to scrape all course data for a given subject.abs

import requests
import browser_cookie3
import re
import pandas as pd
import time
import os
import numpy as np
import math
from bs4 import BeautifulSoup, Tag
from catalog_mapping import course_names

# 1. Initialization
CSV_FOLDER_PATH = "course_csv_info"
SUBJECT_NUMBER = 2
SUBJECT_NUMBER = str(SUBJECT_NUMBER)
BASE_URL = "https://eduapps.mit.edu/ose-rpt/"
SUBJECT_URL_SUFFIX = f"subjectEvaluationSearch.htm?termId=&departmentId=+++{SUBJECT_NUMBER}&subjectCode=&instructorName=&search=Search"
MIT_CATALOG_BASE_URL = "http://catalog.mit.edu/subjects/"
subject_url = BASE_URL + SUBJECT_URL_SUFFIX

# Load browser cookies
cookies = browser_cookie3.firefox()

# Start a session for requests
session = requests.Session()

def check_course_exists_in_dataframe(course_number, term, year, df):
    """Check if a course exists in the dataframe based on its course number."""
    # 0. Initialize the output variable
    output_condition = False

    # 1. Convert the course number to the format used in the dataframe
    course_number = f'="{course_number}"'

    # 2. Check if the course number, year, and term exists in the dataframe already
    if course_number in df['Course Number'].values:
        # 2.1 Get the row of the course, that is, where the course number, term, and year match
        course_rows = df.loc[df['Course Number'] == course_number]
        course_row = course_rows.loc[(course_rows['Term'] == term) & (course_rows['Year'] == year)] if len(course_rows) > 1 else course_rows
        output_condition = True if course_row.values.any() else False
    return output_condition

def get_page_format(course_soup):
    """Determine the format of the course page."""
    
    # Find the <div> with id="contentsframe" in the course_soup
    contents_frame_div = course_soup.body.find('div', id='contentsframe')
    
    if contents_frame_div:
        # Get the first child of this div
        first_child = list(contents_frame_div.children)[1]

        # Check if the first child is a <center> tag
        if isinstance(first_child, Tag) and first_child.name == 'center':
            return "old_format"
        
        # Check if the first child is <a id="top" name="top"></a>
        elif (isinstance(first_child, Tag) and first_child.name == 'a' 
              and first_child.get('id') == 'top' and first_child.get('name') == 'top'):
            return "new_format"
        
        else:
            return "not_implemented"
    else:
        return "not_implemented"

def get_subject_rating_new_format(course_soup):
    try:
        subject_mean = float(course_soup.find_all('p')[4].get_text().replace('\xa0',' ').replace('\t','').replace('\n','').replace('\r','').split('subject: ')[1].split(' ')[0])
    except (NameError, ValueError):
        subject_mean = np.nan
    try:
        subject_std = float(str(course_soup).split('Overall rating of the subject')[1].split('width="50">')[1].split('</td>')[0])
    except (NameError, ValueError, IndexError):
        subject_std = np.nan
    
    return subject_mean, subject_std

def get_teacher_data_new_format(course_soup):
    try:
        teacher_row_data = course_soup.find('table', class_='grid').find_all('tr')[2:]
        teacher_data = {'teacher name':[], 'teacher rating':[], 'teacher help':[], 'number of votes':[]}
        for table_row in teacher_row_data:
            teacher_name = ' '.join(table_row.find_all('td')[0].get_text().replace('\xa0',' ').replace('\t','').replace('\n','').replace('\r','').split(', ')[0:2][::-1])
            teacher_help = float(table_row.find_all('td')[-2].get_text().split(' ')[0])
            teacher_rating = float(table_row.find_all('td')[-1].get_text().split(' ')[0])
            num_votes = int(table_row.find_all('td')[-1].get_text().split(' ')[-1].split('(')[1].split(')')[0])
            teacher_data['teacher name'].append(teacher_name)
            teacher_data['teacher rating'].append(teacher_rating)
            teacher_data['teacher help'].append(teacher_help)
            teacher_data['number of votes'].append(num_votes)
    except AttributeError:
        # if there are no teachers, append np.nan to all the lists
        teacher_data = {'teacher name':[np.nan], 'teacher rating':[np.nan], 'teacher help':[np.nan], 'number of votes':[np.nan]}

    return teacher_data

def combine_distributions(mean1, std1, n1, mean2, std2, n2):
    # Calculate the combined weight
    combined_weight = n1 + n2

    # Calculate the weighted mean
    combined_mean = (mean1 * n1 + mean2 * n2) / combined_weight

    # Compute the combined variance using the provided formula
    combined_variance = (n1 * std1**2 + n2 * std2**2 + n1 * (mean1 - combined_mean)**2 + n2 * (mean2 - combined_mean)**2) / combined_weight

    # Calculate the combined standard deviation
    combined_std = np.sqrt(combined_variance)

    return combined_mean, combined_std, combined_weight

def add_teacher_data_to_df(professor_df, teacher_dict):
    # 1. Iterate over each teacher
    for i, teacher_name in enumerate(teacher_dict['teacher name']):
        # 2. Check if the teacher exists in the dataframe
        if teacher_name not in professor_df['Teacher Name'].values:
            # 2.1 Add the teacher to the dataframe
            add_dict = {'Teacher Name': teacher_name,
                        'Teacher Rating (Avg)': teacher_dict['teacher rating'][i],
                        'Teacher Rating (STD)': 0, # we have to assume a value here unfortunately
                        'Teacher Helpfulness (Avg)': teacher_dict['teacher help'][i],
                        'Teacher Helpfulness (STD)': 0, # we have to assume a value here unfortunately
                        'Number of Ratings': teacher_dict['number of votes'][i],
                        'Number of Classes': 1}
            new_df = pd.DataFrame(add_dict, index=[0])
            professor_df = pd.concat([professor_df,new_df], ignore_index=True)
        else:
            # 2.2 Get the current teacher's rating, helpfulness, and number of ratings
            current_teacher_rating = professor_df.loc[professor_df['Teacher Name'] == teacher_name, 'Teacher Rating (Avg)'].values[0]
            current_teacher_rating_std = professor_df.loc[professor_df['Teacher Name'] == teacher_name, 'Teacher Rating (STD)'].values[0]
            current_teacher_help = professor_df.loc[professor_df['Teacher Name'] == teacher_name, 'Teacher Helpfulness (Avg)'].values[0]
            current_teacher_help_std = professor_df.loc[professor_df['Teacher Name'] == teacher_name, 'Teacher Helpfulness (STD)'].values[0]
            current_num_ratings = professor_df.loc[professor_df['Teacher Name'] == teacher_name, 'Number of Ratings'].values[0]
            current_num_classes = professor_df.loc[professor_df['Teacher Name'] == teacher_name, 'Number of Classes'].values[0]

            # 3. Update the teacher's rating, helpfulness, and number of ratings
            # 3.1 Get the delta values
            delta_teacher_rating = teacher_dict['teacher rating'][i]
            delta_teacher_help = teacher_dict['teacher help'][i]
            delta_num_ratings = teacher_dict['number of votes'][i]

            # 3.2 Combine the distributions
            combined_teacher_rating, combined_teacher_rating_std, _ = combine_distributions(current_teacher_rating, current_teacher_rating_std, current_num_ratings, delta_teacher_rating, 0, delta_num_ratings)
            combined_teacher_help, combined_teacher_help_std, _ = combine_distributions(current_teacher_help, current_teacher_help_std, current_num_ratings, delta_teacher_help, 0, delta_num_ratings)
        
            # 3.3 Update the dataframe
            professor_df.loc[professor_df['Teacher Name'] == teacher_name, 'Teacher Rating (Avg)'] = combined_teacher_rating
            professor_df.loc[professor_df['Teacher Name'] == teacher_name, 'Teacher Rating (STD)'] = combined_teacher_rating_std
            professor_df.loc[professor_df['Teacher Name'] == teacher_name, 'Teacher Helpfulness (Avg)'] = combined_teacher_help
            professor_df.loc[professor_df['Teacher Name'] == teacher_name, 'Teacher Helpfulness (STD)'] = combined_teacher_help_std
            professor_df.loc[professor_df['Teacher Name'] == teacher_name, 'Number of Ratings'] = current_num_ratings + delta_num_ratings
            professor_df.loc[professor_df['Teacher Name'] == teacher_name, 'Number of Classes'] = current_num_classes + 1

    return professor_df

def get_pace_new_format(course_soup):
    # 1. Get the pace data
    # 1.1 Get the pace average rating
    try:
        pace_avg = float(course_soup.find_all('table', class_='indivQuestions')[['ace ' in x.get_text() for x in course_soup.find_all('table', class_='indivQuestions')].index(True)].find('tbody').find_all('tr')[-3].find('td', class_='avg').get_text())
    except NameError:
        pace_avg = np.nan
    
    # 1.2 Get the pace standard deviation
    try:
        pace_std = float(course_soup.find_all('table', class_='indivQuestions')[['ace ' in x.get_text() for x in course_soup.find_all('table', class_='indivQuestions')].index(True)].find('tbody').find_all('tr')[-3].find_all('td')[-1].get_text())
    except NameError:
        pace = np.nan

    return pace_avg, pace_std

def get_hour_data_new_format(course_soup):
    # 1. Get the hours data
    # 1.0 Initialize the total hours lists
    total_hours_avg = []
    total_hours_std = []

    # 1.0.1 Get the hours table html data
    hours_table_html = course_soup.find_all('table', class_='indivQuestions')[[('hrs' in x.get_text() or 'hours' in x.get_text()) for x in course_soup.find_all('table', class_='indivQuestions')].index(True)].find('tbody').find_all('tr')

    # 1.1 Get the hours in class average
    try:
        hours_in_class_avg = float(hours_table_html[[('in class' in x.get_text() or 'in the classroom' in x.get_text()) for x in hours_table_html].index(True)].find('td', class_='avg').get_text())
        total_hours_avg.append(hours_in_class_avg)
    except:
        hours_in_class_avg = np.nan
    
    # 1.2 Get the hours in class standard deviation
    try:
        hours_in_class_std = float(hours_table_html[[('in class' in x.get_text() or 'in the classroom' in x.get_text()) for x in hours_table_html].index(True)].find_all('td')[-1].get_text())
        total_hours_std.append(hours_in_class_std)
    except:
        hours_in_class_std = np.nan
    
    # 1.3 Get the hours out of class average
    try:
        hours_out_class_avg = float(hours_table_html[['outside of the classroom' in x.get_text() for x in hours_table_html].index(True)].find('td', class_='avg').get_text())
        total_hours_avg.append(hours_out_class_avg)
    except:
        hours_out_class_avg = np.nan
    
    # 1.4 Get the hours out of class standard deviation
    try:
        hours_out_class_std = float(hours_table_html[['outside of the classroom' in x.get_text() for x in hours_table_html].index(True)].find_all('td')[-1].get_text())
        total_hours_std.append(hours_out_class_std)
    except:
        hours_out_class_std = np.nan
    
    # 1.4.1 Get the hours on homework average
    try:
        hours_on_homework_avg = float(hours_table_html[['on homework' in x.get_text() for x in hours_table_html].index(True)].find('td', class_='avg').get_text())
        total_hours_avg.append(hours_on_homework_avg)
    except:
        hours_on_homework_avg = np.nan
    
    # 1.4.2 Get the hours on homework standard deviation
    try:
        hours_on_homework_std = float(hours_table_html[['on homework' in x.get_text() for x in hours_table_html].index(True)].find_all('td')[-1].get_text())
        total_hours_std.append(hours_on_homework_std)
    except:
        hours_on_homework_std = np.nan
    
    # 1.4.3 Get the hours on lab average
    try:
        hours_lab_avg = float(hours_table_html[['in lab' in x.get_text() for x in hours_table_html].index(True)].find('td', class_='avg').get_text())
        total_hours_avg.append(hours_lab_avg)
    except:
        hours_lab_avg = np.nan
    
    # 1.4.4 Get the hours on lab standard deviation
    try:
        hours_lab_std = float(hours_table_html[['in lab' in x.get_text() for x in hours_table_html].index(True)].find_all('td')[-1].get_text())
        total_hours_std.append(hours_lab_std)
    except:
        hours_lab_std = np.nan
    
    # 1.5 Get the total hours average if given directly
    try:
        hours_per_week_avg = float(hours_table_html[['How much time (in hours) did you spend per week on this subject?' in x.get_text() for x in hours_table_html].index(True)].find('td', class_='avg').get_text())
        total_hours_avg.append(hours_per_week_avg)
    except:
        hours_per_week_avg = np.nan
    
    # 1.5.1 Get the total hours standard deviation if given directly
    try:
        hours_per_week_std = float(hours_table_html[['How much time (in hours) did you spend per week on this subject?' in x.get_text() for x in hours_table_html].index(True)].find_all('td')[-1].get_text())
        total_hours_std.append(hours_per_week_std)
    except:
        hours_per_week_std = np.nan
    
    # 1.6 Get the total hours average
    total_hours_avg = np.sum(total_hours_avg)
    total_hours_std = np.sqrt(np.sum([x**2 for x in total_hours_std])) # can only sum variances, not standard deviations. Assuming the standard deviations are independent, we can sum the variances and then take the square root to get the total standard deviation

    return total_hours_avg, total_hours_std

def get_assignment_quality_new_format(course_soup):
    # 1. Get the assignment quality data
    # 1.1 Get the assignment quality average rating
    # 1.1.1 Get the assignment quality table html data
    assignment_quality_table_html = course_soup.find_all('table', class_='indivQuestions')[[('assignments contributed to my' in x.get_text() or 'Problem sets helped me' in x.get_text() or 'Assignments contributed to my' in x.get_text()) for x in course_soup.find_all('table', class_='indivQuestions')].index(True)].find('tbody').find_all('tr')

    # 1.1.2 Get the assignment quality average
    try:
        assignment_quality_avg = float(assignment_quality_table_html[[('assignments contributed to my' in x.get_text() or 'Problem sets helped me' in x.get_text() or 'Assignments contributed to my' in x.get_text()) for x in assignment_quality_table_html].index(True)].find('td', class_='avg').get_text())
    except:
        assignment_quality_avg = np.nan
    
    # 1.1.3 Get the assignment quality standard deviation
    try:
        assignment_quality_std = float(assignment_quality_table_html[[('assignments contributed to my' in x.get_text() or 'Problem sets helped me' in x.get_text() or 'Assignments contributed to my' in x.get_text()) for x in assignment_quality_table_html].index(True)].find_all('td')[-1].get_text())
    except:
        assignment_quality_std = np.nan

    return assignment_quality_avg, assignment_quality_std

def get_grading_fairness_ratings_new_format(course_soup):
    # 1. Get the grading fairness data
    # 1.1 Get the grading fairness table html data
    grading_fairness_table = course_soup.find_all('table', class_='indivQuestions')[[('Graded fairly' in x.get_text() or 'grading thus far has been fair' in x.get_text() or 'Grading thus far has been fair' in x.get_text()) for x in course_soup.find_all('table', class_='indivQuestions')].index(True)].find('tbody').find_all('tr')

    # 1.2 Get the grading fairness average
    try:
        grading_fairness_avg = float(grading_fairness_table[[('Graded fairly' in x.get_text() or 'grading thus far has been fair' in x.get_text() or 'Grading thus far has been fair' in x.get_text()) for x in grading_fairness_table].index(True)].find('td', class_='avg').get_text())
    except:
        grading_fairness_avg = np.nan
    
    # 1.3 Get the grading fairness standard deviation
    try:
        grading_fairness_std = float(grading_fairness_table[[('Graded fairly' in x.get_text() or 'grading thus far has been fair' in x.get_text() or 'Grading thus far has been fair' in x.get_text()) for x in grading_fairness_table].index(True)].find_all('td')[-1].get_text())
    except:
        grading_fairness_std = np.nan

    return grading_fairness_avg, grading_fairness_std

def get_course_catalog_info(course_information_list, course):
    # 1. Get the course number and subject name
    course_number, subject_name = course.split(' ', 1)
    # 1.1 Find which row in course_information_list corresponds to the current course
    # 1.1.1 Define a re pattern to match the course number properly
    pattern = r'\b' + re.escape(str(course_number)) + r'\b'
    try:
        # 1.1.2 Find the row in course_information_list that matches the course number pattern
        course_information_row = course_information_list[[re.search(pattern, str(x.find('strong'))) is not None for x in course_information_list].index(True)]

        # 1.1.3 If the subject name is not in the course information row, then raise a ValueError to assign np.nan to the course information
        if subject_name not in str(course_information_row):
            print(f'{course_number} {subject_name} is not in the current MIT course catalog...')
            raise ValueError('The subject name is not in the course information row...')
        
        # 1.2 Get the level of the course (U or G)
        # 1.2.1 Define a re pattern to search for the course type (' U ' or ' G ')
        pattern = r'U \(|G \('
        # 1.2.2 Find the course type from the course information row
        try:
            course_type = re.search(pattern, str(course_information_row)).group().strip().replace('>','').replace(' (','')
        except AttributeError:
            course_type = np.nan

        # 1.3 Get the course description
        # 1.3.1 Define a re pattern to search for the course description
        pattern = r'<p class="courseblockdesc">.*</p>'
        # 1.3.2 Find the course description from the course information row
        try:
            course_description = re.search(pattern, str(course_information_row)).group().strip().replace('>','').replace('<','').replace('/','').replace('p class="courseblockdesc"','').replace('"','').replace('Description','')
        except AttributeError:
            course_description = np.nan
    except ValueError:
        course_type = np.nan
        course_description = np.nan

    return course_type, course_description, course_number, subject_name

def extract_data_from_new_webpage(course_soup, course_information_list, df, url, professor_df):
    """Extract data from a given course page."""
    # 0. Initialize the data dictionary by iterating over the columns of df
    data_dict = { column : None for column in df.columns }

    # 1. Locate the required HTML tag
    h1_tag = course_soup.find('td', class_='subjectTitle')\
                        .find('h1')

    # 2. Convert the contents of the <h1> tag into a list
    course_list = [course.strip().replace('\xa0',' ') for course in h1_tag.get_text(separator='<br>').split('<br>')]

    # 3. Extract other data from the webpage
    # 3.1. Extract the year and term
    h2_tag = course_soup.find('td', class_='subjectTitle')\
                        .find('h2')
    term_and_year = h2_tag.get_text().split('Survey Window: ')[1].replace('\xa0',' ').replace('\t','').replace('\n','').replace('\r','').split('|')[0]
    term = term_and_year.split(' ')[0]
    year = int(term_and_year.split(' ')[1])

    # 3.2. Extract data related to responders and response rate
    header_data = course_soup.find_all('p', class_="tooltip")[1:3]

    # 3.2.1. Extract the number of respondents
    number_of_respondents = int(header_data[0].get_text().split(': ')[1].split(' ')[0])

    # 3.2.2. Extract the response rate
    response_rate = float(header_data[1].get_text().split(': ')[1].split('%')[0])/100

    # 3.3 Extract data related to subject rating
    subject_rating_mean, subject_rating_std = get_subject_rating_new_format(course_soup)

    # 3.4 Extract data related to professors
    teacher_dict = get_teacher_data_new_format(course_soup)    
    
    # 3.5 Extract data related to pace
    pace_avg, pace_std = get_pace_new_format(course_soup)

    # 3.6 Extract data related to hours spent in class
    total_hours_avg, total_hours_std = get_hour_data_new_format(course_soup)

    # 3.7 Extract data related to assignment quality
    assignment_quality_avg, assignment_quality_std = get_assignment_quality_new_format(course_soup)

    # 3.8 Extract data related to grading fairness
    grading_fairness_avg, grading_fairness_std = get_grading_fairness_ratings_new_format(course_soup)

    # 4. Initialize an empty list
    output_data_list = []

    # 5. Add course data to the output data list
    # 5.1 Iterate over each course in course_list
    for course in course_list:
        # 5.2 Check if the course in question matches the subject number we are looking for
        # 5.2.1 Extract the subject number
        subject_number = course.split('.')[0]

        # 5.2.2 Check if it matches SUBJECT_NUMBER
        if subject_number == SUBJECT_NUMBER:
            # 5.3 Output the scraped course data to a dictionary
            # 5.3.1 Initialize the data dictionary
            current_data = data_dict.copy()

            # 5.3.2 Obtain data about the course from the course catalog using the course_information_list object
            course_type, course_description, course_number, subject_name = get_course_catalog_info(course_information_list, course)

            # 5.3.3 Add the data to the dictionary
            current_data["Course Number"] = f'="{course_number}"'
            current_data["Subject Name"] = subject_name
            current_data["Description"] = course_description
            current_data["Level (U or G)"] = course_type
            current_data["Year"] = year
            current_data["Term"] = term
            current_data["Teachers"] = '; '.join([str(name) for name in teacher_dict['teacher name']])
            current_data["Teacher Rating (Avg)"] = np.mean(teacher_dict['teacher rating'])
            current_data["Teacher Rating (STD)"] = np.std(teacher_dict['teacher rating'])
            current_data["Teacher Helpfulness (Avg)"] = np.mean(teacher_dict['teacher help'])
            current_data["Teacher Helpfulness (STD)"] = np.std(teacher_dict['teacher help'])
            current_data["Number of Respondents"] = number_of_respondents
            current_data["Response Rate"] = response_rate
            current_data["Subject Rating (Avg)"] = subject_rating_mean
            current_data["Subject Rating (STD)"] = subject_rating_std
            current_data["Pace (Avg)"] = pace_avg
            current_data["Pace (STD)"] = pace_std
            current_data["Total Weekly Hours Spent (Avg)"] = total_hours_avg
            current_data["Total Weekly Hours Spent (STD)"] = total_hours_std
            current_data["Assignment Quality (Avg)"] = assignment_quality_avg
            current_data["Assignment Quality (STD)"] = assignment_quality_std
            current_data["Grading Fairness (Avg)"] = grading_fairness_avg
            current_data["Grading Fairness (STD)"] = grading_fairness_std
            current_data["Webpage Link"] = url

            # 5.4 Add the data to the output data list
            output_data_list.append(current_data)

    # 6. Return the new df and professor df
    new_df = pd.DataFrame(output_data_list)
    df = pd.concat([df,new_df], ignore_index=True)
    professor_df = add_teacher_data_to_df(professor_df, teacher_dict) if teacher_dict['teacher name'][0] != np.nan else professor_df
    return df, professor_df

def extract_data_from_old_webpage(course_soup, course_information_list, df, url, professor_df):
    """Extract data from a given course page with old format."""

    # 0. Initialize data_dict with columns of df
    data_dict = {column: None for column in df.columns}

    # 1. Get the course list that contains which courses the page corresponds to
    # 1.1 Find where in the page the course list is located
    course_data_tag = course_soup.find_all('h2')[0]

    # 2. Convert contents of the found tag to a format suitable for old webpage
    # Placeholder logic
    course_list = [course.strip() for course in course_data_tag.get_text(separator='<br>').split('<br>')]

    # 3. Extract other data from old webpage format:
    # 3.1. Get year and term
    year, term = get_year_and_term_old_format(course_soup)

    # 3.2. Get data on responders and response rate
    responders_data = get_responders_data_old_format(course_soup)

    # 3.3. Get subject rating
    subject_rating_data = get_subject_rating_old_format(course_soup)

    # 3.4. Get teacher data
    teacher_data = get_teacher_data_old_format(course_soup)

    # 3.5. Get pace data
    pace_data = get_pace_old_format(course_soup)

    # 3.6. Get hours data
    hours_data = get_hours_old_format(course_soup)

    # 3.7. Get assignment quality data
    assignment_quality_data = get_assignment_quality_old_format(course_soup)

    # 3.8. Get grading fairness data
    grading_fairness_data = get_grading_fairness_old_format(course_soup)

    # 4. Initialize an empty output_data_list
    output_data_list = []

    # 5. Iterate over each course in course_list:
    # Placeholder logic for data extraction
    # 5.1. Check if course exists in df
    # 5.2. If yes, get course data from course_information_list
    # 5.3. Update current_data dictionary with scraped data
    # 5.4. Append current_data to output_data_list

    # 6. Convert output_data_list to a new_df and concatenate it with df
    new_df = pd.DataFrame(output_data_list)
    df = pd.concat([df, new_df], ignore_index=True)

    # 7. Update professor_df with teacher data

    # 8. Return df and professor_df
    return df, professor_df

def get_year_and_term_old_format(soup):
    """Get the year and term of the course from the old format webpage."""
    # 1. Find where the year and term is located
    year_and_term_tag = soup.find_all('table')[1].find_all('b')[0] # get the second table in the list
    term_and_year = year_and_term_tag.get_text().replace('\xa0',' ').replace('\t','').replace('\n','').replace('\r','').split('|')[0]
    term = term_and_year.split(' ')[0]
    year = int(term_and_year.split(' ')[1])

    return None

def get_responders_data_old_format(soup):
    return None

def get_subject_rating_old_format(soup):
    return None

def get_teacher_data_old_format(soup):
    return None

def get_pace_old_format(soup):
    return None

def get_hours_old_format(soup):
    return None

def get_assignment_quality_old_format(soup):
    return None

def get_grading_fairness_old_format(soup):
    return None

def extract_data(course_soup, course_information_list, df, url, professor_df):
    """Extract data from a given course page."""
    
    # Determine the format of the course page
    page_format = get_page_format(course_soup)
    
    # Handle the different formats
    if page_format == "new_format":
        # Extract data from the new format webpage
        df, professor_df = extract_data_from_new_webpage(course_soup, course_information_list, df, url, professor_df)
        return df, professor_df
    elif page_format == "old_format":
        # Logic to handle the old format will go here
        df, professor_df = extract_data_from_old_webpage(course_soup, course_information_list, df, url, professor_df)
        return df, professor_df
    else:
        # Handle the not_implemented case
        raise NotImplementedError("The given page format is not implemented!")
    
def process_course_link(course_link, course_information_list, df, professor_df):
    link = BASE_URL + course_link if course_link.startswith('subjectEvaluation') else course_link
    response = session.get(link, cookies=cookies)
    if response.status_code != 200:
        print(f"Error accessing course page: {link}")
        return df, professor_df

    course_soup = BeautifulSoup(response.content, 'html.parser')
    df, professor_df = extract_data(course_soup, course_information_list, df, link, professor_df)

    return df, professor_df

def extract_header_to_content(soup):
    header_to_content = {}
    current_header = None
    
    for tag in soup.find_all(['h2', 'p']):
        if tag.name == 'h2':
            current_header = tag.text
            header_to_content[current_header] = []
        elif tag.name == 'p' and current_header is not None:
            header_to_content[current_header].append(str(tag))

    return header_to_content

def get_course_year_and_term(html_string, header_to_content):
    # 1. Get the course year and term based on the link and the header_to_content dictionary
    course_year_and_term = list(header_to_content.keys())[[html_string in str(x) for x in header_to_content.values()].index(True)]

    # 2. Extract the year and term from the course_year_and_term string
    # 2.1 Extract the term
    term = course_year_and_term.split(' Term')[0]

    # 2.1.2 Convert the term to the appropriate format
    if term == 'January':
        term = 'IAP'
    
    # 2.2 Extract the year depending on the term
    if term == 'IAP' or term == 'Spring':
        year = int(course_year_and_term.split(' ')[-1].split('-')[-1])
    else:
        year = int(course_year_and_term.split(' ')[-1].split('-')[0])

    return term, year

def main():
    # Fetch the main course listing page
    response = session.get(subject_url, cookies=cookies)
    if response.status_code != 200:
        print("Error accessing the main subject URL! Please go through the login and verification process in your browser and try again.")
        print(f'Error code: {response.status_code}')
        print('Exiting...')
        return None
    
    # Get the course links list
    soup = BeautifulSoup(response.content, 'html.parser')
    course_links = soup.find_all('a', href=True)

    # Fetch the MIT course catalog subject information page
    # 1. Construct the search URL
    # 1.2 Construct the search URL using the url suffix
    search_url = MIT_CATALOG_BASE_URL + SUBJECT_NUMBER

    # 1.3 Fetch the search URL
    search_response = session.get(search_url, cookies=cookies)
    if search_response.status_code != 200:
        print("Error accessing the MIT course catalog subject information page!")
        return None
    
    # 2. Obtain a course information list from the search response
    # 2.1 Get the catalog soup
    catalog_soup = BeautifulSoup(search_response.content, 'html.parser')

    # 2.2 Get the course information list
    course_information_list = catalog_soup.find_all('div', class_='courseblock')

    # Obtain the header to content dictionary map
    header_to_content = extract_header_to_content(soup)

    # Define CSV file paths
    subject_data_csv_path = os.path.join(CSV_FOLDER_PATH, f"subject_{SUBJECT_NUMBER}.csv")
    professor_csv_path = os.path.join(CSV_FOLDER_PATH, f"professor_ratings.csv")

    # initialize the subject csv
    if pd.io.common.file_exists(subject_data_csv_path):
        df = pd.read_csv(subject_data_csv_path)
    else:
        columns = ["Year", "Term", "Course Number", "Subject Name", "Description", "Level (U or G)", "Teachers",
                   "Teacher Rating (Avg)", "Teacher Rating (STD)", 
                   "Teacher Helpfulness (Avg)", "Teacher Helpfulness (STD)", "Number of Respondents", 
                   "Response Rate", "Subject Rating (Avg)", "Subject Rating (STD)", "Pace (Avg)", 
                   "Pace (STD)", "Total Weekly Hours Spent (Avg)", "Total Weekly Hours Spent (STD)", 
                   "Assignment Quality (Avg)", "Assignment Quality (STD)", "Grading Fairness (Avg)", 
                   "Grading Fairness (STD)", "Webpage Link"]
        df = pd.DataFrame(columns=columns)
    
    # initialize the professor csv
    if pd.io.common.file_exists(professor_csv_path):
        professor_df = pd.read_csv(professor_csv_path)
    else:
        columns = ["Teacher Name", "Teacher Rating (Avg)", "Teacher Rating (STD)","Teacher Helpfulness (Avg)","Teacher Helpfulness (STD)","Number of Ratings","Number of Classes"]
        professor_df = pd.DataFrame(columns=columns)

    # Iterate through each link
    for link in course_links:
        html_string = str(link)  # Assuming the link text contains the course number
        if 'evaluation' in html_string: # "subjectId=" in html_string:
            # Get the course year and term
            term, year = get_course_year_and_term(html_string, header_to_content)

            # Get the course number
            course_number = link.get_text().split(' ')[0]

            if not check_course_exists_in_dataframe(course_number, term, year, df):
                # 1. Start the timer
                start_time = time.time()

                # 2. Process the course link
                df, professor_df = process_course_link(link['href'], course_information_list, df, professor_df)

                # 3. Sleep for 2 seconds
                elapsed_time = time.time() - start_time
                if elapsed_time < 2:
                    time.sleep(2 - elapsed_time)

                # 4. Save dataframe to CSV
                df.to_csv(subject_data_csv_path, index=False)
                professor_df.to_csv(professor_csv_path, index=False)

                print(f"Finished processing course {course_number} ({term} {year}) in {elapsed_time:0.2f} seconds!")

if __name__ == "__main__":
    main()