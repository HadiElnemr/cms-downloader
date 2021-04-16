'''functions to scrape cms-downloader'''
import getpass
import os
import random
import re
import sys
import threading

import requests
from bs4 import BeautifulSoup as bs
from iterfzf import iterfzf
from requests_ntlm import HttpNtlmAuth
from tqdm import tqdm

from Guc import DownloadFile, DownloadList

HOST = 'https://cms.guc.edu.eg'
DOWNLOADS_DIR = 'Downloads'


def authenticate_user(username, password):
    '''validate user credentials'''
    session = requests.Session()
    request_session = session.get(HOST,
                                  verify=False, auth=HttpNtlmAuth(username, password))
    return request_session.status_code == 200


def get_credinalities():
    '''login to cms website'''
    try:
        file_env = open(".env", "r")
        lines = file_env.readlines()
        cred = (lines[0].strip(), lines[1].strip())
        file_env.close()
    except:
        cred = (input("Enter Your GUC username :  "),
                getpass.getpass(prompt="Enter Your GUC Password : "))
        file_env = open(".env", "w")
        file_env.write(f"{cred[0]}\n{cred[1]}")
        file_env.close()
    return cred


def get_avaliable_courses(home_page_soup):
    '''fetch courses links'''
    course_links = []
    link_tags = home_page_soup('a')
    for link_tag in link_tags:
        course_link = link_tag.get('href', None)
        if course_link is None:
            continue
        match = re.match(
            r'\/apps\/student\/CourseViewStn\?id(.*)', course_link)
        if match:
            course_links.append(HOST+course_link)
    return course_links


def get_course_names(home_page_soup):
    '''get courses names'''
    courses_table = list(home_page_soup.find('table', {
        'id': 'ContentPlaceHolderright_ContentPlaceHoldercontent_GridViewcourses'}))
    courses_name = []
    for i in range(2, len(courses_table) - 1):
        courses_name.append(re.sub(
            r'\n*[\(][\|]([^\|]*)[\|][\)]([^\(]*)[\(].*\n*', '[\\1]\\2', courses_table[i].text))
    return courses_name


def make_courses_dir(courses_names):
    '''make Directories for each course'''
    if not os.path.exists(DOWNLOADS_DIR):
        os.makedirs(DOWNLOADS_DIR)
    for directorty in courses_names:
        if not os.path.exists(f'{DOWNLOADS_DIR}/{directorty}'):
            os.makedirs(f'{DOWNLOADS_DIR}/{directorty}')


def choose_course(courses_names, courses_links):
    ''' prompt the user a list to choose the link '''
    courses_dict = dict(zip(courses_names, courses_links))
    courses = []
    for course in courses_dict:
        courses.append(course)
    course = iterfzf(courses)
    course_url = courses_dict.get(course)
    return course_url, course


def get_course_soup(course_url, username, password, session):
    '''get course html for given course'''
    course_page = session.get(course_url, verify=False,
                              auth=HttpNtlmAuth(username, password))
    course_page_soup = bs(course_page.text, 'html.parser')
    return course_page_soup


def get_files(course_url, username, password, session):
    '''get filename link and description'''
    files = DownloadList()
    course_page_soup = get_course_soup(course_url, username, password, session)
    files_body = course_page_soup.find_all(class_="card-body")
    for i in files_body:
        url = HOST+i.find('a').get("href")
        week = i.parent.parent.parent.parent.find('h2').text
        discreption = re.sub(
            r'[0-9]* - (.*)', "\\1", i.find("div").text)
        name = re.sub(
            r'[0-9]* - (.*)', "\\1", i.find("strong").text)
        files.list.append(DownloadFile(name, url, discreption, week))
    return files


def get_announcments(course_page_soup):
    '''get course announcments'''
    announcment_section = course_page_soup.find('div', class_='row')
    announcments = announcment_section.find_all('p')
    return [announcment.text for announcment in announcments]


def get_downloded_items(course):
    '''list the already downloaded items'''
    names = []
    for directorty in os.listdir(f'{DOWNLOADS_DIR}/{course}'):
        if os.path.isdir(f"{DOWNLOADS_DIR}/{course}/{directorty}"):
            names.append(os.listdir(f'{DOWNLOADS_DIR}/{course}/{directorty}'))
        else:
            continue
    flat_names = [item for sublist in names for item in sublist]
    return [item.rsplit('.', 1)[0] for item in flat_names]


def filter_downloads(whole_files, downloaded_files):
    '''filter the downloads'''
    return diff(whole_files.get_names(), downloaded_files)


def diff(lst1, lst2):
    '''get the diff of two lists'''
    return [item for item in lst1 if item not in lst2]


def get_display_items(whole_files, names):
    '''get the items whose names will be displayed'''
    items = DownloadList()
    for i in whole_files.list:
        for j in names:
            if i.name == j:
                items.list.append(i)
    return items


def choose_files(downloadfiles):
    '''prompt the user to choose files'''
    if not downloadfiles:
        print("NO FILES YET")
        sys.exit(0)
    items_to_download_names = iterfzf(
        downloadfiles.get_discrepitions(), multi=True)
    files_to_download = DownloadList()
    for item in downloadfiles.list:
        for name in items_to_download_names:
            if item.discreption == name:
                files_to_download.list.append(item)
    return files_to_download


def check_exists(file_to_download):
    '''check if file already exists'''
    return os.path.isfile(file_to_download)


def get_random_color():
    '''generate random color'''
    colors = ['#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#00FFFF', '#800000', '#FF1493',
              '#F0FFFF', '#D2691E', '#9400D3', '#7FFFD4', '#66CDAA', '#FF6347', '#000080']
    return random.choice(colors)


def download_file(file_to_download, username, password):
    '''download a file'''

    color = get_random_color()
    response = requests.get(file_to_download.url, auth=HttpNtlmAuth(
        username, password), verify=False, stream=True, allow_redirects=True)
    total_size = int(response.headers.get('content-length'))
    initial_pos = 0

    with open(file_to_download.path, 'wb') as downloading:
        with tqdm(total=total_size, unit="B",
                  unit_scale=True, desc=file_to_download.name,
                  initial=initial_pos, colour=color, dynamic_ncols=True) as pbar:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    downloading.write(chunk)
                    pbar.update(len(chunk))


def download_files(files_to_download, username, password, pdf=False):
    '''multitherad download files'''
    therads = []
    exts = ['.pdf', '.pptx', 'zip']
    for file in files_to_download:
        file.noramlize()
        if pdf:
            if not file.ext in exts:
                continue
        if check_exists(file.path):
            continue
        process_thread = threading.Thread(
            target=download_file, args=(file, username, password))
        process_thread.start()  # start the thread
        therads.append(process_thread)
